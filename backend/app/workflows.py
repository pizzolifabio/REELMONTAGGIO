"""Workflow eseguiti dal worker: montaggio, revisioni, render, Self-Learning, contenuti, pubblicazione."""
import copy
from pathlib import Path

from sqlmodel import Session, or_, select

from . import skills
from .agent import prompts, runner
from .config import settings
from .db import session_scope
from .jobs import JobContext, handler
from .leadmagnet import export_pdf
from .models import Asset, Content, Feedback, Project, SkillProposal, TimelineVersion
from .pipeline import edl as edl_mod
from .pipeline.media import extract_audio
from .pipeline.render import render
from .pipeline.transcribe import transcribe
from .security import random_slug


def project_dir(project_id: int) -> Path:
    d = settings.media_dir / "projects" / str(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def available_assets(s: Session, project_id: int) -> dict[int, Asset]:
    """Asset del progetto + libreria globale (loghi, musica)."""
    rows = s.exec(select(Asset).where(or_(Asset.project_id == project_id, Asset.project_id == None))).all()  # noqa: E711
    return {a.id: a for a in rows}


def _split(assets: dict[int, Asset], project_id: int):
    videos = sorted((a for a in assets.values() if a.kind == "video" and a.project_id == project_id),
                    key=lambda a: (a.position, a.id))
    images = [a for a in assets.values() if a.kind == "image"]
    music = [a for a in assets.values() if a.kind == "music"]
    return videos, images, music


def _set_project(project_id: int, status: str, message: str = "") -> None:
    with session_scope() as s:
        p = s.get(Project, project_id)
        p.status, p.status_message = status, message
        s.add(p)
        s.commit()


def _validator(assets: dict[int, Asset]):
    def validate(data: dict):
        data = dict(data)
        note = data.pop("_note", "")
        full = edl_mod.validate(data, assets)
        return full, note
    return validate


def _save_version(project_id: int, edl: dict, note: str) -> int:
    with session_scope() as s:
        p = s.get(Project, project_id)
        version = p.current_version + 1
        s.add(TimelineVersion(project_id=project_id, version=version, edl=edl, note=note))
        p.current_version = version
        s.add(p)
        s.commit()
        return version


def render_version(ctx: JobContext, project_id: int, version: int, start: float = 0.0, span: float = 1.0) -> None:
    with session_scope() as s:
        tv = s.exec(select(TimelineVersion).where(
            TimelineVersion.project_id == project_id, TimelineVersion.version == version)).one()
        tv.render_status, tv.render_error = "rendering", ""
        s.add(tv)
        s.commit()
        assets = available_assets(s, project_id)
        timeline = copy.deepcopy(tv.edl)

    out = project_dir(project_id) / "renders" / f"v{version}.mp4"
    work = settings.work_dir / str(project_id) / f"v{version}"
    try:
        full = edl_mod.validate(timeline, assets)
        render(full, assets, work, out, on_progress=lambda p: ctx.progress(start + p * span))
    except Exception as e:
        with session_scope() as s:
            tv = s.get(TimelineVersion, tv.id)
            tv.render_status, tv.render_error = "error", str(e)[:2000]
            s.add(tv)
            s.commit()
        raise
    with session_scope() as s:
        tv = s.get(TimelineVersion, tv.id)
        tv.render_status, tv.render_path = "done", str(out)
        s.add(tv)
        s.commit()


@handler("process_project")
def process_project(ctx: JobContext, project_id: int) -> None:
    """Trascrive le clip, chiede all'agente la prima timeline e fa il render."""
    try:
        _set_project(project_id, "processing", "Trascrizione in corso")
        with session_scope() as s:
            to_do = [a.id for a in s.exec(select(Asset).where(
                Asset.project_id == project_id, Asset.kind == "video")).all() if a.transcript is None]
        for i, asset_id in enumerate(to_do):
            with session_scope() as s:
                a = s.get(Asset, asset_id)
                path, dur, has_audio, label = Path(a.path), a.duration, a.has_audio, a.label or a.filename
            ctx.progress(0.4 * i / max(len(to_do), 1), f"Trascrizione: {label}")
            if has_audio:
                wav = extract_audio(path, settings.work_dir / f"asset-{asset_id}.wav")
                t = transcribe(wav, dur, on_progress=lambda p, i=i: ctx.progress(0.4 * (i + p) / len(to_do)))
                wav.unlink(missing_ok=True)
            else:
                t = {"language": None, "segments": [], "words": []}
            with session_scope() as s:
                a = s.get(Asset, asset_id)
                a.transcript = t
                s.add(a)
                s.commit()

        ctx.progress(0.42, "L'agente sta montando il video")
        _set_project(project_id, "processing", "Montaggio con l'agente")
        with session_scope() as s:
            project = s.get(Project, project_id)
            assets = available_assets(s, project_id)
            videos, images, music = _split(assets, project_id)
            if not videos:
                raise RuntimeError("Carica almeno un video")
            prompt = prompts.initial_edit(project, videos, images, music, skills.load(skills.EDITING),
                                          project.music_asset_id)
        full, note = runner.run_json(prompts.EDITOR_SYSTEM, prompt, validate=_validator(assets))
        version = _save_version(project_id, full, note or "Primo montaggio")

        ctx.progress(0.5, "Render")
        _set_project(project_id, "processing", "Render del video")
        render_version(ctx, project_id, version, start=0.5, span=0.5)
        _set_project(project_id, "ready", "")
    except Exception as e:
        _set_project(project_id, "error", str(e)[:500])
        raise


@handler("apply_feedback")
def apply_feedback(ctx: JobContext, project_id: int) -> None:
    with session_scope() as s:
        project = s.get(Project, project_id)
        current = s.exec(select(TimelineVersion).where(
            TimelineVersion.project_id == project_id,
            TimelineVersion.version == project.current_version)).one()
        pending = s.exec(select(Feedback).where(
            Feedback.project_id == project_id, Feedback.status.in_(["pending", "failed"]))
            .order_by(Feedback.timestamp)).all()
        if not pending:
            return
        for fb in pending:
            fb.status = "applying"
            s.add(fb)
        s.commit()
        fb_ids = [fb.id for fb in pending]
        assets = available_assets(s, project_id)
        videos, images, music = _split(assets, project_id)
        prompt = prompts.apply_feedback(project, current.edl, pending, videos, images, music,
                                        skills.load(skills.EDITING))

    try:
        _set_project(project_id, "processing", f"Applico {len(fb_ids)} feedback")
        ctx.progress(0.05, "L'agente sta applicando i feedback")
        full, note = runner.run_json(prompts.EDITOR_SYSTEM, prompt, validate=_validator(assets))
        version = _save_version(project_id, full, note or "Revisione da feedback")
        with session_scope() as s:
            for fid in fb_ids:
                fb = s.get(Feedback, fid)
                fb.status, fb.applied_in_version = "applied", version
                s.add(fb)
            s.commit()
        ctx.progress(0.3, "Render")
        render_version(ctx, project_id, version, start=0.3, span=0.7)
        _set_project(project_id, "ready")
    except Exception as e:
        with session_scope() as s:
            for fid in fb_ids:
                fb = s.get(Feedback, fid)
                if fb.status == "applying":
                    fb.status = "failed"
                    s.add(fb)
            s.commit()
        _set_project(project_id, "error", str(e)[:500])
        raise


@handler("render")
def render_job(ctx: JobContext, project_id: int, version: int) -> None:
    _set_project(project_id, "processing", "Render del video")
    try:
        render_version(ctx, project_id, version)
        _set_project(project_id, "ready")
    except Exception as e:
        _set_project(project_id, "error", str(e)[:500])
        raise


@handler("self_learning")
def self_learning(ctx: JobContext) -> None:
    with session_scope() as s:
        rows = s.exec(select(Feedback, Project).join(Project)
                      .where(Feedback.consolidated == False).order_by(Feedback.created_at)).all()  # noqa: E712
        if not rows:
            raise RuntimeError("Nessun nuovo feedback da consolidare")
        data = [{"id": fb.id, "date": fb.created_at.strftime("%Y-%m-%d"), "project": p.name,
                 "timestamp": fb.timestamp, "text": fb.text} for fb, p in rows]
    ctx.progress(0.1, f"Analizzo {len(data)} feedback")
    current = skills.list_files()

    def validate(result: dict):
        changes = []
        for ch in result.get("changes", []):
            skills._safe_path(ch["path"])  # solleva se il percorso non è valido
            changes.append({"path": ch["path"], "reason": ch.get("reason", ""),
                            "before": current.get(ch["path"], ""), "after": ch["content"]})
        return {"summary": result.get("summary", ""), "changes": changes}

    result = runner.run_json(prompts.LEARNING_SYSTEM, prompts.self_learning(data, current), validate=validate)
    with session_scope() as s:
        s.add(SkillProposal(summary=result["summary"], changes=result["changes"], feedback_ids=[d["id"] for d in data]))
        s.commit()


def final_transcript(s: Session, project_id: int) -> str:
    project = s.get(Project, project_id)
    tv = s.exec(select(TimelineVersion).where(
        TimelineVersion.project_id == project_id, TimelineVersion.version == project.current_version)).first()
    if tv is None:
        raise RuntimeError("Il progetto non ha ancora un montaggio")
    assets = available_assets(s, project_id)
    words = edl_mod.output_words(edl_mod.validate(tv.edl, assets), assets)
    return " ".join(w["text"] for w in words)


@handler("generate_content")
def generate_content(ctx: JobContext, project_id: int) -> None:
    with session_scope() as s:
        project = s.get(Project, project_id)
        prompt = prompts.content(project, final_transcript(s, project_id), skills.load(skills.CONTENT))
    ctx.progress(0.1, "L'agente sta scrivendo i contenuti")

    def validate(d: dict):
        for key in ("keyword", "caption", "lead_magnet"):
            if not d.get(key):
                raise ValueError(f"Campo mancante: {key}")
        if not d["lead_magnet"].get("sections"):
            raise ValueError("lead_magnet.sections è vuoto")
        d["keyword"] = d["keyword"].strip().upper().split()[0]
        return d

    data = runner.run_json(prompts.CONTENT_SYSTEM, prompt, validate=validate)
    ctx.progress(0.7, "Impagino il PDF")
    with session_scope() as s:
        content = s.exec(select(Content).where(Content.project_id == project_id)).first() or Content(project_id=project_id)
        content.title = data.get("title", "")
        content.keyword = data["keyword"]
        content.caption = data["caption"]
        content.hashtags = data.get("hashtags", "")
        content.dm_message = data.get("dm_message", "")
        content.lead_magnet = data["lead_magnet"]
        content.slug = content.slug or random_slug()
        pdf = export_pdf(content.lead_magnet, project_dir(project_id) / "lead-magnet.pdf")
        content.pdf_path = str(pdf)
        s.add(content)
        s.commit()


@handler("export_pdf")
def export_pdf_job(ctx: JobContext, project_id: int) -> None:
    with session_scope() as s:
        content = s.exec(select(Content).where(Content.project_id == project_id)).one()
        content.pdf_path = str(export_pdf(content.lead_magnet, project_dir(project_id) / "lead-magnet.pdf"))
        s.add(content)
        s.commit()
