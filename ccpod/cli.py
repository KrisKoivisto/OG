"""ccpod: Color Commentary post-production.

  ccpod go EPISODE.mp4 TRANSCRIPT.srt      notes + clip picks + render, all in one
  ccpod notes TRANSCRIPT.srt               show notes, titles, chapters
  ccpod clips EPISODE.mp4 TRANSCRIPT.srt   pick Shorts, write plan.json (no rendering)
  ccpod render plan.json [--only 2,5]      render (or re-render) Shorts from plan.json
  ccpod transcribe EPISODE.mp4             make a word-timed transcript locally (optional)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import config as cfgmod
from . import transcript as tx


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "clip"


def _outdir(args, video_or_tx: str) -> Path:
    name = args.episode or Path(video_or_tx).stem
    return Path(args.out) / _slug(name)


def cmd_notes(args, cfg) -> Path:
    from .ai import write_notes
    from .notes import to_markdown
    segs = tx.load(args.transcript)
    print("Writing show notes…", file=sys.stderr)
    notes = write_notes(cfg, segs)
    out = _outdir(args, args.video or args.transcript) / "notes.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(notes, cfg, args.episode or ""), encoding="utf-8")
    print(f"Show notes: {out}")
    return out


def cmd_clips(args, cfg) -> Path:
    from .ai import plan_clips
    segs = tx.load(args.transcript)
    print("Picking Shorts…", file=sys.stderr)
    plan = plan_clips(cfg, segs)
    clips = []
    for n, c in enumerate(plan.clips, start=1):
        start, end = tx.snap(segs, c.start, c.end)
        clips.append({"n": n, "start": start, "end": end, "hook": c.hook, "title": c.title,
                      "description": c.description, "hashtags": c.hashtags, "why": c.why,
                      "sfx": [s.model_dump() for s in c.sfx], "layout": cfg["render"]["layout"],
                      "focus": 0.5, "skip": False})
    out_dir = _outdir(args, args.video or args.transcript)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.json"
    plan_path.write_text(json.dumps({
        "episode": args.episode or Path(args.video).stem,
        "video": str(Path(args.video).resolve()),
        "transcript": str(Path(args.transcript).resolve()),
        "clips": clips,
    }, indent=2), encoding="utf-8")
    for c in clips:
        print(f"  {c['n']:>2}. {tx.fmt_ts(c['start'])}-{tx.fmt_ts(c['end'])}  {c['hook']}  ({c['why']})")
    print(f"Plan: {plan_path}  (edit times, hooks, sfx, or set \"skip\": true, then ccpod render)")
    return plan_path


def cmd_render(args, cfg) -> None:
    from .render import render_clip
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    video = Path(args.video or plan["video"])
    segs = tx.load(args.transcript or plan["transcript"])
    only = {int(x) for x in args.only.split(",")} if args.only else None
    lines = []
    for c in plan["clips"]:
        if c.get("skip") or (only and c["n"] not in only):
            continue
        out = plan_path.parent / f"short-{c['n']:02d}-{_slug(c['hook'])}.mp4"
        print(f"Rendering {out.name}…", file=sys.stderr)
        render_clip(video, segs, c, out, cfg)
        tags = " ".join(c.get("hashtags", []))
        lines += [f"## {out.name}", "", f"**Title:** {c['title']}", "", f"{c['description']}", "", tags, ""]
    if lines:
        up = plan_path.parent / "uploads.md"
        up.write_text("# Ready to upload\n\n" + "\n".join(lines), encoding="utf-8")
        print(f"Done. Titles and descriptions: {up}")


def cmd_go(args, cfg) -> None:
    cmd_notes(args, cfg)
    args.plan = str(cmd_clips(args, cfg))
    args.only = None
    cmd_render(args, cfg)


def cmd_transcribe(args, cfg) -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("Local transcription needs: pip install 'ccpod[whisper]'  (or just export the transcript from Riverside as SRT)")
    model = WhisperModel(args.model, device="auto", compute_type="auto")
    segments, _ = model.transcribe(args.video, word_timestamps=True, vad_filter=True)
    data = {"segments": []}
    for s in segments:
        data["segments"].append({"start": s.start, "end": s.end, "text": s.text.strip(),
                                 "words": [{"start": w.start, "end": w.end, "text": w.word} for w in (s.words or [])]})
        print(f"[{tx.fmt_ts(s.start)}] {s.text.strip()}", file=sys.stderr)
    out = Path(args.video).with_suffix(".transcript.json")
    out.write_text(json.dumps(data), encoding="utf-8")
    print(f"Transcript: {out}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="ccpod", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="path to show.toml")
    p.add_argument("--out", default="out", help="output folder (default: out)")
    p.add_argument("--episode", help="episode name for folders and notes, e.g. S2E1")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("go"); s.add_argument("video"); s.add_argument("transcript"); s.set_defaults(fn=cmd_go)
    s = sub.add_parser("notes"); s.add_argument("transcript"); s.set_defaults(fn=cmd_notes)
    s = sub.add_parser("clips"); s.add_argument("video"); s.add_argument("transcript"); s.set_defaults(fn=cmd_clips)
    s = sub.add_parser("render"); s.add_argument("plan"); s.add_argument("--only"); s.add_argument("--video"); s.add_argument("--transcript"); s.set_defaults(fn=cmd_render)
    s = sub.add_parser("transcribe"); s.add_argument("video"); s.add_argument("--model", default="large-v3"); s.set_defaults(fn=cmd_transcribe)

    args = p.parse_args(argv)
    for k in ("video", "transcript"):
        if not hasattr(args, k):
            setattr(args, k, None)
    cfg = cfgmod.load(args.config)
    try:
        args.fn(args, cfg)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
