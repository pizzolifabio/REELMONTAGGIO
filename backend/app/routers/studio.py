"""Reel Studio: feedback a timestamp, revisioni, modifiche manuali alla timeline."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..jobs import enqueue
from ..models import Feedback, TimelineVersion
from ..pipeline import edl as edl_mod
from ..workflows import available_assets
from .common import active_job, get_project_or_404, job_out

router = APIRouter(prefix="/api", tags=["studio"])


class FeedbackIn(BaseModel):
    timestamp: float
    text: str
    asset_id: Optional[int] = None


class TimelineIn(BaseModel):
    edl: dict[str, Any]
    note: str = "Modifica manuale"


def _ensure_idle(s: Session, project_id: int) -> None:
    if active_job(s, project_id):
        raise HTTPException(409, "C'è già un'elaborazione in corso su questo progetto")


@router.post("/projects/{project_id}/feedback")
def add_feedback(project_id: int, body: FeedbackIn, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    if not body.text.strip():
        raise HTTPException(400, "Scrivi il feedback")
    fb = Feedback(project_id=project_id, version=p.current_version, timestamp=max(body.timestamp, 0),
                  text=body.text.strip(), asset_id=body.asset_id)
    s.add(fb)
    s.commit()
    s.refresh(fb)
    return fb


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: int, s: Session = Depends(get_session)):
    fb = s.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(404)
    if fb.status not in ("pending", "failed"):
        raise HTTPException(400, "Puoi eliminare solo feedback non ancora applicati")
    s.delete(fb)
    s.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/feedback/apply")
def apply_feedback(project_id: int, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    _ensure_idle(s, project_id)
    if p.current_version == 0:
        raise HTTPException(400, "Il progetto non ha ancora un montaggio")
    pending = s.exec(select(Feedback).where(Feedback.project_id == project_id,
                                            Feedback.status.in_(["pending", "failed"]))).all()
    if not pending:
        raise HTTPException(400, "Nessun feedback da applicare")
    p.status, p.status_message = "processing", "In coda"
    s.add(p)
    s.commit()
    return job_out(enqueue("apply_feedback", project_id=project_id))


def _new_version(s: Session, project_id: int, timeline: dict, note: str):
    p = get_project_or_404(s, project_id)
    _ensure_idle(s, project_id)
    try:
        full = edl_mod.validate(timeline, available_assets(s, project_id))
    except edl_mod.TimelineError as e:
        raise HTTPException(400, str(e)) from e
    p.current_version += 1
    s.add(TimelineVersion(project_id=project_id, version=p.current_version, edl=full, note=note))
    p.status, p.status_message = "processing", "In coda"
    s.add(p)
    s.commit()
    return job_out(enqueue("render", project_id=project_id, version=p.current_version))


@router.put("/projects/{project_id}/timeline")
def save_timeline(project_id: int, body: TimelineIn, s: Session = Depends(get_session)):
    return _new_version(s, project_id, body.edl, body.note)


@router.post("/projects/{project_id}/versions/{version}/restore")
def restore_version(project_id: int, version: int, s: Session = Depends(get_session)):
    tv = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == project_id,
                                              TimelineVersion.version == version)).first()
    if not tv:
        raise HTTPException(404, "Versione non trovata")
    return _new_version(s, project_id, tv.edl, f"Ripristino della versione {version}")


@router.post("/projects/{project_id}/versions/{version}/render")
def rerender(project_id: int, version: int, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    _ensure_idle(s, project_id)
    p.status, p.status_message = "processing", "In coda"
    s.add(p)
    s.commit()
    return job_out(enqueue("render", project_id=project_id, version=version))
