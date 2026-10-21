"""YouTube Data API v3: OAuth e upload resumable (Shorts = video verticale ≤ 3 minuti)."""
from pathlib import Path
from urllib.parse import urlencode

import httpx

from ..config import settings
from .common import SocialError, check, expires_in, get_account, needs_refresh, save_account

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def redirect_uri() -> str:
    return f"{settings.api_base_url}/oauth/youtube/callback"


def auth_url(state: str) -> str:
    if not settings.google_client_id:
        raise SocialError("GOOGLE_CLIENT_ID mancante in .env")
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": settings.google_client_id, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state,
    })


def exchange_code(code: str):
    data = check(httpx.post("https://oauth2.googleapis.com/token", data={
        "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
        "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri(),
    }, timeout=30))
    me = check(httpx.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                         headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=30))
    channel = (me.get("items") or [{}])[0]
    return save_account("youtube", username=channel.get("snippet", {}).get("title", ""),
                        external_id=channel.get("id", ""), access_token=data["access_token"],
                        refresh_token=data.get("refresh_token", ""), expires_at=expires_in(data.get("expires_in")))


def token() -> str:
    acc = get_account("youtube")
    if not acc or not acc.access_token:
        raise SocialError("Account YouTube non collegato")
    if needs_refresh(acc):
        if not acc.refresh_token:
            raise SocialError("Token YouTube scaduto: ricollega l'account")
        data = check(httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
            "refresh_token": acc.refresh_token, "grant_type": "refresh_token"}, timeout=30))
        acc = save_account("youtube", access_token=data["access_token"], expires_at=expires_in(data.get("expires_in")))
    return acc.access_token


def upload_short(path: Path, title: str, description: str, privacy: str = "public") -> dict:
    tok = token()
    if "#shorts" not in (title + description).lower():
        description = f"{description}\n\n#Shorts".strip()
    meta = {
        "snippet": {"title": title[:100] or "Nuovo video", "description": description[:5000], "categoryId": "22"},
        "status": {"privacyStatus": privacy if privacy in ("public", "unlisted", "private") else "public",
                   "selfDeclaredMadeForKids": False},
    }
    size = path.stat().st_size
    init = httpx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {tok}", "X-Upload-Content-Type": "video/mp4",
                 "X-Upload-Content-Length": str(size)},
        json=meta, timeout=60,
    )
    if init.status_code >= 400:
        check(init)
    upload_url = init.headers.get("Location")
    if not upload_url:
        raise SocialError(f"YouTube non ha restituito l'URL di upload: {init.text[:300]}")
    with path.open("rb") as f:
        r = httpx.put(upload_url, content=f.read(), headers={"Content-Type": "video/mp4"}, timeout=None)
    video = check(r)
    return {"id": video["id"], "url": f"https://youtube.com/shorts/{video['id']}"}
