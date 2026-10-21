"""Automazione DM: commento con parola chiave → risposta privata → verifica follower → invio risorsa.

Flusso conforme alle API Instagram:
1. webhook `comments` con la parola chiave → private reply (un messaggio) con pulsante quick reply;
2. l'utente tocca il pulsante o risponde → webhook `messages`; ora la User Profile API restituisce
   `is_user_follow_business`;
3. se segue la pagina → invio del link; altrimenti messaggio che chiede il follow e ripropone il pulsante.
"""
import logging
import re
import unicodedata

from sqlmodel import select

from ..config import settings
from ..db import session_scope
from ..models import Automation, Content, Lead, now
from . import instagram
from .common import get_account

log = logging.getLogger("reel_studio.dm")
PAYLOAD_PREFIX = "RS_AUTO:"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).upper()


def matches(keyword: str, text: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(normalize(keyword.strip()))}(?![A-Z0-9])", normalize(text)) is not None


def resource_link(auto: Automation) -> str:
    if auto.resource_url:
        return auto.resource_url
    if auto.project_id:
        with session_scope() as s:
            c = s.exec(select(Content).where(Content.project_id == auto.project_id)).first()
            if c and c.resource_url:
                return c.resource_url
            if c and c.slug and settings.public_base_url:
                return f"{settings.public_base_url}/r/{c.slug}"
    return ""


def find_automation(text: str, media_id: str | None) -> Automation | None:
    with session_scope() as s:
        autos = s.exec(select(Automation).where(Automation.active == True)).all()  # noqa: E712
    # prima le automazioni legate al post specifico, poi quelle globali
    autos.sort(key=lambda a: 0 if a.ig_media_id else 1)
    for a in autos:
        if a.ig_media_id and a.ig_media_id != media_id:
            continue
        if matches(a.keyword, text):
            return a
    return None


def _deliver(auto: Automation, igsid: str) -> None:
    link = resource_link(auto)
    instagram.send_message(igsid, f"{auto.dm_message}\n\n{link}".strip())


def handle_comment(value: dict) -> str:
    acc = get_account("instagram")
    sender = value.get("from", {})
    if acc and sender.get("id") == acc.external_id:
        return "ignorato: commento della pagina"
    auto = find_automation(value.get("text", ""), value.get("media", {}).get("id"))
    if not auto:
        return "nessuna automazione corrispondente"
    comment_id = value["id"]
    with session_scope() as s:
        if s.exec(select(Lead).where(Lead.comment_id == comment_id)).first():
            return "già gestito"
        lead = Lead(automation_id=auto.id, igsid=sender.get("id", ""), username=sender.get("username", ""),
                    comment_id=comment_id, comment_text=value.get("text", "")[:500])
        s.add(lead)
        s.commit()
        s.refresh(lead)
        lead_id = lead.id

    try:
        if auto.public_reply:
            instagram.reply_to_comment(comment_id, auto.public_reply)
        if auto.require_follow:
            instagram.private_reply(comment_id, auto.opening_message, auto.button_label,
                                    f"{PAYLOAD_PREFIX}{auto.id}")
            status = "contacted"
        else:
            link = resource_link(auto)
            instagram.private_reply(comment_id, f"{auto.opening_message}\n\n{auto.dm_message}\n{link}".strip())
            status = "sent"
        _set_lead(lead_id, status)
        return f"lead {lead_id}: {status}"
    except Exception as e:  # noqa: BLE001
        _set_lead(lead_id, "error", str(e))
        log.exception("Errore nella risposta al commento")
        return f"errore: {e}"


def handle_message(event: dict) -> str:
    acc = get_account("instagram")
    message = event.get("message", {})
    sender = event.get("sender", {}).get("id", "")
    if message.get("is_echo") or (acc and sender == acc.external_id):
        return "ignorato: messaggio inviato dalla pagina"
    payload = (message.get("quick_reply") or {}).get("payload") or (event.get("postback") or {}).get("payload") or ""

    with session_scope() as s:
        q = select(Lead).where(Lead.igsid == sender, Lead.status.in_(["contacted", "awaiting_follow"]))
        if payload.startswith(PAYLOAD_PREFIX):
            q = q.where(Lead.automation_id == int(payload[len(PAYLOAD_PREFIX):]))
        lead = s.exec(q.order_by(Lead.created_at.desc())).first()
        if not lead:
            return "nessun lead in attesa per questo utente"
        auto = s.get(Automation, lead.automation_id)
        lead_id = lead.id

    try:
        profile = instagram.user_profile(sender)
        if profile.get("is_user_follow_business") or not auto.require_follow:
            _deliver(auto, sender)
            _set_lead(lead_id, "sent", username=profile.get("username"))
            return f"lead {lead_id}: risorsa inviata"
        instagram.send_message(sender, auto.follow_message, auto.button_label, f"{PAYLOAD_PREFIX}{auto.id}")
        _set_lead(lead_id, "awaiting_follow", username=profile.get("username"))
        return f"lead {lead_id}: in attesa del follow"
    except Exception as e:  # noqa: BLE001
        _set_lead(lead_id, "error", str(e))
        log.exception("Errore nella gestione del messaggio")
        return f"errore: {e}"


def _set_lead(lead_id: int, status: str, error: str = "", username: str | None = None) -> None:
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        lead.status, lead.error, lead.updated_at = status, error[:1000], now()
        if username:
            lead.username = username
        s.add(lead)
        s.commit()


def handle_webhook(body: dict) -> list[str]:
    results = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                results.append(handle_comment(change.get("value", {})))
        for event in entry.get("messaging", []):
            if "message" in event or "postback" in event:
                results.append(handle_message(event))
    return results
