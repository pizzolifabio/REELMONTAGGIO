import re
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from ..config import settings
from ..db import get_session
from ..jobs import enqueue
from ..models import (Asset, Automation, Content, Feedback, Job, Project, ScheduledPost, TimelineVersion)
from ..pipeline.media import probe, thumbnail
from ..workflows import project_dir
from .common import active_job, asset_out, get_project_or_404, job_out, media_url

router = APIRouter(prefix="/api", tags=["progetti"])

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"}


class ProjectIn(BaseModel):
    name: str
    script: str = ""
    brief: str = ""


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    script: Optional[str] = None
    brief: Optional[str] = None
    music_asset_id: Optional[int] = None


class AssetPatch(BaseModel):
    label: Optional[str] = None
    position: Optional[int] = None


def _project_summary(s: Session, p: Project) -> dict:
    first_video = s.exec(select(Asset).where(Asset.project_id == p.id, Asset.kind == "video")
                         .order_by(Asset.position, Asset.id)).first()
    current = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == p.id,
                                                   TimelineVersion.version == p.current_version)).first()
    clips = s.exec(select(Asset).where(Asset.project_id == p.id, Asset.kind == "video")).all()
    thumb = first_video.path + ".jpg" if first_video else None
    job = active_job(s, p.id)
    return {
        "id": p.id, "name": p.name, "status": p.status, "status_message": p.status_message,
        "current_version": p.current_version, "created_at": p.created_at, "clip_count": len(clips),
        "thumb_url": media_url(thumb) if thumb and Path(thumb).exists() else None,
        "render_url": media_url(current.render_path) if current and current.render_status == "done" else None,
        "job": job_out(job) if job else None,
    }


@router.get("/projects")
def list_projects(s: Session = Depends(get_session)):
    return [_project_summary(s, p) for p in s.exec(select(Project).order_by(Project.created_at.desc())).all()]


@router.post("/projects")
def create_project(body: ProjectIn, s: Session = Depends(get_session)):
    p = Project(**body.model_dump())
    s.add(p)
    s.commit()
    s.refresh(p)
    return _project_summary(s, p)


@router.get("/projects/{project_id}")
def get_project(project_id: int, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    assets = s.exec(select(Asset).where(Asset.project_id == project_id).order_by(Asset.position, Asset.id)).all()
    versions = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == project_id)
                      .order_by(TimelineVersion.version.desc())).all()
    feedback = s.exec(select(Feedback).where(Feedback.project_id == project_id).order_by(Feedback.created_at)).all()
    content = s.exec(select(Content).where(Content.project_id == project_id)).first()
    jobs = s.exec(select(Job).where(Job.project_id == project_id).order_by(Job.id.desc()).limit(10)).all()
    return {
        **_project_summary(s, p),
        "script": p.script, "brief": p.brief, "music_asset_id": p.music_asset_id,
        "assets": [asset_out(a) for a in assets],
        "versions": [{
            "version": v.version, "note": v.note, "edl": v.edl, "render_status": v.render_status,
            "render_error": v.render_error, "render_url": media_url(v.render_path), "created_at": v.created_at,
        } for v in versions],
        "feedback": [fb.model_dump() for fb in feedback],
        "has_content": content is not None,
        "jobs": [job_out(j) for j in jobs],
    }


@router.patch("/projects/{project_id}")
def update_project(project_id: int, body: ProjectPatch, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    s.add(p)
    s.commit()
    return {"ok": True}


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, s: Session = Depends(get_session)):
    get_project_or_404(s, project_id)
    if active_job(s, project_id):
        raise HTTPException(409, "C'è un'elaborazione in corso su questo progetto")
    for model in (Feedback, TimelineVersion, ScheduledPost, Content, Asset):
        s.exec(delete(model).where(model.project_id == project_id))
    for auto in s.exec(select(Automation).where(Automation.project_id == project_id)).all():
        auto.project_id = None
        s.add(auto)
    s.exec(delete(Project).where(Project.id == project_id))
    s.commit()
    shutil.rmtree(settings.media_dir / "projects" / str(project_id), ignore_errors=True)
    shutil.rmtree(settings.work_dir / str(project_id), ignore_errors=True)
    return {"ok": True}


