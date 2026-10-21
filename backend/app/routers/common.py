from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from ..config import settings
from ..models import Asset, Job, Project


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(settings.media_dir.resolve())
    except ValueError:
        return None
    return f"{settings.api_base_url}/media/{rel.as_posix()}"


def asset_out(a: Asset) -> dict:
    thumb = a.path + ".jpg" if a.kind == "video" else (a.path if a.kind == "image" else None)
    return {
        "id": a.id, "project_id": a.project_id, "kind": a.kind, "label": a.label or a.filename,
        "filename": a.filename, "duration": a.duration, "width": a.width, "height": a.height,
        "has_audio": a.has_audio, "transcribed": a.transcript is not None, "position": a.position,
        "url": media_url(a.path), "thumb_url": media_url(thumb) if thumb and Path(thumb).exists() else None,
        "transcript": a.transcript,
    }


def job_out(j: Job) -> dict:
    return {
        "id": j.id, "kind": j.kind, "project_id": j.project_id, "status": j.status, "progress": j.progress,
        "message": j.message, "error": j.error, "created_at": j.created_at, "finished_at": j.finished_at,
    }


def get_project_or_404(s: Session, project_id: int) -> Project:
    p = s.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Progetto non trovato")
    return p


def active_job(s: Session, project_id: int) -> Job | None:
    return s.exec(select(Job).where(Job.project_id == project_id, Job.status.in_(["queued", "running"]))
                  .order_by(Job.id.desc())).first()
