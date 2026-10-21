"""TikTok Content Posting API (Direct Post, FILE_UPLOAD)."""
import math
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from ..config import settings
from .common import SocialError, check, expires_in, get_account, needs_refresh, save_account

API = "https://open.tiktokapis.com/v2"
SCOPES = ["user.info.basic", "video.publish"]
MIN_CHUNK = 5 * 1024 * 1024
MAX_CHUNK = 64 * 1024 * 1024


def redirect_uri() -> str:
    base = settings.public_base_url or settings.api_base_url
    return f"{base}/oauth/tiktok/callback"


def auth_url(state: str) -> str:
    if not settings.tiktok_client_key:
        raise SocialError("TIKTOK_CLIENT_KEY mancante in .env")
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": settings.tiktok_client_key, "response_type": "code", "scope": ",".join(SCOPES),
        "redirect_uri": redirect_uri(), "state": state,
    })


def _token_request(**data) -> dict:
    return check(httpx.post(f"{API}/oauth/token/", data={
        "client_key": settings.tiktok_client_key, "client_secret": settings.tiktok_client_secret, **data,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30))


def exchange_code(code: str):
    data = _token_request(code=code, grant_type="authorization_code", redirect_uri=redirect_uri())
    info = check(httpx.get(f"{API}/user/info/", params={"fields": "open_id,display_name"},
                           headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=30))
    user = info.get("data", {}).get("user", {})
    return save_account("tiktok", username=user.get("display_name", ""), external_id=data.get("open_id", ""),
                        access_token=data["access_token"], refresh_token=data.get("refresh_token", ""),
                        expires_at=expires_in(data.get("expires_in")))


def token() -> str:
    acc = get_account("tiktok")
    if not acc or not acc.access_token:
        raise SocialError("Account TikTok non collegato")
    if needs_refresh(acc):
        data = _token_request(grant_type="refresh_token", refresh_token=acc.refresh_token)
        acc = save_account("tiktok", access_token=data["access_token"],
                           refresh_token=data.get("refresh_token", acc.refresh_token),
                           expires_at=expires_in(data.get("expires_in")))
    return acc.access_token


def _headers() -> dict:
    return {"Authorization": f"Bearer {token()}", "Content-Type": "application/json; charset=UTF-8"}


def creator_info() -> dict:
    return check(httpx.post(f"{API}/post/publish/creator_info/query/", headers=_headers(), timeout=30)).get("data", {})


def _chunks(size: int) -> tuple[int, int]:
    if size <= MAX_CHUNK:
        return size, 1
    chunk = MAX_CHUNK
    return chunk, math.floor(size / chunk)  # l'ultimo chunk assorbe il resto


def publish(path: Path, title: str, privacy: str = "public", on_status=None) -> dict:
    info = creator_info()
    options = info.get("privacy_level_options", [])
    wanted = "PUBLIC_TO_EVERYONE" if privacy == "public" else "SELF_ONLY"
    # le app non ancora verificate da TikTok possono pubblicare solo SELF_ONLY
    level = wanted if wanted in options else ("SELF_ONLY" if "SELF_ONLY" in options else (options or [wanted])[0])

    size = path.stat().st_size
    chunk, count = _chunks(size)
    init = check(httpx.post(f"{API}/post/publish/video/init/", headers=_headers(), json={
        "post_info": {"title": title[:2200], "privacy_level": level, "disable_comment": False,
                      "disable_duet": False, "disable_stitch": False, "video_cover_timestamp_ms": 1000},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count},
    }, timeout=30))["data"]

    with path.open("rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            body = f.read(end - start + 1)
            r = httpx.put(init["upload_url"], content=body, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(body)),
                "Content-Range": f"bytes {start}-{end}/{size}"}, timeout=None)
            if r.status_code not in (200, 201, 206):
                raise SocialError(f"Upload TikTok fallito ({r.status_code}): {r.text[:300]}")

    publish_id = init["publish_id"]
    deadline = time.time() + 15 * 60
    while time.time() < deadline:
        st = check(httpx.post(f"{API}/post/publish/status/fetch/", headers=_headers(),
                              json={"publish_id": publish_id}, timeout=30)).get("data", {})
        status = st.get("status")
        if on_status:
            on_status(status)
        if status == "PUBLISH_COMPLETE":
            ids = st.get("publicaly_available_post_id") or []
            acc = get_account("tiktok")
            url = f"https://www.tiktok.com/@{acc.username}/video/{ids[0]}" if ids and acc else ""
            return {"id": str(ids[0]) if ids else publish_id, "url": url, "privacy": level}
        if status == "FAILED":
            raise SocialError(f"TikTok ha rifiutato il video: {st.get('fail_reason')}")
        time.sleep(8)
    raise SocialError("Timeout pubblicazione TikTok")
