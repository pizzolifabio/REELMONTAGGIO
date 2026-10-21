import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import jobs, workflows  # noqa: F401  workflows registra gli handler dei job
from .config import settings
from .db import init_db
from .routers import accounts, automations, content, learning, projects, public, publish, studio
from .social import publisher  # noqa: F401  registra l'handler "publish"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
# percorsi raggiungibili attraverso il tunnel pubblico; tutto il resto resta solo locale
PUBLIC_PREFIXES = ("/webhooks/", "/r/", "/public/", "/oauth/instagram/", "/oauth/tiktok/")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    jobs.start()
    yield
    jobs.stop()


app = FastAPI(title="Reel Studio", lifespan=lifespan)


@app.middleware("http")
async def tunnel_guard(request: Request, call_next):
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    if host not in LOCAL_HOSTS and not request.url.path.startswith(PUBLIC_PREFIXES):
        return JSONResponse({"detail": "Non disponibile"}, status_code=404)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_base_url, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (projects, studio, learning, content, publish, automations, accounts, public):
    app.include_router(r.router)

app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/api/health")
def health():
    return {"ok": True}
