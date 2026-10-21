"""Configurazione letta da `reel-studio/.env` (vedi `.env.example`)."""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _ffmpeg_tool(name: str) -> str:
    # ffmpeg-full (keg-only su Homebrew) include libass, necessario per i sottotitoli animati
    full = Path("/opt/homebrew/opt/ffmpeg-full/bin") / name
    return str(full) if full.exists() else (shutil.which(name) or name)


class Settings:
    root = ROOT
    data_dir = Path(_env("DATA_DIR", str(ROOT / "data")))
    media_dir = data_dir / "media"
    work_dir = data_dir / "work"
    skills_dir = ROOT / "skills"
    db_path = data_dir / "reel_studio.db"

    # URL del backend raggiungibile dal browser locale
    api_base_url = _env("API_BASE_URL", "http://localhost:8000")
    web_base_url = _env("WEB_BASE_URL", "http://localhost:3000")
    # URL pubblico (tunnel Cloudflare) per webhook Meta, video_url di Instagram e link ai lead magnet
    public_base_url = _env("PUBLIC_BASE_URL").rstrip("/")

    # Agente
    agent_provider = _env("AGENT_PROVIDER", "claude-cli")  # claude-cli | codex-cli | anthropic-api
    agent_model = _env("AGENT_MODEL", "opus")
    agent_timeout = int(_env("AGENT_TIMEOUT", "900"))
    anthropic_api_key = _env("ANTHROPIC_API_KEY")
    anthropic_model = _env("ANTHROPIC_MODEL", "claude-opus-5-5")
    claude_bin = _env("CLAUDE_BIN", shutil.which("claude") or str(Path.home() / ".local/bin/claude"))
    codex_bin = _env("CODEX_BIN", shutil.which("codex") or "codex")

    # Media
    ffmpeg_bin = _env("FFMPEG_BIN", _ffmpeg_tool("ffmpeg"))
    ffprobe_bin = _env("FFPROBE_BIN", _ffmpeg_tool("ffprobe"))
    whisper_model = _env("WHISPER_MODEL", "large-v3-turbo")
    whisper_language = _env("WHISPER_LANGUAGE", "it")
    chrome_bin = _env("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

    # Instagram (Instagram API with Instagram Login)
    ig_app_id = _env("IG_APP_ID")
    ig_app_secret = _env("IG_APP_SECRET")
    ig_verify_token = _env("IG_VERIFY_TOKEN", "reel-studio")
    ig_api_version = _env("IG_API_VERSION", "v26.0")

    # YouTube
    google_client_id = _env("GOOGLE_CLIENT_ID")
    google_client_secret = _env("GOOGLE_CLIENT_SECRET")

    # TikTok
    tiktok_client_key = _env("TIKTOK_CLIENT_KEY")
    tiktok_client_secret = _env("TIKTOK_CLIENT_SECRET")


settings = Settings()
for d in (settings.data_dir, settings.media_dir, settings.work_dir):
    d.mkdir(parents=True, exist_ok=True)
