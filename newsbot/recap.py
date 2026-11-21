"""
Recaps (update 8):
  * Daily reel   - a ~22 second 9:16 video of the day's top 5 stories, with original
                   background music, for Instagram Reels, Facebook Reels and Telegram.
  * Weekly recap - "The Week In Markets": a 10-card carousel every Sunday.

Pure helpers here (picking stories, drawing frames, making the video).
bot.py does the uploading.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import config
import images

ASSETS = Path(__file__).resolve().parent / "assets"
MUSIC_DIR = ASSETS / "music"
RW, RH = 1080, 1920          # 9:16 reel


# ----------------------------------------------------------------------------
# Picking the biggest stories
# ----------------------------------------------------------------------------
def log_item(p: dict, story: dict, now: float) -> dict:
    """What we remember about each posted headline (for the daily reel / weekly recap)."""
    return {"ts": now, "headline": p["headline"], "credit": p["credit_main"],
            "story_id": story.get("story_id", ""), "priority": story["priority"],
            "focus": bool(story.get("focus")), "breaking": bool(story.get("breaking")),
            "n_sources": len(story.get("sources", [])), "summary": story.get("summary", "")[:600],
            "countries": story.get("countries", []), "sources": story.get("sources", [])[:3],
            "story": {k: story.get(k) for k in ("priority", "countries", "followup", "is_price")}}


def top_stories(log: list[dict], since: float, until: float, n: int) -> list[dict]:
    """Biggest first: breaking > markets > geopolitics > more sources > US/India; one per story."""
    pool = [x for x in log if since <= x["ts"] < until]
    latest: dict[str, dict] = {}
    for x in sorted(pool, key=lambda x: x["ts"]):
        key = x.get("story_id") or x["headline"]
        prev = latest.get(key)
        # keep the newest wording, but remember if any version was breaking
        latest[key] = {**x, "breaking": x["breaking"] or bool(prev and prev["breaking"])}
    ranked = sorted(latest.values(), key=lambda x: (x["breaking"], x["priority"], x["n_sources"],
                                                    x["focus"], x["ts"]), reverse=True)
    return ranked[:n]


# ----------------------------------------------------------------------------
# Reel frames (1080x1920)
# ----------------------------------------------------------------------------
def _fonts():
    from PIL import ImageFont
    bold, medium = str(ASSETS / "Poppins-Bold.ttf"), str(ASSETS / "Poppins-Medium.ttf")
    return (lambda s: ImageFont.truetype(bold, s)), (lambda s: ImageFont.truetype(medium, s))


def _canvas(label: str = "MARKETS", seed: str = ""):
    from PIL import ImageDraw
    img = images.background(RW, RH, label, seed)
    return img, ImageDraw.Draw(img, "RGBA")


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _centered(d, y, text, font, fill):
    d.text(((RW - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)


def _logo(size: int):
    from PIL import Image, ImageDraw
    p = ASSETS / "logo.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGB").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    return im, mask


def frame_intro(title: str, subtitle: str, pill: str) -> bytes:
    img, d = _canvas()
    B, M = _fonts()
    lg = _logo(220)
    if lg:
        img.paste(lg[0], ((RW - 220) // 2, 430), lg[1])
    f_pill = B(34)
    tw = d.textlength(pill, font=f_pill)
    x = (RW - tw - 56) / 2
    d.rounded_rectangle([x, 720, x + tw + 56, 790], radius=35, fill=config.CARD_ACCENT_MARKETS)
    d.text((x + 28, 731), pill, font=f_pill, fill=(0, 0, 0))
    y = 840
    for line in title.split("\n"):
        _centered(d, y, line, B(104), config.CARD_TEXT)
        y += 124
    _centered(d, y + 20, subtitle, M(42), (150, 150, 150))
    _centered(d, RH - 300, config.BRAND_NAME.upper(), M(36), config.CARD_TEXT)
    return _png(img)


def frame_story(item: dict, idx: int, total: int, label: str) -> bytes:
    from PIL import ImageDraw
    B, M = _fonts()
    when = datetime.fromtimestamp(item["ts"], _tz())
    top = (RH - images.H) // 2 - 40
    img = images.render_image(item["story"], item["headline"], item["credit"], when, height=RH, top_pad=top)
    d = ImageDraw.Draw(img, "RGBA")
    # header: "TOP 5 TODAY" + counter, progress bar
    f = B(40)
    d.text((images.MARGIN, top - 150), label, font=f, fill=config.CARD_ACCENT_MARKETS)
    cnt = f"{idx}/{total}"
    d.text((RW - images.MARGIN - d.textlength(cnt, font=f), top - 150), cnt, font=f, fill=config.CARD_TEXT)
    bar_y, bw = top - 80, RW - 2 * images.MARGIN
    d.rounded_rectangle([images.MARGIN, bar_y, images.MARGIN + bw, bar_y + 8], radius=4, fill=(255, 255, 255, 50))
    d.rounded_rectangle([images.MARGIN, bar_y, images.MARGIN + bw * idx / total, bar_y + 8], radius=4,
                        fill=config.CARD_ACCENT_MARKETS)
    return _png(img)


def frame_outro() -> bytes:
    """End card (update 18): Like / Follow / Subscribe call to action."""
    img, d = _canvas()
    B, M = _fonts()
    lg = _logo(220)
    if lg:
        img.paste(lg[0], ((RW - 220) // 2, 300), lg[1])
    _centered(d, 580, "Enjoyed the update?", B(70), config.CARD_TEXT)
    rows = [("LIKE", (255, 92, 122), "this video"),
            ("FOLLOW", config.CARD_ACCENT_MARKETS, "us on Instagram & Facebook"),
            ("SUBSCRIBE", (255, 70, 70), "on YouTube")]
    f_pill, f_txt = B(46), M(42)
    y = 760
    for word, colour, rest in rows:
        pw = d.textlength(word, font=f_pill) + 64
        tw = d.textlength(rest, font=f_txt)
        x = (RW - (pw + 28 + tw)) // 2
        d.rounded_rectangle([x, y, x + pw, y + 86], radius=43, fill=colour)
        d.text((x + 32, y + 14), word, font=f_pill, fill=(0, 0, 0))
        d.text((x + pw + 28, y + 20), rest, font=f_txt, fill=config.CARD_TEXT)
        y += 130
    _centered(d, y + 50, config.BRAND_HANDLE, B(60), config.CARD_ACCENT_MARKETS)
    _centered(d, y + 140, "Also on Telegram · Threads · X", M(34), (170, 170, 170))
    _centered(d, RH - 300, "Automated headline alerts. Not financial advice.", M(30), (130, 130, 130))
    return _png(img)


def _tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo(config.DIGEST_TIMEZONE)


# ----------------------------------------------------------------------------
# Video (ffmpeg)
# ----------------------------------------------------------------------------
def ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg          # small pip package with its own ffmpeg (installed by the workflow)
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return shutil.which("ffmpeg")


def pick_track(day: datetime, hourly: bool = False) -> Path | None:
    tracks = sorted(MUSIC_DIR.glob("*.m4a")) + sorted(MUSIC_DIR.glob("*.mp3"))
    if not tracks:
        return None
    n = day.toordinal() * 24 + day.hour if hourly else day.toordinal()
    return tracks[n % len(tracks)]


def make_video(frames: list[tuple[bytes, float]], music: Path | None) -> bytes:
    """frames = [(png, seconds)], cross-faded; music faded in/out under it. Returns MP4 bytes."""
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg not available")
    fade = config.REEL_FADE_SECONDS
    with tempfile.TemporaryDirectory() as tmp:
        args = [exe, "-y", "-loglevel", "error"]
        for i, (png, secs) in enumerate(frames):
            p = Path(tmp) / f"f{i}.png"
            p.write_bytes(png)
            args += ["-loop", "1", "-framerate", "30", "-t", f"{secs:.2f}", "-i", str(p)]
        total = sum(s for _, s in frames) - fade * (len(frames) - 1)
        if music:
            args += ["-stream_loop", "-1", "-i", str(music)]
        chain, last, offset = [], "[0:v]", 0.0
        for i in range(1, len(frames)):
            offset += frames[i - 1][1] - fade
            out = f"[v{i}]"
            chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.2f}{out}")
            last = out
        chain.append(f"{last}format=yuv420p,setsar=1[vout]")
        if music:
            a = len(frames)
            chain.append(f"[{a}:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.8,afade=t=out:st={max(total - 2.0, 0):.2f}:d=2.0,"
                         f"volume={config.REEL_MUSIC_VOLUME}[aout]")
        args += ["-filter_complex", ";".join(chain), "-map", "[vout]"]
        if music:
            args += ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
        out = Path(tmp) / "reel.mp4"
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", "30", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", "-t", f"{total:.2f}", str(out)]
        r = subprocess.run(args, capture_output=True, text=True, timeout=240)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"ffmpeg failed: {r.stderr[-300:]}")
        return out.read_bytes()


def build_reel(top: list[dict], day: datetime) -> dict:
    n = len(top)
    frames = [(frame_intro(f"Top {n} Stories\nToday", day.strftime("%A, %d %B %Y"), "DAILY RECAP"),
               config.REEL_INTRO_SECONDS)]
    for i, item in enumerate(top, 1):
        frames.append((frame_story(item, i, n, f"TOP {n} TODAY"), config.REEL_STORY_SECONDS))
    frames.append((frame_outro(), config.REEL_OUTRO_SECONDS))
    video = make_video(frames, pick_track(day))
    lines = [f"{i}. {x['headline']}" + (f" – {x['credit']}" if x["credit"] else "") for i, x in enumerate(top, 1)]
    caption = (f"📰 Today's top {n} stories ({day:%d %b})\n\n" + "\n".join(lines)
               + "\n\n❤️ Like · ➕ Follow · 🔔 Subscribe " + config.BRAND_HANDLE
               + " for markets & world news before the noise.\n"
               + " ".join(config.REEL_HASHTAGS) + "\nAutomated headline alerts. Not financial advice.")
    return {"video": video, "caption": caption[:2150], "count": n,
            "title": f"Today's Top {n} Market & World Stories – {day:%d %b %Y}"}


def build_hour_reel(items: list[dict], window: str, when: datetime) -> dict:
    """update 16: 'Top N this hour' reel from roundup items (biggest first)."""
    top = sorted(items, key=lambda q: (q["priority"], q.get("focus", False), q["ts"]),
                 reverse=True)[: config.HOURLY_REEL_STORIES]
    n = len(top)
    frames = [(frame_intro(f"Top {n}\nThis Hour", window, "MARKETS & WORLD"), config.REEL_INTRO_SECONDS)]
    for i, item in enumerate(top, 1):
        frames.append((frame_story(item, i, n, f"TOP {n} THIS HOUR"), config.HOURLY_REEL_STORY_SECONDS))
    frames.append((frame_outro(), config.REEL_OUTRO_SECONDS))
    video = make_video(frames, pick_track(when, hourly=True))
    plain = [q.get("plain") or q["headline"] for q in top]
    lines = [f"{i}. {h}" for i, h in enumerate(plain, 1)]
    caption = (f"🎬 Top {n} stories ({window})\n\n" + "\n".join(lines)
               + "\n\n❤️ Like · ➕ Follow · 🔔 Subscribe " + config.BRAND_HANDLE
               + " for markets & world news before the noise.\n"
               + " ".join(config.REEL_HASHTAGS) + "\nAutomated headline alerts. Not financial advice.")
    lead = top[0]["headline"].strip()
    title = lead if len(lead) <= 88 else lead[:85].rsplit(" ", 1)[0] + "…"
    return {"video": video, "caption": caption[:2150], "count": n, "title": title,
            "keys": [q["headline"] for q in top]}


# ----------------------------------------------------------------------------
# Weekly recap carousel
# ----------------------------------------------------------------------------
def build_weekly(top: list[dict], start: datetime, end: datetime) -> dict:
    slides = [images.render(x["story"], x["headline"], x["credit"], datetime.fromtimestamp(x["ts"], _tz()))
              for x in top]
    span = f"{start:%d %b}–{end:%d %b}"
    lines = [f"{i}. {x['headline']}" for i, x in enumerate(top, 1)]
    caption = (f"📅 The Week In Markets ({span})\nThe {len(top)} biggest stories of the week.\n\n"
               + "\n".join(lines) + "\n\nSwipe for every story ➡️\n" + " ".join(config.WEEKLY_HASHTAGS)
               + "\nAutomated headline alerts. Not financial advice.")
    # short text version for Threads / Telegram (fits Threads' 500 characters)
    text = f"📅 The Week In Markets ({span})"
    for ln in lines:
        if len(text) + 1 + len(ln) > 470:
            break
        text += "\n" + ln
    return {"slides": slides, "caption": caption[:2150], "text": text, "window": span, "count": len(top)}


def due(at: str, tzname: str, done_day: str, now: float, weekday: int | None = None,
        window_hours: float = 3) -> str | None:
    """Today's date (local) if it's time and not yet done, else None."""
    from zoneinfo import ZoneInfo
    local = datetime.fromtimestamp(now, ZoneInfo(tzname))
    day = local.strftime("%Y-%m-%d")
    if done_day == day or (weekday is not None and local.weekday() != weekday):
        return None
    h, m = (int(v) for v in at.split(":"))
    start = local.replace(hour=h, minute=m, second=0, microsecond=0)
    return day if start <= local < start + timedelta(hours=window_hours) else None