def _store_upload(upload: UploadFile, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(upload.filename or "file").stem)[:60] or "file"
    ext = Path(upload.filename or "").suffix.lower()
    dest = folder / f"{stem}{ext}"
    n = 1
    while dest.exists():
        dest = folder / f"{stem}-{n}{ext}"
        n += 1
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f, length=4 * 1024 * 1024)
    return dest


def _create_asset(s: Session, upload: UploadFile, folder: Path, project_id: int | None, position: int = 0) -> Asset:
    ext = Path(upload.filename or "").suffix.lower()
    kind = "video" if ext in VIDEO_EXT else "image" if ext in IMAGE_EXT else "music" if ext in AUDIO_EXT else None
    if kind is None:
        raise HTTPException(400, f"Formato non supportato: {upload.filename}")
    path = _store_upload(upload, folder)
    info = {"duration": 0, "width": 0, "height": 0, "has_audio": kind != "image"}
    try:
        if kind != "image":
            info = probe(path)
        if kind == "video":
            thumbnail(path, Path(str(path) + ".jpg"), at=min(0.5, info["duration"] / 2))
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"File non leggibile ({upload.filename}): {e}") from e
    asset = Asset(project_id=project_id, kind=kind, filename=upload.filename or path.name, path=str(path),
                  label=Path(upload.filename or path.name).stem, position=position, **info)
    s.add(asset)
    return asset


@router.post("/projects/{project_id}/assets")
def upload_assets(project_id: int, files: list[UploadFile] = File(...), s: Session = Depends(get_session)):
    get_project_or_404(s, project_id)
    start = len(s.exec(select(Asset).where(Asset.project_id == project_id)).all())
    created = [_create_asset(s, f, project_dir(project_id) / "assets", project_id, start + i)
               for i, f in enumerate(files)]
    s.commit()
    return [asset_out(a) for a in created]


@router.patch("/assets/{asset_id}")
def update_asset(asset_id: int, body: AssetPatch, s: Session = Depends(get_session)):
    a = s.get(Asset, asset_id)
    if not a:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    s.add(a)
    s.commit()
    return asset_out(a)


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, s: Session = Depends(get_session)):
    a = s.get(Asset, asset_id)
    if not a:
        raise HTTPException(404)
    Path(a.path).unlink(missing_ok=True)
    Path(a.path + ".jpg").unlink(missing_ok=True)
    s.delete(a)
    s.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/process")
def process(project_id: int, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    if active_job(s, project_id):
        raise HTTPException(409, "Elaborazione già in corso")
    if not s.exec(select(Asset).where(Asset.project_id == project_id, Asset.kind == "video")).first():
        raise HTTPException(400, "Carica almeno un video")
    p.status, p.status_message = "processing", "In coda"
    s.add(p)
    s.commit()
    return job_out(enqueue("process_project", project_id=project_id))


# --- Libreria globale (loghi, grafiche, musica) ----------------------------------------------------

@router.get("/library")
def library(s: Session = Depends(get_session)):
    return [asset_out(a) for a in s.exec(select(Asset).where(Asset.project_id == None)  # noqa: E711
                                         .order_by(Asset.created_at.desc())).all()]


@router.post("/library")
def upload_library(files: list[UploadFile] = File(...), label: str = Form(""), s: Session = Depends(get_session)):
    created = []
    for f in files:
        if Path(f.filename or "").suffix.lower() in VIDEO_EXT:
            raise HTTPException(400, "La libreria accetta solo immagini e musica")
        a = _create_asset(s, f, settings.media_dir / "library", None)
        if label:
            a.label = label
        created.append(a)
    s.commit()
    return [asset_out(a) for a in created]
