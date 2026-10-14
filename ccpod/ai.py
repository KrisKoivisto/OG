"""The Claude part: pick Short-worthy moments and write show notes from the transcript."""
from __future__ import annotations

import anthropic
from pydantic import BaseModel

from . import config as cfgmod
from .transcript import Segment, for_prompt


class SfxCue(BaseModel):
    at: float          # seconds from the start of the clip
    name: str          # filename stem from sfx/


class ClipIdea(BaseModel):
    start: float       # seconds into the episode
    end: float
    hook: str          # big on-screen title, 7 words max
    title: str         # YouTube Shorts title
    description: str
    hashtags: list[str]
    why: str           # one line on why this one hits
    sfx: list[SfxCue]


class ClipPlan(BaseModel):
    clips: list[ClipIdea]


class Chapter(BaseModel):
    start: float
    title: str


class EpisodeNotes(BaseModel):
    title_options: list[str]
    summary: str
    chapters: list[Chapter]
    mentions: list[str]
    pull_quotes: list[str]


def _system(cfg: dict) -> str:
    show = cfg["show"]
    hosts = ", ".join(show.get("hosts") or [])
    formerly = f" (formerly {show['formerly']})" if show.get("formerly") else ""
    return (
        f"You produce {show['name']}{formerly}, a sports and culture podcast with {hosts}. "
        "Full episodes run about an hour of the hosts talking. Almost nobody watches the full "
        "episode on YouTube, but the Shorts do numbers, so your clip picks matter most.\n\n"
        "Write everything in the hosts' voice, following this guide exactly:\n\n"
        + cfgmod.voice(cfg)
    )


def _call(cfg: dict, segs: list[Segment], task: str, schema: type[BaseModel]) -> BaseModel:
    client = anthropic.Anthropic()
    content = [
        # The transcript is the big, unchanging part, so it is cached: re-rolling clips
        # within a few minutes reads it from cache instead of paying for it again.
        {"type": "text", "text": "<transcript>\n" + for_prompt(segs) + "\n</transcript>",
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": task},
    ]
    with client.messages.stream(
        model=cfg["clips"]["model"],
        max_tokens=32000,
        system=_system(cfg),
        messages=[{"role": "user", "content": content}],
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        output_format=schema,
        # If a safety filter ever declines (rare for sports talk), the API retries on a
        # fallback model instead of returning nothing.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("Claude declined this transcript. Try again, or trim the part it flagged.")
    if msg.stop_reason == "max_tokens" or msg.parsed_output is None:
        raise RuntimeError("Claude's answer got cut off. Run it again.")
    return msg.parsed_output


def plan_clips(cfg: dict, segs: list[Segment]) -> ClipPlan:
    c = cfg["clips"]
    sfx = sorted(cfgmod.sfx_library(cfg))
    sfx_line = (
        "Sound effects available (use the exact names, 0-2 per clip, only where a real editor would "
        f"put one, like right after a punchline): {', '.join(sfx)}." if sfx else
        "No sound effects are installed, so leave sfx empty."
    )
    task = "\n\n".join(x for x in [
        f"Pick the {c['count']} best moments for YouTube Shorts. Each clip runs {c['min_seconds']}-"
        f"{c['max_seconds']} seconds and has to work with zero context: a strong first line in the first "
        "two seconds, one idea, and a clean ending (a punchline, a reaction, a hot take landing). "
        "Arguments, wild takes, funny stories, and anything that makes people want to comment are gold. "
        "Use the transcript's second timestamps for start and end, starting at the beginning of a line.",
        "For each clip: hook is the big text on screen for the whole Short, 7 words max, no hashtags. "
        "title is the YouTube title, under 70 characters, written to get the click without lying. "
        "description is 1-2 short sentences. hashtags: up to 3, include #shorts. "
        "why: one line on why it'll hit. " + sfx_line + " sfx.at is seconds from the clip's start.",
        "Order clips best first.",
    ] if x)
    plan = _call(cfg, segs, task, ClipPlan)
    known = set(sfx)
    for clip in plan.clips:
        clip.sfx = [s for s in clip.sfx if s.name in known and 0 <= s.at <= clip.end - clip.start]
    return plan


def write_notes(cfg: dict, segs: list[Segment]) -> EpisodeNotes:
    task = "\n\n".join(x for x in [
        "Write the show notes for this episode.",
        "title_options: 5 episode titles. summary: 2-4 sentences for YouTube and Apple Podcasts, "
        "in the hosts' voice, naming the actual topics. chapters: one per real topic change, start in "
        "seconds, short titles, first chapter at 0, at least 3, none shorter than 10 seconds. "
        "mentions: specific people, teams, shows, songs, articles, or links they referenced, so the "
        "hosts can add links. pull_quotes: 3-5 quotable lines, word for word from the transcript, with "
        "who said it if known.",
    ] if x)
    return _call(cfg, segs, task, EpisodeNotes)
