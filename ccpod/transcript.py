"""Load transcripts from Riverside exports (SRT / VTT) or ccpod's own whisper JSON.

Everything becomes a list of Segments. Each Segment carries word timings when we have
them (whisper) and estimated ones when we don't (SRT/VTT), so captions can always pop
word by word.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None
    words: list[Word] = field(default_factory=list)


_TS = r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})"
_CUE = re.compile(_TS + r"\s*-->\s*" + _TS)
_SPEAKER_PREFIX = re.compile(r"^\s*([A-Z][\w .'-]{0,30}?):\s+(.*)$", re.S)
_VTT_VOICE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")
_TAGS = re.compile(r"<[^>]+>")


def _secs(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_timed_text(text: str) -> list[Segment]:
    """Parse SRT or WebVTT. Cue numbers, WEBVTT headers, NOTE/STYLE blocks are skipped."""
    segs: list[Segment] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("﻿", "").strip())
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            m = _CUE.search(line)
            if not m:
                continue
            g = m.groups()
            start, end = _secs(*g[:4]), _secs(*g[4:])
            body = " ".join(lines[i + 1:]).strip()
            speaker = None
            v = _VTT_VOICE.search(body)
            if v:
                speaker = v.group(1).strip()
            body = _TAGS.sub("", body).strip()
            sp = _SPEAKER_PREFIX.match(body)
            if sp and not speaker:
                speaker, body = sp.group(1).strip(), sp.group(2).strip()
            if body:
                segs.append(Segment(start, end, body, speaker))
            break
    for s in segs:
        s.words = estimate_words(s)
    return segs


def estimate_words(seg: Segment) -> list[Word]:
    """Spread a segment's duration across its words, weighted by word length."""
    toks = seg.text.split()
    if not toks:
        return []
    weights = [len(t) + 2 for t in toks]
    total = sum(weights)
    span = max(seg.end - seg.start, 0.01)
    out, t = [], seg.start
    for tok, w in zip(toks, weights):
        d = span * w / total
        out.append(Word(round(t, 3), round(t + d, 3), tok))
        t += d
    return out


def load_whisper_json(data: dict) -> list[Segment]:
    segs = []
    for s in data.get("segments", []):
        words = [Word(w["start"], w["end"], w["text"].strip()) for w in s.get("words", []) if w.get("text", "").strip()]
        seg = Segment(s["start"], s["end"], s["text"].strip(), s.get("speaker"), words)
        if not seg.words:
            seg.words = estimate_words(seg)
        segs.append(seg)
    return segs


def load(path: str | Path) -> list[Segment]:
    p = Path(path)
    raw = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() == ".json":
        return load_whisper_json(json.loads(raw))
    segs = parse_timed_text(raw)
    if not segs:
        raise ValueError(f"{p.name}: no timed lines found. Export the transcript from Riverside as SRT or VTT.")
    return segs


def fmt_ts(sec: float) -> str:
    sec = max(0, int(sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def for_prompt(segs: list[Segment]) -> str:
    """Compact transcript for Claude: one line per segment, start time in seconds."""
    lines = []
    for s in segs:
        who = f"{s.speaker}: " if s.speaker else ""
        lines.append(f"[{s.start:.1f}] {who}{s.text}")
    return "\n".join(lines)


def words_between(segs: list[Segment], start: float, end: float) -> list[Word]:
    """Words inside [start, end], re-timed so the clip starts at 0."""
    out = []
    for s in segs:
        if s.end < start or s.start > end:
            continue
        for w in s.words:
            mid = (w.start + w.end) / 2
            if start <= mid <= end:
                out.append(Word(max(0.0, w.start - start), min(end, w.end) - start, w.text))
    return out


def snap(segs: list[Segment], start: float, end: float) -> tuple[float, float]:
    """Pull clip edges to sentence boundaries so nobody gets cut off mid-word."""
    starts = [s.start for s in segs]
    ends = [s.end for s in segs]
    if not segs:
        return start, end
    # nearest segment start at or before start (within 3s), else nearest overall
    before = [t for t in starts if start - 3 <= t <= start + 0.5]
    new_start = max(before) if before else min(starts, key=lambda t: abs(t - start))
    after = [t for t in ends if end - 0.5 <= t <= end + 3]
    new_end = min(after) if after else min(ends, key=lambda t: abs(t - end))
    if new_end <= new_start:
        return start, end
    return round(max(0.0, new_start - 0.15), 2), round(new_end + 0.25, 2)
