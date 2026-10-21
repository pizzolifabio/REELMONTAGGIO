"""Percorsi raggiungibili dal tunnel pubblico: webhook Meta, risorse lead magnet, video per Instagram."""
import hashlib
import hmac
import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlmodel import select

from ..config import settings
from ..db import session_scope
from ..leadmagnet import render_html
from ..models import Content, TimelineVersion, WebhookEvent
from ..security import verify
from ..social import dm

router = APIRouter(tags=["pubblico"])
log = logging.getLogger("reel_studio.webhooks")


@router.get("/webhooks/instagram", response_class=PlainTextResponse)
def verify_webhook(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == settings.ig_verify_token:
        return q.get("hub.challenge", "")
    raise HTTPException(403, "Verify token non valido")


def _process(event_id: int, body: dict) -> None:
    try:
        result = "; ".join(dm.handle_webhook(body)) or "nessuna azione"
    except Exception as e:  # noqa: BLE001
        log.exception("Errore webhook")
        result = f"errore: {e}"
    with session_scope() as s:
        ev = s.get(WebhookEvent, event_id)
        ev.result = result[:2000]
        s.add(ev)
        s.commit()


@router.post("/webhooks/instagram")
async def receive_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if settings.ig_app_secret:
        expected = "sha256=" + hmac.new(settings.ig_app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request.headers.get("x-hub-signature-256", "")):
            raise HTTPException(401, "Firma non valida")
    body = json.loads(raw or b"{}")
    with session_scope() as s:
        ev = WebhookEvent(body=body)
        s.add(ev)
        s.commit()
        s.refresh(ev)
    # Meta vuole una risposta 200 rapida: l'elaborazione avviene dopo
    background.add_task(_process, ev.id, body)
    return {"ok": True}


def _content_by_slug(slug: str) -> Content:
    with session_scope() as s:
        c = s.exec(select(Content).where(Content.slug == slug)).first()
    if not c:
        raise HTTPException(404, "Risorsa non trovata")
    return c


@router.get("/r/{slug}", response_class=HTMLResponse)
def resource_page(slug: str):
    c = _content_by_slug(slug)
    return render_html(c.lead_magnet, f"/r/{slug}/pdf" if c.pdf_path else None)


@router.get("/r/{slug}/pdf")
def resource_pdf(slug: str):
    c = _content_by_slug(slug)
    if not c.pdf_path or not Path(c.pdf_path).exists():
        raise HTTPException(404)
    name = (c.lead_magnet.get("title") or "guida").replace("/", "-")[:80]
    return FileResponse(c.pdf_path, media_type="application/pdf", filename=f"{name}.pdf")


@router.get("/public/renders/{project_id}/{version}/{sig}.mp4")
def public_render(project_id: int, version: int, sig: str):
    if not verify(f"render:{project_id}:{version}", sig):
        raise HTTPException(404)
    with session_scope() as s:
        tv = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == project_id,
                                                  TimelineVersion.version == version)).first()
    if not tv or not tv.render_path or not Path(tv.render_path).exists():
        raise HTTPException(404)
    return FileResponse(tv.render_path, media_type="video/mp4")
