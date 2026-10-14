from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "show": {"name": "Color Commentary", "hosts": [], "formerly": "", "footer": ""},
    "clips": {"count": 8, "min_seconds": 20, "max_seconds": 75, "model": "claude-opus-5-5"},
    "brand": {
        "accent": "#F5C400", "text": "#FFFFFF", "outline": "#000000",
        "hook_bg": "#D9232D", "hook_text": "#FFFFFF", "font": "Arial Black",
        "caption_words": 3, "logo": "",
    },
    "render": {"layout": "blur", "loudness": -14, "sfx_volume": 0.8, "crf": 20},
}


def load(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "show.toml"
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    if p.exists():
        with open(p, "rb") as f:
            for section, values in tomllib.load(f).items():
                cfg.setdefault(section, {}).update(values)
    cfg["_root"] = p.parent
    return cfg


def voice(cfg: dict) -> str:
    p = Path(cfg["_root"]) / "voice.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def sfx_library(cfg: dict) -> dict[str, Path]:
    d = Path(cfg["_root"]) / "sfx"
    exts = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
    return {f.stem: f for f in sorted(d.glob("*")) if f.suffix.lower() in exts} if d.exists() else {}


def fonts_dir(cfg: dict) -> Path | None:
    d = Path(cfg["_root"]) / "fonts"
    return d if d.exists() and any(f.suffix.lower() in {".ttf", ".otf"} for f in d.iterdir()) else None
