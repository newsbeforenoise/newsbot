"""
Update 7 extras (pure logic, no network - bot.py does the posting):
  * BREAKING label for the biggest stories
  * Market open / close summaries ("🔔 US Stocks Close ...")
  * Economic calendar ("🗓 Today's key data" + "⏰ Coming up at 8:30 AM ET")
  * Daily health report for your private Telegram chat
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import config


def _zone(name: str):
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return timezone.utc


def _hm(text: str) -> tuple[int, int]:
    h, m = text.split(":")
    return int(h), int(m)


def _at(day: datetime, text: str) -> datetime:
    h, m = _hm(text)
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def _clock(dt: datetime) -> str:
    """'8:30 AM'"""
    return dt.strftime("%I:%M %p").lstrip("0")


# ----------------------------------------------------------------------------
# BREAKING
# ----------------------------------------------------------------------------
def breaking_today(posted: list, now: float) -> int:
    return sum(1 for p in posted if p.get("breaking") and p["ts"] > now - 86400)


def is_breaking(story: dict, group_text: str, posted: list, now: float) -> bool:
    """Official releases, war/central-bank keywords, or big index moves - at most N a day."""
    if not config.BREAKING_ENABLED or story.get("followup") or story.get("kind"):
        return False
    if breaking_today(posted, now) >= config.BREAKING_MAX_PER_DAY:
        return False
    if story.get("is_price"):
        return (story.get("symbol") in config.BREAKING_PRICE_SYMBOLS
                and story.get("move_pct", 0) >= config.BREAKING_PRICE_PCT)
    if story.get("priority", 0) < 2:
        return False
    if story.get("official") and config.BREAKING_OFFICIAL:
        return True
    low = (group_text or story.get("text", "")).lower()
    return any(k in low for k in config.BREAKING_KEYWORDS)


# ----------------------------------------------------------------------------
# Market open / close
# ----------------------------------------------------------------------------
SHORT_NAMES = {"Nasdaq Composite": "Nasdaq", "Dollar Index": "Dollar Index (DXY)"}


def _symbol_cfg(sym: str) -> dict | None:
    return next((c for c in config.PRICE_SYMBOLS if c["symbol"] == sym), None)


def _fmt(cfg: dict, value: float) -> str:
    dp = cfg.get("dp", 2)
    return f'{cfg.get("prefix", "")}{value:,.{dp}f}{cfg.get("suffix", "")}'


def bell_line(sym: str, quote: list | None) -> str | None:
    cfg = _symbol_cfg(sym)
    if not cfg or not quote:
        return None
    price, prev = quote[0], quote[1]
    if not price or not prev:
        return None
    chg = (price / prev - 1) * 100
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "■")
    return f"{SHORT_NAMES.get(cfg['name'], cfg['name'])} {_fmt(cfg, price)} {arrow} {chg:+.2f}%"


def due_bells(price_state: dict, sent: dict, now: float) -> list[dict]:
    """Bells whose time has come today, the market traded, and not yet posted.
    `sent` = {bell_id: 'YYYY-MM-DD'} (updated by the caller after posting)."""
    out = []
    for bell in config.MARKET_BELLS:
        tz = _zone(bell["tz"])
        local = datetime.fromtimestamp(now, tz)
        if local.weekday() >= 5:
            continue
        today = local.strftime("%Y-%m-%d")
        if sent.get(bell["id"]) == today:
            continue
        start = _at(local, bell["at"])
        if not (start <= local < start + timedelta(minutes=config.BELL_WINDOW_MINUTES)):
            continue
        q = (price_state.get(bell["symbols"][0]) or {}).get("q")
        if not q or not q[2]:
            continue
        mtime = datetime.fromtimestamp(q[2], tz)
        if mtime < _at(local, bell["fresh"]):
            continue          # no trading today (holiday) or prices not updated yet
        lines = [ln for ln in (bell_line(s, (price_state.get(s) or {}).get("q")) for s in bell["symbols"]) if ln]
        if not lines:
            continue
        out.append({"id": bell["id"], "day": today, "title": bell["title"], "lines": lines,
                    "tags": bell.get("tags", [])})
    return out


# ----------------------------------------------------------------------------
# Economic calendar
# ----------------------------------------------------------------------------
def parse_calendar(raw: bytes | None) -> list[dict]:
    """Forex Factory weekly JSON -> [{ts, title, country, flag, forecast, previous, timed}] (filtered)."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for e in data:
        if not isinstance(e, dict):
            continue
        country = (e.get("country") or "").upper()
        if country not in config.CALENDAR_COUNTRIES or e.get("impact") not in config.CALENDAR_IMPACT:
            continue
        try:
            dt = datetime.fromisoformat(str(e.get("date", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        title = " ".join(str(e.get("title", "")).split())
        if not title:
            continue
        out.append({"ts": dt.timestamp(), "title": title, "country": country,
                    "flag": config.CALENDAR_COUNTRIES[country],
                    "forecast": str(e.get("forecast") or "").strip(),
                    "previous": str(e.get("previous") or "").strip(),
                    # "All Day" / "Tentative" events come through at midnight: no exact time
                    "timed": not (dt.hour == 0 and dt.minute == 0)})
    out.sort(key=lambda x: x["ts"])
    return out


def event_key(e: dict) -> str:
    return f"{int(e['ts'])}|{e['country']}|{e['title']}"


def _numbers(e: dict) -> str:
    bits = []
    if e["forecast"]:
        bits.append(f"Forecast {e['forecast']}")
    if e["previous"]:
        bits.append(f"Previous {e['previous']}")
    return (" – " + ", ".join(bits)) if bits else ""


def heads_up_posts(events: list[dict], sent: list[str], now: float) -> list[dict]:
    """One 'Coming up' post per release time, posted 5-17 minutes before (runs are every 5 min)."""
    lead = config.CALENDAR_HEADS_UP_MINUTES * 60
    due = [e for e in events if e["timed"] and event_key(e) not in sent
           and now < e["ts"] <= now + lead + 2 * 60 and e["ts"] - now >= max(lead - 10 * 60, 60)]
    tz = _zone(config.CALENDAR_TIMEZONE)
    posts = []
    for ts in sorted({e["ts"] for e in due}):
        group = [e for e in due if e["ts"] == ts][: config.CALENDAR_MAX_LINES]
        when = datetime.fromtimestamp(ts, tz)
        head = f"⏰ Coming Up At {_clock(when)} {when.tzname()}"
        if len(group) == 1:
            e = group[0]
            text = f"{head}: {e['flag']} {e['title']}{_numbers(e)}"
        else:
            text = head + "\n" + "\n".join(f"{e['flag']} {e['title']}{_numbers(e)}" for e in group)
        posts.append({"text": text, "keys": [event_key(e) for e in group], "tags": ["#EconomicCalendar"]})
    return posts


def daily_calendar_post(events: list[dict], sent_day: str, now: float) -> dict | None:
    """'🗓 Today's Key Data (EST)' list, once each weekday morning."""
    tz = _zone(config.CALENDAR_TIMEZONE)
    local = datetime.fromtimestamp(now, tz)
    today = local.strftime("%Y-%m-%d")
    if local.weekday() >= 5 or sent_day == today:
        return None
    start = _at(local, config.CALENDAR_DAILY_AT)
    if not (start <= local < start + timedelta(hours=2)):
        return None
    end = local.replace(hour=23, minute=59, second=59)
    todays = [e for e in events if now <= e["ts"] <= end.timestamp()]
    if not todays:
        return {"text": "", "day": today}          # nothing big today: mark done, post nothing
    lines = []
    for e in todays[: config.CALENDAR_MAX_LINES]:
        t = _clock(datetime.fromtimestamp(e["ts"], tz)) if e["timed"] else "All Day"
        lines.append(f"{t} {e['flag']} {e['title']}" + (f" (F {e['forecast']})" if e["forecast"] else ""))
    more = len(todays) - len(lines)
    if more > 0:
        lines.append(f"+{more} more")
    text = f"🗓 Today's Key Data ({local.tzname()})\n" + "\n".join(lines)
    return {"text": text, "day": today, "tags": ["#EconomicCalendar"]}


# ----------------------------------------------------------------------------
# Daily health report
# ----------------------------------------------------------------------------
def report_due(stats: dict, now: float) -> str | None:
    """Returns today's date string when the report should be sent now, else None."""
    if not config.DAILY_REPORT:
        return None
    local = datetime.fromtimestamp(now, _zone(config.DAILY_REPORT_TIMEZONE))
    today = local.strftime("%Y-%m-%d")
    if stats.get("report_day") == today:
        return None
    start = _at(local, config.DAILY_REPORT_AT)
    if not (start <= local < start + timedelta(hours=3)):
        return None
    return today


def build_report(posted: list, stats: dict, enabled: list[str], digest_on: list[str], now: float) -> str:
    since = now - 86400
    recent = [p for p in posted if p["ts"] > since]
    news = [p for p in recent if not p.get("kind") and not p.get("is_price")]
    lines = [f"📊 {config.BRAND_NAME} – last 24 hours"]
    lines.append(f"Headlines: {len(news)} (🔴 breaking {sum(1 for p in recent if p.get('breaking'))})"
                 f" | price alerts {sum(1 for p in recent if p.get('is_price'))}"
                 f" | market & calendar {sum(1 for p in recent if p.get('kind'))}")
    problems = []
    live = [n for n in enabled if n not in digest_on]
    counts = []
    for name in live:
        n = sum(1 for p in recent if name in p.get("platforms", []))
        counts.append(f"{name} {n}")
        if n == 0 and recent:
            problems.append(f"{name} posted nothing")
    if counts:
        lines.append("Posted: " + " | ".join(counts))
    digests = [d for d in stats.get("digests", []) if d["ts"] > since]
    for name in digest_on:
        n = sum(1 for d in digests if name in d.get("done", []))
        lines.append(f"{name}: {n} hourly carousels")
        if digests and n == 0:
            problems.append(f"{name} carousels failing")
    fails = [f for f in stats.get("fails", []) if f["ts"] > since]
    if fails:
        by = {}
        for f in fails:
            by.setdefault(f["platform"], []).append(f)
        lines.append("Errors: " + " | ".join(f"{k} {len(v)}" for k, v in sorted(by.items())))
        for k, v in sorted(by.items()):
            lines.append(f"  {k} last error: {v[-1]['error'][:120]}")
    feeds = stats.get("feeds")
    if feeds:
        lines.append(f"News feeds working: {feeds[0]}/{feeds[1]}")
        if feeds[0] < feeds[1] * 0.5:
            problems.append("many news feeds down")
    if not recent:
        problems.append("nothing posted at all")
    lines.append("")
    lines.append("⚠️ Check: " + "; ".join(problems) if problems else "✅ All good")
    return "\n".join(lines)
