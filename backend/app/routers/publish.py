"""Calendario di pubblicazione multi-piattaforma."""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..jobs import enqueue
from ..models import Account, Project, ScheduledPost, TimelineVersion, now
from ..social.publisher import default_caption
from .common import get_project_or_404, media_url

router = APIRouter(prefix="/api", tags=["pubblicazione"])

Platform = Literal["instagram", "youtube", "tiktok"]


class PostIn(BaseModel):
    project_id: int
    version: Optional[int] = None
    platforms: list[Platform]
    scheduled_at: Optional[datetime] = None  # None = subito
    title: Optional[str] = None
    caption: Optional[str] = None
    privacy: Literal["public", "unlisted", "private"] = "public"


class PostPatch(BaseModel):
    scheduled_at: Optional[datetime] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    privacy: Optional[Literal["public", "unlisted", "private"]] = None


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def post_out(s: Session, post: ScheduledPost) -> dict:
    project = s.get(Project, post.project_id)
    tv = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == post.project_id,
                                              TimelineVersion.version == post.version)).first()
    return {**post.model_dump(), "scheduled_at": _utc(post.scheduled_at).isoformat(),
            "project_name": project.name if project else "",
            "render_url": media_url(tv.render_path) if tv else None}


@router.get("/posts")
def list_posts(s: Session = Depends(get_session)):
    return [post_out(s, p) for p in s.exec(select(ScheduledPost).order_by(ScheduledPost.scheduled_at.desc())).all()]


@router.post("/posts")
def create_posts(body: PostIn, s: Session = Depends(get_session)):
    project = get_project_or_404(s, body.project_id)
    version = body.version or project.current_version
    tv = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == project.id,
                                              TimelineVersion.version == version)).first()
    if not tv or tv.render_status != "done":
        raise HTTPException(400, "Questa versione non ha ancora un video renderizzato")
    if not body.platforms:
        raise HTTPException(400, "Scegli almeno una piattaforma")
    connected = {a.platform for a in s.exec(select(Account)).all()}
    missing = [p for p in body.platforms if p not in connected]
    if missing:
        raise HTTPException(400, f"Collega prima l'account: {', '.join(missing)}")

    title, caption = default_caption(project.id)
    when = _utc(body.scheduled_at) if body.scheduled_at else now()
    posts = []
    for platform in body.platforms:
        post = ScheduledPost(project_id=project.id, version=version, platform=platform, scheduled_at=when,
                             title=body.title if body.title is not None else (title or project.name),
                             caption=body.caption if body.caption is not None else caption, privacy=body.privacy)
        s.add(post)
        posts.append(post)
    s.commit()
    return [post_out(s, p) for p in posts]


@router.patch("/posts/{post_id}")
def update_post(post_id: int, body: PostPatch, s: Session = Depends(get_session)):
    post = s.get(ScheduledPost, post_id)
    if not post:
        raise HTTPException(404)
    if post.status not in ("scheduled", "failed", "cancelled"):
        raise HTTPException(400, "Il post è già in pubblicazione o pubblicato")
    data = body.model_dump(exclude_unset=True)
    if data.get("scheduled_at"):
        data["scheduled_at"] = _utc(data["scheduled_at"])
    for k, v in data.items():
        setattr(post, k, v)
    s.add(post)
    s.commit()
    return post_out(s, post)


@router.post("/posts/{post_id}/cancel")
def cancel_post(post_id: int, s: Session = Depends(get_session)):
    post = s.get(ScheduledPost, post_id)
    if not post or post.status != "scheduled":
        raise HTTPException(400, "Solo i post programmati possono essere annullati")
    post.status = "cancelled"
    s.add(post)
    s.commit()
    return post_out(s, post)


@router.post("/posts/{post_id}/retry")
def retry_post(post_id: int, s: Session = Depends(get_session)):
    post = s.get(ScheduledPost, post_id)
    if not post or post.status not in ("failed", "cancelled", "scheduled"):
        raise HTTPException(400, "Il post non può essere ripubblicato ora")
    post.status, post.error = "publishing", ""
    s.add(post)
    s.commit()
    enqueue("publish", post_id=post_id)
    return post_out(s, post)


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, s: Session = Depends(get_session)):
    post = s.get(ScheduledPost, post_id)
    if not post:
        raise HTTPException(404)
    if post.status == "publishing":
        raise HTTPException(400, "Pubblicazione in corso")
    s.delete(post)
    s.commit()
    return {"ok": True}
