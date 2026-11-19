"""
Headline cards for Instagram / Facebook: black background, white text.

  NEWS BEFORE NOISE                      13 NOV 2026 · 07:12 UTC
  [MARKETS]  [USA] [JAPAN]

  Japan's Nikkei Jumps 2.4% As Yen
  Weakens Past 160 Per Dollar

  Source: Nikkei                                  @NewsB4Noise

Needs Pillow (installed by the GitHub workflow). If Pillow is missing, image
platforms are skipped and everything else keeps posting.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path

import config

ASSETS = Path(__file__).resolve().parent / "assets"
W, H = 1080, 1350          # 4:5 portrait - the largest size Instagram shows in the feed
MARGIN = 84


def available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def country_name(code: str) -> str:
    """'#SouthKorea' -> 'SOUTH KOREA', '#USA' -> 'USA'."""
    tag = config.COUNTRIES.get(code, {}).get("tag", code).lstrip("#")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tag).upper()


def label_for(story: dict) -> tuple[str, str]:
    """(label text, colour) for the category pill."""
    if story.get("is_price"):
        return "PRICE ALERT", config.CARD_ACCENT_PRICE
    if story.get("followup"):
        return "UPDATE", config.CARD_ACCENT_UPDATE
    if story.get("priority", 3) >= 3:
        return "MARKETS", config.CARD_ACCENT_MARKETS
    return "GEOPOLITICS", config.CARD_ACCENT_GEO


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render(story: dict, headline: str, credit: str, now: datetime | None = None) -> bytes:
    """Returns the card as JPEG bytes."""
    from PIL import Image, ImageDraw, ImageFont

    now = now or datetime.now(timezone.utc)
    bold = str(ASSETS / "Poppins-Bold.ttf")
    medium = str(ASSETS / "Poppins-Medium.ttf")
    img = Image.new("RGB", (W, H), config.CARD_BACKGROUND)
    d = ImageDraw.Draw(img)
    grey = (150, 150, 150)

    # --- top bar: brand + time
    f_small = ImageFont.truetype(medium, 30)
    d.text((MARGIN, MARGIN), config.BRAND_NAME.upper(), font=f_small, fill=config.CARD_TEXT)
    stamp = (now.strftime("%d %b %Y · %H:%M ") + (now.tzname() or "UTC")).upper()
    d.text((W - MARGIN - d.textlength(stamp, font=f_small), MARGIN), stamp, font=f_small, fill=grey)
    d.line([(MARGIN, MARGIN + 62), (W - MARGIN, MARGIN + 62)], fill=(40, 40, 40), width=2)

    # --- pills: category + countries
    f_pill = ImageFont.truetype(bold, 28)
    x, y = MARGIN, MARGIN + 104
    label, colour = label_for(story)
    pills = [(label, colour, config.CARD_BACKGROUND)] + [
        (country_name(c), (38, 38, 38), config.CARD_TEXT) for c in story.get("countries", [])[:3]]
    for text, bg, fg in pills:
        tw = d.textlength(text, font=f_pill)
        d.rounded_rectangle([x, y, x + tw + 44, y + 58], radius=29, fill=bg)
        d.text((x + 22, y + 10), text, font=f_pill, fill=fg)
        x += tw + 44 + 16

    # --- headline: largest size that fits the space
    top, bottom = y + 58 + 70, H - MARGIN - 120
    box_w = W - 2 * MARGIN
    for size in range(84, 38, -4):
        f_head = ImageFont.truetype(bold, size)
        lines = _wrap(d, headline, f_head, box_w)
        line_h = int(size * 1.22)
        if len(lines) * line_h <= bottom - top:
            break
    block_h = len(lines) * line_h
    ty = top + max(0, (bottom - top - block_h) // 3)     # sit slightly above centre
    for ln in lines:
        d.text((MARGIN, ty), ln, font=f_head, fill=config.CARD_TEXT)
        ty += line_h

    # --- bottom bar: source + handle
    d.line([(MARGIN, H - MARGIN - 78), (W - MARGIN, H - MARGIN - 78)], fill=(40, 40, 40), width=2)
    f_foot = ImageFont.truetype(medium, 32)
    if credit:
        d.text((MARGIN, H - MARGIN - 44), f"Source: {credit}", font=f_foot, fill=grey)
    handle = config.BRAND_HANDLE
    d.text((W - MARGIN - d.textlength(handle, font=f_foot), H - MARGIN - 44), handle, font=f_foot,
           fill=config.CARD_TEXT)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92, optimize=True)
    return buf.getvalue()


def _fit_line(d, text: str, font, width: int) -> str:
    """Truncate text with … so it fits on one line."""
    if d.textlength(text, font=font) <= width:
        return text
    while text and d.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip(" ,.;:-–") + "…"


def render_cover(headlines: list[str], window: str, total: int, now: datetime | None = None) -> bytes:
    """First slide of the hourly carousel: what happened this hour, at a glance."""
    from PIL import Image, ImageDraw, ImageFont

    now = now or datetime.now(timezone.utc)
    bold = str(ASSETS / "Poppins-Bold.ttf")
    medium = str(ASSETS / "Poppins-Medium.ttf")
    img = Image.new("RGB", (W, H), config.CARD_BACKGROUND)
    d = ImageDraw.Draw(img)
    grey = (150, 150, 150)

    f_small = ImageFont.truetype(medium, 30)
    d.text((MARGIN, MARGIN), config.BRAND_NAME.upper(), font=f_small, fill=config.CARD_TEXT)
    stamp = now.strftime("%d %b %Y").upper()
    d.text((W - MARGIN - d.textlength(stamp, font=f_small), MARGIN), stamp, font=f_small, fill=grey)
    d.line([(MARGIN, MARGIN + 62), (W - MARGIN, MARGIN + 62)], fill=(40, 40, 40), width=2)

    # pill + title
    f_pill = ImageFont.truetype(bold, 28)
    y = MARGIN + 104
    pill = "THIS HOUR"
    tw = d.textlength(pill, font=f_pill)
    d.rounded_rectangle([MARGIN, y, MARGIN + tw + 44, y + 58], radius=29, fill=config.CARD_ACCENT_MARKETS)
    d.text((MARGIN + 22, y + 10), pill, font=f_pill, fill=config.CARD_BACKGROUND)
    f_title = ImageFont.truetype(bold, 84)
    y += 100
    for line in ("Global Markets", "This Hour"):
        d.text((MARGIN, y), line, font=f_title, fill=config.CARD_TEXT)
        y += 102
    f_sub = ImageFont.truetype(medium, 34)
    sub = f"{window}  ·  {total} headline{'s' if total != 1 else ''}"
    d.text((MARGIN, y + 6), sub, font=f_sub, fill=grey)
    y += 90

    # numbered headline list
    f_item = ImageFont.truetype(medium, 36)
    f_num = ImageFont.truetype(bold, 36)
    shown = headlines[:6]
    for i, h in enumerate(shown, 1):
        num = f"{i}"
        d.text((MARGIN, y), num, font=f_num, fill=config.CARD_ACCENT_MARKETS)
        d.text((MARGIN + 56, y), _fit_line(d, h, f_item, W - 2 * MARGIN - 56), font=f_item, fill=config.CARD_TEXT)
        y += 62
    more = total - len(shown)
    if more > 0:
        d.text((MARGIN + 56, y + 4), f"+{more} more inside", font=f_item, fill=grey)

    # footer
    d.line([(MARGIN, H - MARGIN - 78), (W - MARGIN, H - MARGIN - 78)], fill=(40, 40, 40), width=2)
    f_foot = ImageFont.truetype(bold, 34)
    swipe = "Swipe for every headline"
    d.text((MARGIN, H - MARGIN - 46), swipe, font=f_foot, fill=config.CARD_ACCENT_MARKETS)
    ax, ay = MARGIN + d.textlength(swipe, font=f_foot) + 22, H - MARGIN - 22   # drawn arrow (font has no →)
    d.line([(ax, ay), (ax + 40, ay)], fill=config.CARD_ACCENT_MARKETS, width=5)
    d.polygon([(ax + 52, ay), (ax + 34, ay - 13), (ax + 34, ay + 13)], fill=config.CARD_ACCENT_MARKETS)
    f_handle = ImageFont.truetype(medium, 32)
    handle = config.BRAND_HANDLE
    d.text((W - MARGIN - d.textlength(handle, font=f_handle), H - MARGIN - 44), handle, font=f_handle,
           fill=config.CARD_TEXT)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92, optimize=True)
    return buf.getvalue()
