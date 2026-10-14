"""Turn Claude's notes into paste-ready text. YouTube's chapter rules are enforced here in
code, not left to the model: first chapter at 00:00, at least 3, ascending, 10s minimum."""
from __future__ import annotations

from .ai import Chapter, EpisodeNotes
from .transcript import fmt_ts


def clean_chapters(chapters: list[Chapter], min_gap: float = 10) -> list[Chapter]:
    out: list[Chapter] = []
    for ch in sorted(chapters, key=lambda c: c.start):
        t = max(0.0, float(int(ch.start)))
        if out and t - out[-1].start < min_gap:
            continue
        out.append(Chapter(start=t, title=ch.title.strip()))
    if out and out[0].start < min_gap:
        out[0] = Chapter(start=0, title=out[0].title)
    else:
        out.insert(0, Chapter(start=0, title="Intro"))
    return out


def chapters_text(chapters: list[Chapter]) -> str:
    return "\n".join(f"{fmt_ts(c.start)} {c.title}" for c in chapters)


def to_markdown(notes: EpisodeNotes, cfg: dict, episode_label: str = "") -> str:
    chapters = clean_chapters(notes.chapters)
    ch_txt = chapters_text(chapters)
    footer = (cfg["show"].get("footer") or "").strip()
    yt = "\n\n".join(x for x in [notes.summary.strip(), ch_txt, footer] if x)
    apple = notes.summary.strip()
    warn = "" if len(chapters) >= 3 else "\n> YouTube needs at least 3 chapters to show them. Add one or two by hand.\n"
    lines = [
        f"# {cfg['show']['name']} {episode_label}".rstrip(),
        "",
        "## Title options",
        *[f"- {t}" for t in notes.title_options],
        "",
        "## YouTube description (paste as is)",
        "```",
        yt,
        "```",
        warn,
        "## Apple Podcasts description",
        "```",
        apple,
        "```",
        "",
        "## Stuff we mentioned (add links)",
        *[f"- {m}" for m in notes.mentions],
        "",
        "## Pull quotes",
        *[f"> {q}\n" for q in notes.pull_quotes],
    ]
    return "\n".join(lines).replace("\n\n\n", "\n\n") + "\n"
