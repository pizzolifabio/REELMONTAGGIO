"""Self-Learning: consolidamento dei feedback in regole di skill, con approvazione esplicita."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import skills
from ..db import get_session
from ..jobs import enqueue
from ..models import Feedback, Job, Project, SkillProposal
from .common import job_out

router = APIRouter(prefix="/api", tags=["self-learning"])


class ApproveIn(BaseModel):
    paths: Optional[list[str]] = None  # None = tutte le modifiche proposte


class SkillIn(BaseModel):
    content: str


@router.get("/learning")
def overview(s: Session = Depends(get_session)):
    pending = s.exec(select(Feedback, Project).join(Project).where(Feedback.consolidated == False)  # noqa: E712
                     .order_by(Feedback.created_at.desc())).all()
    proposals = s.exec(select(SkillProposal).order_by(SkillProposal.created_at.desc()).limit(20)).all()
    job = s.exec(select(Job).where(Job.kind == "self_learning").order_by(Job.id.desc())).first()
    return {
        "pending_feedback": [{**fb.model_dump(), "project_name": p.name} for fb, p in pending],
        "proposals": [p.model_dump() for p in proposals],
        "job": job_out(job) if job else None,
    }


@router.post("/learning/run")
def run(s: Session = Depends(get_session)):
    running = s.exec(select(Job).where(Job.kind == "self_learning", Job.status.in_(["queued", "running"]))).first()
    if running:
        raise HTTPException(409, "Self-Learning già in corso")
    if not s.exec(select(Feedback).where(Feedback.consolidated == False)).first():  # noqa: E712
        raise HTTPException(400, "Nessun nuovo feedback da consolidare")
    return job_out(enqueue("self_learning"))


@router.post("/learning/proposals/{proposal_id}/approve")
def approve(proposal_id: int, body: ApproveIn, s: Session = Depends(get_session)):
    prop = s.get(SkillProposal, proposal_id)
    if not prop or prop.status != "pending":
        raise HTTPException(404, "Proposta non trovata o già gestita")
    changes = [c for c in prop.changes if body.paths is None or c["path"] in body.paths]
    skills.write([{"path": c["path"], "content": c["after"]} for c in changes])
    prop.status = "approved"
    s.add(prop)
    for fid in prop.feedback_ids:
        fb = s.get(Feedback, fid)
        if fb:
            fb.consolidated = True
            s.add(fb)
    s.commit()
    return {"ok": True, "applied": [c["path"] for c in changes]}


@router.post("/learning/proposals/{proposal_id}/reject")
def reject(proposal_id: int, s: Session = Depends(get_session)):
    prop = s.get(SkillProposal, proposal_id)
    if not prop or prop.status != "pending":
        raise HTTPException(404)
    prop.status = "rejected"
    s.add(prop)
    s.commit()
    return {"ok": True}


@router.get("/skills")
def list_skills():
    return [{"path": p, "content": c} for p, c in skills.list_files().items()]


@router.put("/skills/{path:path}")
def save_skill(path: str, body: SkillIn):
    try:
        skills.write([{"path": path, "content": body.content}])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}
