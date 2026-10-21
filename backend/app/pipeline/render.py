"""Compila una EDL in un unico comando FFmpeg e lo esegue."""
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from . import captions as cap_mod
from .edl import clip_offsets, duration, output_words


class RenderError(RuntimeError):
    pass


def build_command(edl: dict[str, Any], assets: dict[int, Any], workdir: Path, output: Path) -> list[str]:
    cv = edl["canvas"]
    W, H, fps = cv["width"], cv["height"], cv["fps"]
    total = duration(edl)

    inputs: list[str] = []
    input_index: dict[Any, int] = {}

    def add_input(key: Any, args: list[str]) -> int:
        if key not in input_index:
            input_index[key] = len(input_index)
            inputs.extend(args)
        return input_index[key]

    for clip in edl["clips"]:
        add_input(("v", clip["source"]), ["-i", assets[clip["source"]].path])

    f: list[str] = []
    concat_parts = []
    for i, clip in enumerate(edl["clips"]):
        src = assets[clip["source"]]
        idx = input_index[("v", clip["source"])]
        d = clip["out"] - clip["in"]
        chain = (
            f"[{idx}:v]trim=start={clip['in']:.3f}:end={clip['out']:.3f},setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps}"
        )
        zoom = clip.get("zoom") or {}
        z0, z1 = zoom.get("from", 1), zoom.get("to", zoom.get("from", 1))
        if z0 != 1 or z1 != 1:
            frames = max(int(d * fps), 1)
            chain += (
                f",zoompan=z='{z0}+({z1}-{z0})*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d=1:s={W}x{H}:fps={fps}"
            )
        if clip.get("transition_in") == "fade":
            chain += ",fade=t=in:st=0:d=0.25"
        f.append(chain + f",format=yuv420p[v{i}]")

        if src.has_audio:
            f.append(
                f"[{idx}:a]atrim=start={clip['in']:.3f}:end={clip['out']:.3f},asetpts=PTS-STARTPTS,"
                f"aformat=sample_rates=48000:channel_layouts=stereo,"
                f"afade=t=in:d=0.02,afade=t=out:st={max(d - 0.02, 0):.3f}:d=0.02[a{i}]"
            )
        else:
            f.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f}[a{i}]")
        concat_parts.append(f"[v{i}][a{i}]")

    f.append("".join(concat_parts) + f"concat=n={len(edl['clips'])}:v=1:a=1[vcat][acat]")

    # sottotitoli + overlay di testo (libass)
    words = output_words(edl, assets)
    ass = cap_mod.build_ass(edl, words, total)
    (workdir / "captions.ass").write_text(ass, encoding="utf-8")
    f.append("[vcat]ass=filename=captions.ass[vtxt]")
    last_v = "vtxt"

    # overlay immagini (loghi, grafiche)
    for k, ov in enumerate(o for o in edl["overlays"] if o["kind"] == "image"):
        img = assets[ov["asset"]]
        idx = add_input(("img", ov["id"]), ["-loop", "1", "-framerate", str(fps), "-t", f"{total:.3f}", "-i", img.path])
        start, end = ov["start"], min(ov["end"], total)
        chain = f"[{idx}:v]format=rgba,scale={int(W * ov['width'])}:-1"
        if ov["animation"] in ("fade", "pop"):
            chain += f",fade=t=in:st={start:.3f}:d=0.25:alpha=1,fade=t=out:st={max(end - 0.25, start):.3f}:d=0.25:alpha=1"
        f.append(chain + f"[img{k}]")
        x = f"{W * ov['x']:.1f}-w/2"
        y = f"{H * ov['y']:.1f}-h/2"
        f.append(
            f"[{last_v}][img{k}]overlay=x={x}:y={y}:enable='between(t,{start:.3f},{end:.3f})'[vo{k}]"
        )
        last_v = f"vo{k}"

    # audio: voce + musica con ducking
    audio_cfg = edl["audio"]
    voice = "acat"
    if audio_cfg.get("voice_gain_db"):
        f.append(f"[acat]volume={audio_cfg['voice_gain_db']}dB[voice]")
        voice = "voice"

    music = edl["music"]
    if music.get("asset") is not None:
        m = assets[music["asset"]]
        idx = add_input(("m", music["asset"]), ["-stream_loop", "-1", "-i", m.path])
        fade = music.get("fade_out", 1.5)
        f.append(
            f"[{idx}:a]atrim=start={music.get('start_offset', 0):.3f},asetpts=PTS-STARTPTS,"
            f"atrim=duration={total:.3f},aformat=sample_rates=48000:channel_layouts=stereo,"
            f"volume={music.get('volume', 0.12)},afade=t=out:st={max(total - fade, 0):.3f}:d={fade}[mus]"
        )
        if music.get("duck", True):
            f.append(f"[{voice}]asplit=2[vmix][vsc]")
            f.append("[mus][vsc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[mducked]")
            f.append("[vmix][mducked]amix=inputs=2:duration=first:normalize=0[amix]")
        else:
            f.append(f"[{voice}][mus]amix=inputs=2:duration=first:normalize=0[amix]")
        voice = "amix"

    if audio_cfg.get("normalize", True):
        f.append(f"[{voice}]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
    else:
        f.append(f"[{voice}]anull[aout]")

    (workdir / "filter.txt").write_text(";\n".join(f), encoding="utf-8")

    return [
        settings.ffmpeg_bin, "-y", "-hide_banner", "-nostats", "-progress", "pipe:1",
        *inputs,
        "-/filter_complex", "filter.txt",
        "-map", f"[{last_v}]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-t", f"{total:.3f}",
        str(output),
    ]


def render(edl: dict[str, Any], assets: dict[int, Any], workdir: Path, output: Path,
           on_progress: Callable[[float], None] | None = None) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_command(edl, assets, workdir, output)
    total = duration(edl)
    # stderr va su file: una pipe non letta si riempie (es. avvisi libass ripetuti a ogni frame) e blocca FFmpeg
    log_path = workdir / "ffmpeg.log"
    with log_path.open("w") as log:
        proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=log, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.startswith("out_time_us=") and on_progress and total:
                try:
                    on_progress(min(int(line.split("=")[1]) / 1e6 / total, 1.0))
                except ValueError:
                    pass
        code = proc.wait()
    if code != 0:
        stderr = log_path.read_text(errors="replace").strip()
        raise RenderError(stderr.splitlines()[-1] if stderr else "FFmpeg fallito")
    return output


__all__ = ["render", "build_command", "RenderError", "clip_offsets"]
