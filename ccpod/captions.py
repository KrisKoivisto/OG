"""Burned-in captions and the hook title, written as an ASS subtitle file for ffmpeg/libass."""
from __future__ import annotations

from .transcript import Word

W, H = 1080, 1920


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_text(s: str) -> str:
    return s.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def chunk_words(words: list[Word], n: int) -> list[list[Word]]:
    """Groups of up to n words, breaking early after sentence punctuation or a long pause."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        pause = nxt is not None and nxt.start - w.end > 0.6
        if len(cur) >= n or w.text[-1:] in ".?!," or pause or nxt is None:
            chunks.append(cur)
            cur = []
    return chunks


def build_ass(words: list[Word], duration: float, hook: str, brand: dict, layout: str = "blur") -> str:
    font = brand.get("font", "Arial Black")
    text_c, accent_c = ass_color(brand["text"]), ass_color(brand["accent"])
    outline_c = ass_color(brand["outline"])
    hook_bg, hook_tx = ass_color(brand["hook_bg"]), ass_color(brand["hook_text"])
    cap_margin = 470 if layout == "blur" else 560
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},84,{text_c},{text_c},{outline_c},&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,{cap_margin},1
Style: Hook,{font},64,{hook_tx},{hook_tx},{hook_bg},{hook_bg},-1,0,0,0,100,100,0,0,3,22,0,8,90,90,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    if hook.strip():
        events.append(f"Dialogue: 1,{ass_time(0)},{ass_time(duration)},Hook,,0,0,0,,{ass_text(hook.strip().upper())}")
    chunks = chunk_words(words, int(brand.get("caption_words", 3)))
    for ci, chunk in enumerate(chunks):
        nxt_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else duration
        chunk_end = chunk[-1].end
        if nxt_start - chunk_end < 0.35:          # no flicker between back-to-back chunks
            chunk_end = nxt_start
        for wi, w in enumerate(chunk):
            start = w.start if wi else chunk[0].start
            end = chunk[wi + 1].start if wi + 1 < len(chunk) else chunk_end
            if end <= start:
                continue
            parts = []
            for k, x in enumerate(chunk):
                t = ass_text(x.text.upper())
                parts.append(f"{{\\c{accent_c}}}{t}{{\\c{text_c}}}" if k == wi else t)
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(min(end, duration))},Cap,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(events) + "\n"
