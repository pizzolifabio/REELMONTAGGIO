"""Collegamento account social e stato del sistema."""
import os
import shutil
import subprocess

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Account, Job
from ..social import instagram, tiktok, youtube
from ..social.common import SocialError, new_state, pop_state
from .common import job_out

router = APIRouter(tags=["account"])
MODULES = {"instagram": instagram, "youtube": youtube, "tiktok": tiktok}


class TokenIn(BaseModel):
    access_token: str


@router.get("/api/accounts")
def list_accounts(s: Session = Depends(get_session)):
    accounts = {a.platform: a for a in s.exec(select(Account)).all()}
    configured = {
        "instagram": bool(settings.ig_app_id and settings.ig_app_secret),
        "youtube": bool(settings.google_client_id and settings.google_client_secret),
        "tiktok": bool(settings.tiktok_client_key and settings.tiktok_client_secret),
    }
    return [{
        "platform": p,
        "connected": p in accounts,
        "username": accounts[p].username if p in accounts else None,
        "expires_at": accounts[p].expires_at if p in accounts else None,
        "connected_at": accounts[p].connected_at if p in accounts else None,
        "app_configured": configured[p],
    } for p in MODULES]


@router.get("/api/accounts/{platform}/connect")
def connect(platform: str):
    module = MODULES.get(platform)
    if not module:
        raise HTTPException(404)
    try:
        return {"url": module.auth_url(new_state(platform))}
    except SocialError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/accounts/instagram/token")
def instagram_token(body: TokenIn):
    """Collegamento rapido: incolla un token generato dalla dashboard Meta (Instagram API setup)."""
    try:
        acc = instagram.connect_with_token(body.access_token.strip())
    except SocialError as e:
        raise HTTPException(400, f"Token non valido: {e}") from e
    return {"ok": True, "username": acc.username}


@router.delete("/api/accounts/{platform}")
def disconnect(platform: str, s: Session = Depends(get_session)):
    acc = s.exec(select(Account).where(Account.platform == platform)).first()
    if acc:
        s.delete(acc)
        s.commit()
    return {"ok": True}


@router.get("/oauth/{platform}/callback")
def oauth_callback(platform: str, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    module = MODULES.get(platform)
    target = f"{settings.web_base_url}/settings"
    if not module:
        raise HTTPException(404)
    if error:
        return RedirectResponse(f"{target}?error={error_description or error}")
    try:
        pop_state(state, platform)
        module.exchange_code(code)
    except SocialError as e:
        return RedirectResponse(f"{target}?error={e}")
    return RedirectResponse(f"{target}?connected={platform}")


@router.get("/api/system")
def system(s: Session = Depends(get_session)):
    def has_filter(name: str) -> bool:
        try:
            out = subprocess.run([settings.ffmpeg_bin, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
            return f" {name} " in out
        except OSError:
            return False

    jobs = s.exec(select(Job).order_by(Job.id.desc()).limit(15)).all()
    return {
        "ffmpeg": bool(shutil.which(settings.ffmpeg_bin)),
        "ffmpeg_captions": has_filter("ass"),
        "agent_provider": settings.agent_provider,
        "agent_available": bool(shutil.which(settings.claude_bin)) if settings.agent_provider == "claude-cli"
        else bool(shutil.which(settings.codex_bin)) if settings.agent_provider == "codex-cli"
        else bool(settings.anthropic_api_key),
        "whisper_model": settings.whisper_model,
        "chrome": os.path.exists(settings.chrome_bin),
        "public_base_url": settings.public_base_url or None,
        "webhook_url": f"{settings.public_base_url}/webhooks/instagram" if settings.public_base_url else None,
        "verify_token": settings.ig_verify_token,
        "oauth_redirects": {
            "instagram": f"{settings.public_base_url}/oauth/instagram/callback" if settings.public_base_url else None,
            "youtube": youtube.redirect_uri(),
            "tiktok": tiktok.redirect_uri(),
        },
        "jobs": [job_out(j) for j in jobs],
    }
