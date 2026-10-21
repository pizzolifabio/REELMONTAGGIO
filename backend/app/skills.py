"""Repository delle skill (memoria del Self-Learning): file Markdown in reel-studio/skills."""
import shutil
from datetime import datetime
from pathlib import Path

from .config import settings

EDITING = ("editing-style", "captions")
CONTENT = ("copywriting", "lead-magnet")


def _safe_path(rel: str) -> Path:
    path = (settings.skills_dir / rel).resolve()
    if not str(path).startswith(str(settings.skills_dir.resolve())) or path.suffix != ".md":
        raise ValueError(f"Percorso skill non valido: {rel}")
    return path


def list_files() -> dict[str, str]:
    settings.skills_dir.mkdir(exist_ok=True)
    return {
        str(p.relative_to(settings.skills_dir)): p.read_text(encoding="utf-8")
        for p in sorted(settings.skills_dir.rglob("*.md"))
    }


def load(categories: tuple[str, ...] | None = None) -> str:
    files = list_files()
    parts = [
        f"### {path}\n{content.strip()}"
        for path, content in files.items()
        if categories is None or path.split("/")[0] in categories
    ]
    return "\n\n".join(parts) or "(nessuna skill ancora)"


def read(rel: str) -> str:
    path = _safe_path(rel)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write(changes: list[dict]) -> Path:
    """Scrive le modifiche salvando prima una copia di tutte le skill (per poter tornare indietro)."""
    backup = settings.data_dir / "skills_history" / datetime.now().strftime("%Y%m%d-%H%M%S")
    if settings.skills_dir.exists():
        shutil.copytree(settings.skills_dir, backup, dirs_exist_ok=True)
    for change in changes:
        path = _safe_path(change["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(change["content"].rstrip() + "\n", encoding="utf-8")
    return backup
