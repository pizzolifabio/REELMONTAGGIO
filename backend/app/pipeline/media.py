import json
import subprocess
from pathlib import Path

from ..config import settings


def probe(path: Path) -> dict:
    out = subprocess.run(
        [settings.ffprobe_bin, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    width = int(video["width"]) if video else 0
    height = int(video["height"]) if video else 0
    # i video da smartphone salvano la rotazione nei metadati
    rotation = 0
    if video:
        for sd in video.get("side_data_list", []):
            if "rotation" in sd:
                rotation = abs(int(sd["rotation"]))
        rotation = rotation or abs(int(video.get("tags", {}).get("rotate", 0)))
    if rotation in (90, 270):
        width, height = height, width
    return {
        "duration": float(data["format"].get("duration", 0)),
        "width": width,
        "height": height,
        "has_audio": audio is not None,
    }


def extract_audio(src: Path, dst: Path) -> Path:
    subprocess.run(
        [settings.ffmpeg_bin, "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(dst)],
        check=True,
    )
    return dst


def thumbnail(src: Path, dst: Path, at: float = 0.5) -> Path:
    subprocess.run(
        [settings.ffmpeg_bin, "-y", "-v", "error", "-ss", str(at), "-i", str(src), "-frames:v", "1",
         "-vf", "scale=360:-2", str(dst)],
        check=True,
    )
    return dst
