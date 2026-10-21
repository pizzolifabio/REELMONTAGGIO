"""Instagram API with Instagram Login (graph.instagram.com): pubblicazione Reel, commenti e messaggi."""
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx

from ..config import settings
from .common import SocialError, check, expires_in, get_account, needs_refresh, save_account

SCOPES = [
    "instagram_business_basic",
    "instagram_business_content_publish",
    "instagram_business_manage_comments",
    "instagram_business_manage_messages",
]


def graph(path: str) -> str:
    return f"https://graph.instagram.com/{settings.ig_api_version}/{path.lstrip('/')}"


def redirect_uri() -> str:
    # Meta richiede un redirect HTTPS: si usa il tunnel pubblico
    if not settings.public_base_url:
        raise SocialError("Imposta PUBLIC_BASE_URL (tunnel HTTPS) per collegare Instagram con OAuth")
    return f"{settings.public_base_url}/oauth/instagram/callback"


def auth_url(state: str) -> str:
    if not settings.ig_app_id:
        raise SocialError("IG_APP_ID mancante in .env")
    return "https://www.instagram.com/oauth/authorize?" + urlencode({
        "client_id": settings.ig_app_id, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": ",".join(SCOPES), "state": state,
    })


def exchange_code(code: str):
    short = check(httpx.post("https://api.instagram.com/oauth/access_token", data={
        "client_id": settings.ig_app_id, "client_secret": settings.ig_app_secret,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri(), "code": code,
    }, timeout=30))
    long = check(httpx.get("https://graph.instagram.com/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": settings.ig_app_secret,
        "access_token": short["access_token"],
    }, timeout=30))
    return connect_with_token(long["access_token"], long.get("expires_in"))


def connect_with_token(token: str, expires: int | None = None):
    me = check(httpx.get(graph("me"), params={"fields": "user_id,username", "access_token": token}, timeout=30))
    return save_account("instagram", username=me.get("username", ""), external_id=str(me.get("user_id", "")),
                        access_token=token, expires_at=expires_in(expires or 60 * 24 * 3600))


def token() -> tuple[str, str]:
    acc = get_account("instagram")
    if not acc or not acc.access_token:
        raise SocialError("Account Instagram non collegato")
    # i token long-lived durano 60 giorni e si rinnovano se hanno più di 24 ore
    if acc.expires_at and needs_refresh(acc, margin=timedelta(days=7)):
        data = check(httpx.get("https://graph.instagram.com/refresh_access_token", params={
            "grant_type": "ig_refresh_token", "access_token": acc.access_token}, timeout=30))
        acc = save_account("instagram", access_token=data["access_token"], expires_at=expires_in(data.get("expires_in")))
    return acc.access_token, acc.external_id


def _post(path: str, json: dict) -> dict:
    tok, _ = token()
    return check(httpx.post(graph(path), json=json, headers={"Authorization": f"Bearer {tok}"}, timeout=60))


def _get(path: str, **params) -> dict:
    tok, _ = token()
    return check(httpx.get(graph(path), params=params, headers={"Authorization": f"Bearer {tok}"}, timeout=60))


# --- Pubblicazione -------------------------------------------------------------------------------

def publish_reel(video_url: str, caption: str, on_status=None) -> dict:
    _, ig_id = token()
    container = _post(f"{ig_id}/media", {"media_type": "REELS", "video_url": video_url, "caption": caption,
                                          "share_to_feed": True})
    cid = container["id"]
    deadline = time.time() + 15 * 60
    while True:
        st = _get(cid, fields="status_code,status")
        code = st.get("status_code")
        if on_status:
            on_status(code)
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise SocialError(f"Instagram non ha elaborato il video: {st.get('status')}")
        if time.time() > deadline:
            raise SocialError("Timeout elaborazione video su Instagram")
        time.sleep(10)
    media = _post(f"{ig_id}/media_publish", {"creation_id": cid})
    info = _get(media["id"], fields="permalink")
    return {"id": media["id"], "url": info.get("permalink", "")}


def recent_media(limit: int = 25) -> list[dict]:
    _, ig_id = token()
    data = _get(f"{ig_id}/media", fields="id,caption,permalink,timestamp,thumbnail_url,media_url,media_product_type",
                limit=limit)
    return data.get("data", [])


# --- Commenti e messaggi --------------------------------------------------------------------------

def reply_to_comment(comment_id: str, text: str) -> dict:
    return _post(f"{comment_id}/replies", {"message": text})


def private_reply(comment_id: str, text: str, button: str | None = None, payload: str | None = None) -> dict:
    """Risposta privata a un commento (una sola consentita finché l'utente non risponde)."""
    message: dict = {"text": text}
    if button and payload:
        message["quick_replies"] = [{"content_type": "text", "title": button[:20], "payload": payload}]
    try:
        return _post("me/messages", {"recipient": {"comment_id": comment_id}, "message": message})
    except SocialError:
        if "quick_replies" not in message:
            raise
        # se i quick reply non sono accettati nella private reply, chiediamo di rispondere al messaggio
        return _post("me/messages", {"recipient": {"comment_id": comment_id},
                                     "message": {"text": f"{text}\n\nRispondi a questo messaggio per riceverla."}})


def send_message(igsid: str, text: str, button: str | None = None, payload: str | None = None) -> dict:
    message: dict = {"text": text}
    if button and payload:
        message["quick_replies"] = [{"content_type": "text", "title": button[:20], "payload": payload}]
    return _post("me/messages", {"recipient": {"id": igsid}, "message": message})


def user_profile(igsid: str) -> dict:
    """Disponibile solo dopo che l'utente ha scritto (o toccato un quick reply) nella conversazione."""
    return _get(igsid, fields="username,name,is_user_follow_business")
