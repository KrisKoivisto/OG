# Color Commentary toolkit

Two pieces:

1. **Topic list.** One shared list for show notes that works on Android, iPhone, and laptops: https://claude.ai/artifact/KGEf7FthrTMpo3w59qvEFd
   Share it with JD and June by email as **Editors** (Share button on the page). The source is in `rundown/`.
2. **`ccpod`.** Takes the Riverside recording and gives you vertical Shorts with captions, a hook title, and sound effects, plus show notes, titles, and YouTube chapters.

## What ccpod does

```
Riverside export (video + SRT transcript)
        │
        ▼
ccpod go episode.mp4 episode.srt --episode S2E1
        │
        ├── out/s2e1/notes.md      titles, YouTube description with chapters, Apple description, pull quotes
        ├── out/s2e1/plan.json     the clips Claude picked: times, hook text, titles, sound effect cues
        ├── out/s2e1/short-01-….mp4 … short-08-….mp4   1080x1920, captions burned in, loudness set for Shorts
        └── out/s2e1/uploads.md    title + description + hashtags for each Short, ready to paste
```

Don't like a pick? Open `plan.json`, change the times, the hook, or the sound effects (or set `"skip": true`), then re-render just that one:

```
ccpod render out/s2e1/plan.json --only 3
```

## Setup (once, on the editing computer)

```
brew install ffmpeg            # Windows: winget install ffmpeg
pip install -e .
export ANTHROPIC_API_KEY=...   # from console.anthropic.com
```

In Riverside, export the full video and the transcript as **SRT**.

## Make it yours

- `show.toml`: colors, font, caption size, clip length, how many clips, the footer pasted under every description.
- `voice.md`: how the show sounds. Paste in your best Short titles and running jokes. This is what keeps the writing from sounding like a robot.
- `sfx/`: drop sound effects in (`airhorn.mp3`, `vine-boom.wav`…). Claude only cues sounds that are in this folder.
- `fonts/`: drop in your brand font if it isn't installed on the computer.
- Layout: `blur` keeps the whole Riverside frame and fills the top and bottom with a blurred copy. `crop` cuts a tight 9:16 strip; set `"focus"` in plan.json from 0 (left) to 1 (right) to aim it at whoever's talking.

## Optional

`ccpod transcribe episode.mp4` makes a transcript with exact word timings locally (`pip install -e '.[whisper]'`). Riverside's SRT works fine without it; captions are just timed a little more loosely.

## Tests

```
pip install -e '.[dev]' && pytest
```
