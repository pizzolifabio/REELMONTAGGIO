from pathlib import Path

from sqlmodel import select

from ..config import settings
from ..db import session_scope
from ..jobs import JobContext, handler
from ..models import Automation, Content, ScheduledPost, TimelineVersion
from ..security import sign
from . import instagram, tiktok, youtube
from .common import SocialError


def public_render_url(project_id: int, version: int) -> str:
    if not settings.public_base_url:
        raise SocialError("Instagram scarica il video da un URL pubblico: imposta PUBLIC_BASE_URL (tunnel)")
    sig = sign(f"render:{project_id}:{version}")
    return f"{settings.public_base_url}/public/renders/{project_id}/{version}/{sig}.mp4"


def _update(post_id: int, **fields) -> None:
    with session_scope() as s:
        post = s.get(ScheduledPost, post_id)
        for k, v in fields.items():
            setattr(post, k, v)
        s.add(post)
        s.commit()


@handler("publish")
def publish(ctx: JobContext, post_id: int) -> None:
    with session_scope() as s:
        post = s.get(ScheduledPost, post_id)
        if post.status == "cancelled":
            return
        tv = s.exec(select(TimelineVersion).where(TimelineVersion.project_id == post.project_id,
                                                  TimelineVersion.version == post.version)).first()
        if not tv or tv.render_status != "done" or not Path(tv.render_path).exists():
            _update(post_id, status="failed", error="Render non disponibile per questa versione")
            raise SocialError("Render non disponibile")
        path = Path(tv.render_path)
        platform, caption, title, privacy, project_id, version = (
            post.platform, post.caption, post.title, post.privacy, post.project_id, post.version)

    _update(post_id, status="publishing", error="")
    ctx.progress(0.05, f"Pubblicazione su {platform}")
    try:
        if platform == "instagram":
            result = instagram.publish_reel(public_render_url(project_id, version), caption,
                                            on_status=lambda st: ctx.progress(0.5, f"Instagram: {st}"))
            # collega le automazioni DM del progetto al post appena pubblicato
            with session_scope() as s:
                for auto in s.exec(select(Automation).where(Automation.project_id == project_id,
                                                            Automation.ig_media_id == "")).all():
                    auto.ig_media_id = result["id"]
                    s.add(auto)
                s.commit()
        elif platform == "youtube":
            result = youtube.upload_short(path, title or caption.split("\n")[0], caption, privacy)
        elif platform == "tiktok":
            result = tiktok.publish(path, caption or title, privacy,
                                    on_status=lambda st: ctx.progress(0.6, f"TikTok: {st}"))
        else:
            raise SocialError(f"Piattaforma non supportata: {platform}")
    except Exception as e:
        _update(post_id, status="failed", error=str(e)[:2000])
        raise
    note = ""
    if platform == "tiktok" and result.get("privacy") == "SELF_ONLY" and privacy == "public":
        note = "Pubblicato come privato: TikTok consente post pubblici solo alle app verificate."
    _update(post_id, status="published", external_id=result["id"], result_url=result.get("url", ""), error=note)


def default_caption(project_id: int) -> tuple[str, str]:
    with session_scope() as s:
        c = s.exec(select(Content).where(Content.project_id == project_id)).first()
        if not c:
            return "", ""
        caption = c.caption + (f"\n\n{c.hashtags}" if c.hashtags else "")
        return c.title, caption
