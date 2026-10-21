"""Lead magnet, caption e parola chiave."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..jobs import enqueue
from ..leadmagnet import render_html
from ..models import Content
from .common import active_job, get_project_or_404, job_out, media_url

router = APIRouter(prefix="/api", tags=["contenuti"])


class ContentPatch(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    keyword: Optional[str] = None
    dm_message: Optional[str] = None
    resource_url: Optional[str] = None
    lead_magnet: Optional[dict[str, Any]] = None


def content_out(c: Content) -> dict:
    public = f"{settings.public_base_url}/r/{c.slug}" if settings.public_base_url and c.slug else None
    return {**c.model_dump(), "pdf_url": media_url(c.pdf_path), "public_url": public,
            "link": c.resource_url or public}


@router.get("/projects/{project_id}/content")
def get_content(project_id: int, s: Session = Depends(get_session)):
    c = s.exec(select(Content).where(Content.project_id == project_id)).first()
    return content_out(c) if c else None


@router.post("/projects/{project_id}/content/generate")
def generate(project_id: int, s: Session = Depends(get_session)):
    p = get_project_or_404(s, project_id)
    if p.current_version == 0:
        raise HTTPException(400, "Prima crea il montaggio")
    if active_job(s, project_id):
        raise HTTPException(409, "C'è già un'elaborazione in corso su questo progetto")
    return job_out(enqueue("generate_content", project_id=project_id))


@router.patch("/projects/{project_id}/content")
def update_content(project_id: int, body: ContentPatch, s: Session = Depends(get_session)):
    c = s.exec(select(Content).where(Content.project_id == project_id)).first()
    if not c:
        raise HTTPException(404, "Genera prima i contenuti")
    data = body.model_dump(exclude_unset=True)
    if "keyword" in data:
        data["keyword"] = data["keyword"].strip().upper()
    for k, v in data.items():
        setattr(c, k, v)
    s.add(c)
    s.commit()
    if "lead_magnet" in data:
        enqueue("export_pdf", project_id=project_id)
    return content_out(c)


@router.get("/projects/{project_id}/content/preview", response_class=HTMLResponse)
def preview(project_id: int, s: Session = Depends(get_session)):
    c = s.exec(select(Content).where(Content.project_id == project_id)).first()
    if not c:
        raise HTTPException(404)
    return render_html(c.lead_magnet, media_url(c.pdf_path))
