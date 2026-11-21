"""
Headline cards for Instagram / Facebook: themed colour background with the NBN logo
(update 16; CARD_STYLE = "black" for the original plain black), white text.

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
    if story.get("spotlight"):
        return "STOCK SPOTLIGHT", (190, 150, 255)
    if story.get("is_price"):
        return "PRICE ALERT", config.CARD_ACCENT_PRICE
    if story.get("followup"):
        return "UPDATE", config.CARD_ACCENT_UPDATE
    if story.get("priority", 3) >= 3:
        return "MARKETS", config.CARD_ACCENT_MARKETS
    return "GEOPOLITICS", config.CARD_ACCENT_GEO


# ----------------------------------------------------------------------------
# Backgrounds (update 16): colour gradient by story type, faint chart line,
# large NBN logo watermark. CARD_STYLE = "black" in config.py restores the old look.
# ----------------------------------------------------------------------------
def theme_for(label: str, seed: str = "") -> tuple:
    themes = getattr(config, "CARD_THEMES", {})
    options = themes.get(label) or themes.get("MARKETS") or [((0, 0, 0), (0, 0, 0))]
    return options[sum(map(ord, seed)) % len(options)]


def background(w: int, h: int, label: str = "BRAND", seed: str = "", bottom_at: int | None = None):
    """RGB image: gradient + subtle chart line + logo watermark (or plain black)."""
    from PIL import Image, ImageDraw
    if getattr(config, "CARD_STYLE", "black") != "themed":
        return Image.new("RGB", (w, h), config.CARD_BACKGROUND)
    top, bottom = theme_for(label, seed)
    mask = Image.linear_gradient("L").resize((w, h))                 # 0 at top -> 255 at bottom
    img = Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), mask)
    d = ImageDraw.Draw(img, "RGBA")
    # faint grid + a seeded "price line" across the lower part of the card
    for gy in range(int(h * 0.55), h, 90):
        d.line([(0, gy), (w, gy)], fill=(255, 255, 255, 10), width=1)
    rnd, y, pts = (sum(map(ord, seed)) or 7), h * 0.80, []
    for i in range(0, w + 60, 60):
        rnd = (rnd * 1103515245 + 12345) % 2147483648
        y = min(h * 0.93, max(h * 0.62, y + ((rnd % 120) - 60)))
        pts.append((i, y))
    d.line(pts, fill=(255, 255, 255, 26), width=5, joint="curve")
    # big logo watermark, bottom-right, partly off the edge
    logo = ASSETS / "logo.png"
    if logo.exists():
        size = int(w * 0.78)
        lg = Image.open(logo).convert("RGB").resize((size, size))
        wm_mask = lg.convert("L").point(lambda v: int(v * 0.09))      # only the bright logo parts show, faintly
        img.paste(lg, (w - int(size * 0.72), (bottom_at or h) - int(size * 0.94)), wm_mask)
    return img


def _badge(size: int):
    """Small round NBN logo for next to the brand name."""
    from PIL import Image, ImageDraw
    p = ASSETS / "logo.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGB").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    return im, mask


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
    img = render_image(story, headline, credit, now)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92, optimize=True)
    return buf.getvalue()


def render_image(story: dict, headline: str, credit: str, now: datetime | None = None,
                 height: int = H, top_pad: int = 0):
    """The card as a PIL image. height/top_pad: draw on a taller canvas (reel frames) so the
    background runs edge to edge."""
    from PIL import ImageDraw, ImageFont

    now = now or datetime.now(timezone.utc)
    bold = str(ASSETS / "Poppins-Bold.ttf")
    medium = str(ASSETS / "Poppins-Medium.ttf")
    label, colour = label_for(story)
    img = background(W, height, label, headline, bottom_at=top_pad + H)
    d = ImageDraw.Draw(img, "RGBA")
    grey = (170, 170, 170)
    rule = (255, 255, 255, 40)
    oy = top_pad

    # --- top bar: logo + brand + time
    f_small = ImageFont.truetype(medium, 30)
    bx = MARGIN
    badge = _badge(46) if getattr(config, "CARD_STYLE", "black") == "themed" else None
    if badge:
        img.paste(badge[0], (MARGIN, oy + MARGIN - 6), badge[1])
        bx = MARGIN + 60
    d.text((bx, oy + MARGIN), config.BRAND_NAME.upper(), font=f_small, fill=config.CARD_TEXT)
    stamp = (now.strftime("%d %b %Y · %H:%M ") + (now.tzname() or "UTC")).upper()
    d.text((W - MARGIN - d.textlength(stamp, font=f_small), oy + MARGIN), stamp, font=f_small, fill=grey)
    d.line([(MARGIN, oy + MARGIN + 62), (W - MARGIN, oy + MARGIN + 62)], fill=rule, width=2)

    # --- pills: category + countries
    f_pill = ImageFont.truetype(bold, 28)
    x, y = MARGIN, oy + MARGIN + 104
    pills = [(label, colour, (0, 0, 0))] + [
        (country_name(c), (255, 255, 255, 38), config.CARD_TEXT) for c in story.get("countries", [])[:3]]
    for text, bg, fg in pills:
        tw = d.textlength(text, font=f_pill)
        d.rounded_rectangle([x, y, x + tw + 44, y + 58], radius=29, fill=bg)
        d.text((x + 22, y + 10), text, font=f_pill, fill=fg)
        x += tw + 44 + 16

    # --- headline: largest size that fits the space
    top, bottom = y + 58 + 70, oy + H - MARGIN - 120
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
    fy = oy + H - MARGIN
    d.line([(MARGIN, fy - 78), (W - MARGIN, fy - 78)], fill=rule, width=2)
    f_foot = ImageFont.truetype(medium, 32)
    if credit:
        d.text((MARGIN, fy - 44), f"Source: {credit}", font=f_foot, fill=grey)
    handle = config.BRAND_HANDLE
    d.text((W - MARGIN - d.textlength(handle, font=f_foot), fy - 44), handle, font=f_foot,
           fill=config.CARD_TEXT)
    return img


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
    img = background(W, H, "MARKETS", window)
    d = ImageDraw.Draw(img, "RGBA")
    grey = (170, 170, 170)

    f_small = ImageFont.truetype(medium, 30)
    d.text((MARGIN, MARGIN), config.BRAND_NAME.upper(), font=f_small, fill=config.CARD_TEXT)
    stamp = now.strftime("%d %b %Y").upper()
    d.text((W - MARGIN - d.textlength(stamp, font=f_small), MARGIN), stamp, font=f_small, fill=grey)
    d.line([(MARGIN, MARGIN + 62), (W - MARGIN, MARGIN + 62)], fill=(255, 255, 255, 40), width=2)

    # pill + title
    f_pill = ImageFont.truetype(bold, 28)
    y = MARGIN + 104
    pill = "THIS HOUR"
    tw = d.textlength(pill, font=f_pill)
    d.rounded_rectangle([MARGIN, y, MARGIN + tw + 44, y + 58], radius=29, fill=config.CARD_ACCENT_MARKETS)
    d.text((MARGIN + 22, y + 10), pill, font=f_pill, fill=(0, 0, 0))
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
    d.line([(MARGIN, H - MARGIN - 78), (W - MARGIN, H - MARGIN - 78)], fill=(255, 255, 255, 40), width=2)
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
