"""Segreto locale per firmare i link pubblici (video per Instagram, risorse lead magnet)."""
import hashlib
import hmac
import secrets

from .config import settings

_KEY_FILE = settings.data_dir / "secret.key"
if not _KEY_FILE.exists():
    _KEY_FILE.write_text(secrets.token_hex(32))
    _KEY_FILE.chmod(0o600)
SECRET = _KEY_FILE.read_text().strip().encode()


def sign(value: str, length: int = 24) -> str:
    return hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()[:length]


def verify(value: str, signature: str) -> bool:
    return hmac.compare_digest(sign(value, len(signature)), signature)


def random_slug() -> str:
    return secrets.token_urlsafe(9)
