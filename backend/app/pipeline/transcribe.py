"""Trascrizione locale con faster-whisper e timestamp per parola."""
import threading
import wave
from pathlib import Path
from typing import Callable

from ..config import settings

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(settings.whisper_model, device="auto", compute_type="int8")
    return _model


def _load_wav(path: Path):
    """Legge il WAV mono 16 kHz prodotto da FFmpeg senza passare da PyAV
    (alcune versioni di PyAV non sono compatibili con faster-whisper)."""
    import numpy as np

    with wave.open(str(path), "rb") as f:
        if f.getsampwidth() != 2 or f.getnchannels() != 1 or f.getframerate() != 16000:
            raise ValueError("Audio atteso: WAV PCM 16 bit, mono, 16 kHz")
        pcm = f.readframes(f.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(audio: Path, duration: float, on_progress: Callable[[float], None] | None = None) -> dict:
    model = _get_model()
    segments, info = model.transcribe(
        _load_wav(audio),
        language=settings.whisper_language or None,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )
    out_segments, words = [], []
    for seg in segments:
        out_segments.append({"s": round(float(seg.start), 2), "e": round(float(seg.end), 2), "text": seg.text.strip()})
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
        if on_progress and duration:
            on_progress(min(seg.end / duration, 1.0))
    return {"language": info.language, "segments": out_segments, "words": words}
