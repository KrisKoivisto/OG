import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ccpod import captions, cli, config, transcript as tx
from ccpod.ai import Chapter, ClipIdea, ClipPlan, EpisodeNotes, SfxCue
from ccpod.notes import clean_chapters, to_markdown

SRT = """1
00:00:00,000 --> 00:00:04,000
Kris: Welcome back to Color Commentary.

2
00:00:04,500 --> 00:00:09,000
JD: Man, it has been a long time.

3
00:00:09,200 --> 00:00:15,000
Big June: And I still think the Knicks are winning it all!
"""

VTT = """WEBVTT

NOTE riverside export

00:01.000 --> 00:03.500
<v Kris>First line here

1
00:03.600 --> 00:06.000
<v JD>Second line
"""


def test_parse_srt_speakers_and_words():
    segs = tx.parse_timed_text(SRT)
    assert [s.speaker for s in segs] == ["Kris", "JD", "Big June"]
    assert segs[2].text.startswith("And I still")
    w = segs[0].words
    assert w[0].start == 0 and abs(w[-1].end - 4.0) < 0.01
    assert all(a.end <= b.start + 1e-6 for a, b in zip(w, w[1:]))


def test_parse_vtt_short_timestamps():
    segs = tx.parse_timed_text(VTT)
    assert [(s.start, s.end, s.speaker, s.text) for s in segs] == [
        (1.0, 3.5, "Kris", "First line here"), (3.6, 6.0, "JD", "Second line")]


def test_snap_to_line_edges():
    segs = tx.parse_timed_text(SRT)
    s, e = tx.snap(segs, 5.3, 14.0)
    assert s == pytest.approx(4.35) and e == pytest.approx(15.25)


def test_chapters_follow_youtube_rules():
    ch = clean_chapters([Chapter(start=95, title="Knicks"), Chapter(start=3, title="Cold open"),
                         Chapter(start=100, title="dupe"), Chapter(start=600, title="Movies")])
    assert [(c.start, c.title) for c in ch] == [(0, "Cold open"), (95, "Knicks"), (600, "Movies")]
    ch = clean_chapters([Chapter(start=120, title="A")])
    assert ch[0].start == 0 and ch[0].title == "Intro"


def test_notes_markdown_has_chapters_and_footer():
    cfg = config.load()
    md = to_markdown(EpisodeNotes(title_options=["t1"], summary="We back.", chapters=[
        Chapter(start=0, title="Intro"), Chapter(start=60, title="Hoops"), Chapter(start=900, title="Movies")],
        mentions=["Knicks"], pull_quotes=["\"We back\" - Kris"]), cfg, "S2E1")
    assert "00:00 Intro\n01:00 Hoops\n15:00 Movies" in md
    assert "podcasts.apple.com" in md


def test_ass_highlights_one_word_at_a_time():
    words = [tx.Word(0, .4, "we"), tx.Word(.4, .8, "back"), tx.Word(.8, 1.2, "baby")]
    ass = captions.build_ass(words, 2.0, "We're back", config.DEFAULTS["brand"])
    caps = [l for l in ass.splitlines() if l.startswith("Dialogue: 0")]
    assert len(caps) == 3
    assert "Hook,,0,0,0,,WE'RE BACK" in ass
    assert captions.ass_color("#F5C400") == "&H0000C4F5"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
@pytest.mark.parametrize("layout", ["blur", "crop"])
def test_end_to_end_render(tmp_path, monkeypatch, layout):
    video = tmp_path / "ep.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=16",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=16", "-shortest",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(video)], check=True)
    srt = tmp_path / "ep.srt"
    srt.write_text(SRT)
    root = tmp_path / "show"
    (root / "sfx").mkdir(parents=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.5",
                    str(root / "sfx" / "airhorn.wav")], check=True)
    shutil.copy(Path(config.ROOT) / "show.toml", root / "show.toml")
    (root / "show.toml").write_text((root / "show.toml").read_text().replace('layout = "blur"', f'layout = "{layout}"'))

    def fake_plan(cfg, segs):
        return ClipPlan(clips=[ClipIdea(start=4.6, end=14.8, hook="June has a Knicks take", title="t",
                                        description="d", hashtags=["#shorts"], why="w",
                                        sfx=[SfxCue(at=6.0, name="airhorn"), SfxCue(at=1, name="not-installed")])])
    monkeypatch.setattr("ccpod.ai.plan_clips", fake_plan)
    out = tmp_path / "out"
    cli.main(["--config", str(root / "show.toml"), "--out", str(out), "--episode", "S2E1", "clips", str(video), str(srt)])
    plan = json.loads((out / "s2e1" / "plan.json").read_text())
    assert plan["clips"][0]["start"] == pytest.approx(4.35)
    cli.main(["--config", str(root / "show.toml"), "--out", str(out), "render", str(out / "s2e1" / "plan.json")])
    mp4 = next((out / "s2e1").glob("short-01-*.mp4"))
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                            "-of", "json", str(mp4)], capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert abs(float(info["format"]["duration"]) - (15.25 - 4.35)) < 0.3
    assert (out / "s2e1" / "uploads.md").exists()
