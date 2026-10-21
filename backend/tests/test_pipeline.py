import subprocess
from types import SimpleNamespace

import pytest

from app.config import settings
from app.pipeline import edl as edl_mod
from app.pipeline.media import probe
from app.pipeline.render import render


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    video = d / "clip.mp4"
    subprocess.run([
        settings.ffmpeg_bin, "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=6",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video),
    ], check=True)
    music = d / "music.m4a"
    subprocess.run([settings.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=220:duration=3", str(music)], check=True)
    logo = d / "logo.png"
    subprocess.run([settings.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=red:s=200x200", "-frames:v", "1", str(logo)], check=True)
    info = probe(video)
    words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4} for i, w in enumerate(
        "ciao questo è un test dei sottotitoli animati. funziona davvero bene".split())]
    return {
        1: SimpleNamespace(id=1, kind="video", path=str(video), duration=info["duration"], has_audio=True,
                           transcript={"words": words}),
        2: SimpleNamespace(id=2, kind="music", path=str(music), duration=3, has_audio=True, transcript=None),
        3: SimpleNamespace(id=3, kind="image", path=str(logo), duration=0, has_audio=False, transcript=None),
    }


def test_validate_rejects_out_of_range(media):
    with pytest.raises(edl_mod.TimelineError):
        edl_mod.validate({"clips": [{"id": "c1", "source": 1, "in": 0, "out": 99}]}, media)


def test_validate_rejects_unknown_asset(media):
    with pytest.raises(edl_mod.TimelineError):
        edl_mod.validate({"clips": [{"id": "c1", "source": 7, "in": 0, "out": 1}]}, media)


def test_output_words_are_remapped(media):
    full = edl_mod.validate({"clips": [
        {"id": "c1", "source": 1, "in": 2.0, "out": 3.0},
        {"id": "c2", "source": 1, "in": 0.0, "out": 1.0},
    ], "captions": {"corrections": {"test": "TEST"}}}, media)
    words = edl_mod.output_words(full, media)
    assert words[0]["text"] == "TEST" and words[0]["start"] == 0.0
    assert any(w["text"] == "ciao" and 1.0 <= w["start"] < 2.0 for w in words)


def test_full_render(media, tmp_path):
    timeline = {
        "clips": [
            {"id": "c1", "source": 1, "in": 0.0, "out": 2.5, "zoom": {"from": 1.0, "to": 1.15}},
            {"id": "c2", "source": 1, "in": 3.5, "out": 5.5, "transition_in": "fade"},
        ],
        "overlays": [
            {"id": "logo", "kind": "image", "asset": 3, "start": 0.5, "end": 3.0, "x": 0.85, "y": 0.1, "width": 0.15},
            {"id": "t1", "kind": "text", "text": "Titolo", "start": 0, "end": 1.5, "y": 0.2, "background": "#0A84FF"},
        ],
        "music": {"asset": 2, "volume": 0.2},
    }
    full = edl_mod.validate(timeline, media)
    out = render(full, media, tmp_path / "work", tmp_path / "out.mp4")
    info = probe(out)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert abs(info["duration"] - 4.5) < 0.2
    assert info["has_audio"]
