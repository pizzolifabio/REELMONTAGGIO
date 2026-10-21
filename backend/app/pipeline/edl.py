"""Timeline (EDL): validazione, valori di default e mappatura parole → tempo finale."""
import copy
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA = json.loads((Path(__file__).parent / "timeline.schema.json").read_text())

DEFAULTS: dict[str, Any] = {
    "canvas": {"width": 1080, "height": 1920, "fps": 30},
    "captions": {
        "enabled": True,
        "font": "Helvetica Neue",
        "size": 78,
        "color": "#FFFFFF",
        "highlight": "#FFD60A",
        "outline": 6,
        "position_y": 0.68,
        "max_words": 3,
        "uppercase": False,
        "animation": "pop",
        "emphasis": [],
        "corrections": {},
        "hidden_ranges": [],
    },
    "overlays": [],
    "music": {"asset": None, "volume": 0.12, "duck": True, "start_offset": 0, "fade_out": 1.5},
    "audio": {"normalize": True, "voice_gain_db": 0},
}

OVERLAY_DEFAULTS = {"x": 0.5, "y": 0.15, "width": 0.3, "size": 84, "color": "#FFFFFF", "animation": "pop"}


class TimelineError(ValueError):
    pass


def with_defaults(edl: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(edl)
    for key, default in DEFAULTS.items():
        if isinstance(default, dict):
            out[key] = {**default, **(out.get(key) or {})}
        else:
            out.setdefault(key, copy.deepcopy(default))
    out["overlays"] = [{**OVERLAY_DEFAULTS, **o} for o in out.get("overlays", [])]
    for clip in out["clips"]:
        clip.setdefault("transition_in", "cut")
    return out


def validate(edl: dict[str, Any], assets: dict[int, Any]) -> dict[str, Any]:
    """Valida la EDL contro lo schema e contro gli asset reali. Restituisce la EDL con i default."""
    try:
        jsonschema.validate(edl, SCHEMA)
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path)
        raise TimelineError(f"Schema non valido in '{path}': {e.message}") from e

    full = with_defaults(edl)
    errors: list[str] = []
    for clip in full["clips"]:
        asset = assets.get(clip["source"])
        if asset is None or asset.kind != "video":
            errors.append(f"clip {clip['id']}: source {clip['source']} non è un video del progetto")
            continue
        if clip["out"] <= clip["in"]:
            errors.append(f"clip {clip['id']}: out deve essere maggiore di in")
        if clip["out"] > asset.duration + 0.05:
            errors.append(f"clip {clip['id']}: out {clip['out']} oltre la durata ({asset.duration:.2f}s)")
        if clip["out"] - clip["in"] < 0.2:
            errors.append(f"clip {clip['id']}: durata inferiore a 0.2s")

    total = duration(full)
    for ov in full["overlays"]:
        if ov["end"] <= ov["start"]:
            errors.append(f"overlay {ov['id']}: end deve essere maggiore di start")
        if ov["start"] >= total:
            errors.append(f"overlay {ov['id']}: inizia dopo la fine del video ({total:.2f}s)")
        if ov["kind"] == "image":
            a = assets.get(ov.get("asset"))
            if a is None or a.kind != "image":
                errors.append(f"overlay {ov['id']}: asset {ov.get('asset')} non è un'immagine disponibile")
        elif not ov.get("text"):
            errors.append(f"overlay {ov['id']}: testo mancante")

    music = full["music"].get("asset")
    if music is not None:
        a = assets.get(music)
        if a is None or a.kind != "music":
            errors.append(f"music: asset {music} non è una traccia musicale disponibile")

    if errors:
        raise TimelineError("; ".join(errors))
    return full


def duration(edl: dict[str, Any]) -> float:
    return sum(c["out"] - c["in"] for c in edl["clips"])


def clip_offsets(edl: dict[str, Any]) -> list[float]:
    offsets, t = [], 0.0
    for c in edl["clips"]:
        offsets.append(t)
        t += c["out"] - c["in"]
    return offsets


def _apply_corrections(text: str, corrections: dict[str, str]) -> str:
    for wrong, right in corrections.items():
        text = re.sub(rf"(?<!\w){re.escape(wrong)}(?!\w)", right, text, flags=re.IGNORECASE)
    return text


def output_words(edl: dict[str, Any], assets: dict[int, Any]) -> list[dict[str, Any]]:
    """Parole del parlato mappate sul tempo del video finale (per i sottotitoli)."""
    words: list[dict[str, Any]] = []
    corrections = edl["captions"].get("corrections", {})
    for clip, offset in zip(edl["clips"], clip_offsets(edl)):
        asset = assets.get(clip["source"])
        transcript = (asset.transcript or {}) if asset else {}
        for w in transcript.get("words", []):
            mid = (w["s"] + w["e"]) / 2
            if clip["in"] <= mid <= clip["out"]:
                start = offset + max(w["s"], clip["in"]) - clip["in"]
                end = offset + min(w["e"], clip["out"]) - clip["in"]
                text = _apply_corrections(w["w"].strip(), corrections)
                if text:
                    words.append({"text": text, "start": round(start, 3), "end": round(max(end, start + 0.05), 3)})
    hidden = edl["captions"].get("hidden_ranges", [])
    return [w for w in words if not any(a <= w["start"] < b for a, b in hidden)]
