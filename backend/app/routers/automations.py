"""Automazioni DM da commento."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from ..db import get_session
from ..models import Automation, Content, Lead, Project, WebhookEvent
from ..social import instagram
from ..social.common import SocialError
from ..social.dm import resource_link

router = APIRouter(prefix="/api", tags=["automazioni"])


class AutomationIn(BaseModel):
    name: str = ""
    project_id: Optional[int] = None
    ig_media_id: str = ""
    keyword: str
    opening_message: Optional[str] = None
    button_label: Optional[str] = None
    dm_message: Optional[str] = None
    resource_url: str = ""
    require_follow: bool = True
    follow_message: Optional[str] = None
    public_reply: str = ""
    active: bool = True


class AutomationPatch(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    ig_media_id: Optional[str] = None
    keyword: Optional[str] = None
    opening_message: Optional[str] = None
    button_label: Optional[str] = None
    dm_message: Optional[str] = None
    resource_url: Optional[str] = None
    require_follow: Optional[bool] = None
    follow_message: Optional[str] = None
    public_reply: Optional[str] = None
    active: Optional[bool] = None


def automation_out(s: Session, a: Automation) -> dict:
    counts = dict(s.exec(select(Lead.status, func.count()).where(Lead.automation_id == a.id).group_by(Lead.status)).all())
    project = s.get(Project, a.project_id) if a.project_id else None
    return {**a.model_dump(), "project_name": project.name if project else None,
            "link": resource_link(a), "stats": counts, "total": sum(counts.values())}


@router.get("/automations")
def list_automations(s: Session = Depends(get_session)):
    return [automation_out(s, a) for a in s.exec(select(Automation).order_by(Automation.created_at.desc())).all()]


@router.post("/automations")
def create_automation(body: AutomationIn, s: Session = Depends(get_session)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["keyword"] = data["keyword"].strip().upper()
    if not data["keyword"]:
        raise HTTPException(400, "Parola chiave obbligatoria")
    if body.project_id and body.dm_message is None:
        c = s.exec(select(Content).where(Content.project_id == body.project_id)).first()
        if c and c.dm_message:
            data["dm_message"] = c.dm_message
    a = Automation(**data)
    s.add(a)
    s.commit()
    s.refresh(a)
    return automation_out(s, a)


@router.patch("/automations/{automation_id}")
def update_automation(automation_id: int, body: AutomationPatch, s: Session = Depends(get_session)):
    a = s.get(Automation, automation_id)
    if not a:
        raise HTTPException(404)
    data = body.model_dump(exclude_unset=True)
    if "keyword" in data:
        data["keyword"] = data["keyword"].strip().upper()
    for k, v in data.items():
        setattr(a, k, v)
    s.add(a)
    s.commit()
    return automation_out(s, a)


@router.delete("/automations/{automation_id}")
def delete_automation(automation_id: int, s: Session = Depends(get_session)):
    a = s.get(Automation, automation_id)
    if not a:
        raise HTTPException(404)
    for lead in s.exec(select(Lead).where(Lead.automation_id == automation_id)).all():
        s.delete(lead)
    s.delete(a)
    s.commit()
    return {"ok": True}


@router.get("/leads")
def list_leads(automation_id: Optional[int] = None, s: Session = Depends(get_session)):
    q = select(Lead).order_by(Lead.updated_at.desc()).limit(300)
    if automation_id:
        q = q.where(Lead.automation_id == automation_id)
    return s.exec(q).all()


@router.get("/webhook-events")
def webhook_events(s: Session = Depends(get_session)):
    return s.exec(select(WebhookEvent).order_by(WebhookEvent.id.desc()).limit(50)).all()


@router.get("/instagram/media")
def instagram_media():
    try:
        return instagram.recent_media()
    except SocialError as e:
        raise HTTPException(400, str(e)) from e
