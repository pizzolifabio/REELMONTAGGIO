"""Genera un file ASS con sottotitoli animati parola-per-parola e overlay di testo."""
from typing import Any

PUNCT_BREAK = (".", "!", "?", ":", ";")


def ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    t = max(t, 0)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def chunk_words(words: list[dict[str, Any]], max_words: int) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for w in words:
        if current and (
            len(current) >= max_words
            or w["start"] - current[-1]["end"] > 0.6
            or current[-1]["text"].endswith(PUNCT_BREAK)
        ):
            chunks.append(current)
            current = []
        current.append(w)
    if current:
        chunks.append(current)
    return chunks


def build_ass(edl: dict[str, Any], words: list[dict[str, Any]], total: float) -> str:
    cv = edl["canvas"]
    W, H = cv["width"], cv["height"]
    cap = edl["captions"]
    font = cap["font"]

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Caption,{font},{cap['size']},{ass_color(cap['color'])},{ass_color(cap['highlight'])},"
        f"&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{cap['outline']},2,5,80,80,0,1",
        f"Style: Box,{font},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,18,0,5,60,60,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    if cap.get("enabled", True):
        x, y = W // 2, int(H * cap["position_y"])
        emphasis = {e.lower().strip(".,!?") for e in cap.get("emphasis", [])}
        hl = ass_color(cap["highlight"])
        for chunk in chunk_words(words, cap["max_words"]):
            chunk_end = min(chunk[-1]["end"] + 0.15, total)
            for i, current in enumerate(chunk):
                start = current["start"] if i else chunk[0]["start"]
                end = chunk[i + 1]["start"] if i + 1 < len(chunk) else chunk_end
                if end <= start:
                    continue
                parts = []
                for j, w in enumerate(chunk):
                    text = _escape(w["text"].upper() if cap["uppercase"] else w["text"])
                    if j == i:
                        parts.append(f"{{\\c{hl}\\fscx110\\fscy110}}{text}{{\\r}}")
                    elif w["text"].lower().strip(".,!?") in emphasis:
                        parts.append(f"{{\\c{hl}}}{text}{{\\r}}")
                    else:
                        parts.append(text)
                anim = ""
                if i == 0 and cap["animation"] == "pop":
                    anim = "\\fscx70\\fscy70\\t(0,100,\\fscx100\\fscy100)"
                elif i == 0 and cap["animation"] == "fade":
                    anim = "\\fad(120,0)"
                lines.append(
                    f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,"
                    f"{{\\an5\\pos({x},{y}){anim}}}" + " ".join(parts)
                )

    for ov in edl["overlays"]:
        if ov["kind"] != "text":
            continue
        x, y = int(W * ov["x"]), int(H * ov["y"])
        tags = f"\\an5\\pos({x},{y})\\fs{ov['size']}\\c{ass_color(ov['color'])}"
        style = "Caption"
        if ov.get("background"):
            style = "Box"
            tags += f"\\3c{ass_color(ov['background'])}"
        if ov["animation"] == "pop":
            tags += "\\fscx60\\fscy60\\t(0,140,\\fscx100\\fscy100)\\fad(0,150)"
        elif ov["animation"] == "fade":
            tags += "\\fad(200,200)"
        lines.append(
            f"Dialogue: 2,{ass_time(ov['start'])},{ass_time(min(ov['end'], total))},{style},,0,0,0,,"
            f"{{{tags}}}{_escape(ov['text'])}"
        )
    return "\n".join(lines) + "\n"
