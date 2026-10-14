"""Cut one vertical Short with ffmpeg: 9:16 frame, captions, hook title, sound effects, loudness."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import captions
from . import config as cfgmod
from .transcript import Segment, words_between


def video_filter(layout: str, focus: float) -> str:
    if layout == "crop":
        f = min(max(focus, 0.0), 1.0)
        return (f"[0:v]crop=w='min(iw,ih*9/16)':h=ih:x='(iw-ow)*{f}':y=0,"
                f"scale={captions.W}:{captions.H},setsar=1[base]")
    return (f"[0:v]split=2[bg][fg];"
            f"[bg]scale={captions.W}:{captions.H}:force_original_aspect_ratio=increase,"
            f"crop={captions.W}:{captions.H},gblur=sigma=40,eq=brightness=-0.12[bgb];"
            f"[fg]scale={captions.W}:-2[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[base]")


def build_command(video: Path, start: float, end: float, out: Path, clip: dict, cfg: dict,
                  sfx_files: list[tuple[float, Path]], logo: Path | None, has_fonts: bool) -> list[str]:
    r = cfg["render"]
    layout = clip.get("layout") or r["layout"]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(video)]
    for _, f in sfx_files:
        cmd += ["-i", str(f)]
    if logo:
        cmd += ["-i", str(logo)]

    fontsdir = ":fontsdir=fonts" if has_fonts else ""
    graph = [video_filter(layout, float(clip.get("focus", 0.5)))]
    graph.append(f"[base]ass=captions.ass{fontsdir}[cap]")
    if logo:
        li = 1 + len(sfx_files)
        graph.append(f"[{li}:v]scale=180:-1[lg];[cap][lg]overlay=(W-w)/2:H-h-150[v]")
    else:
        graph.append("[cap]null[v]")

    vol = float(r.get("sfx_volume", 0.8))
    mix = ["[a0]"]
    graph.append("[0:a]aresample=48000[a0]")
    for i, (at, _) in enumerate(sfx_files, start=1):
        ms = int(max(0.0, at) * 1000)
        graph.append(f"[{i}:a]aresample=48000,adelay=delays={ms}:all=1,volume={vol}[s{i}]")
        mix.append(f"[s{i}]")
    lufs = float(r.get("loudness", -14))
    if len(mix) > 1:
        graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                     f"loudnorm=I={lufs}:TP=-1.5:LRA=11[a]")
    else:
        graph.append(f"[a0]loudnorm=I={lufs}:TP=-1.5:LRA=11[a]")

    cmd += ["-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(r.get("crf", 20)), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out.resolve())]
    return cmd


def render_clip(video: Path, segs: list[Segment], clip: dict, out: Path, cfg: dict) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg isn't installed. Mac: brew install ffmpeg. Windows: winget install ffmpeg")
    start, end = float(clip["start"]), float(clip["end"])
    if end <= start:
        raise ValueError(f"clip {clip.get('n')}: end is before start")
    if end - start > 180:
        raise ValueError(f"clip {clip.get('n')}: {end - start:.0f}s is over YouTube's 3 minute Shorts limit")
    lib = cfgmod.sfx_library(cfg)
    sfx_files = [(float(s["at"]), lib[s["name"]]) for s in clip.get("sfx", []) if s.get("name") in lib]
    logo_cfg = cfg["brand"].get("logo") or ""
    logo = (Path(cfg["_root"]) / logo_cfg) if logo_cfg else None
    if logo and not logo.exists():
        logo = None
    fonts = cfgmod.fonts_dir(cfg)

    layout = clip.get("layout") or cfg["render"]["layout"]
    words = words_between(segs, start, end)
    ass = captions.build_ass(words, end - start, clip.get("hook", ""), cfg["brand"], layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # ffmpeg runs inside the temp folder so the subtitle path needs no escaping on any OS.
        (Path(tmp) / "captions.ass").write_text(ass, encoding="utf-8")
        if fonts:
            shutil.copytree(fonts, Path(tmp) / "fonts")
        cmd = build_command(video.resolve(), start, end, out, clip, cfg, sfx_files, logo.resolve() if logo else None, bool(fonts))
        res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg failed on clip {clip.get('n')}:\n{res.stderr[-2000:]}")
    return out
