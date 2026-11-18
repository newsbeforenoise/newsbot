"""
Free live price alerts (First Squawk style):
  "USD/JPY Rises Above 160.00, Now At 160.08"
  "Bitcoin Down 5.2% On The Day At $68,847"

Data: Yahoo Finance's public chart endpoint (no key, unofficial - if Yahoo
changes it, alerts just stop; news posting is unaffected).
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import config

UA = "Mozilla/5.0 (compatible; NewsHeadlineBot/1.0)"
STALE_SECONDS = 20 * 60   # market closed / data stale -> no alerts


def fetch_quote(symbol: str) -> tuple[float, float, int] | None:
    """Returns (price, previous_close, market_time) or None."""
    err: object = "no data"
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/"
               f"{urllib.parse.quote(symbol)}?interval=5m&range=1d")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                meta = json.loads(r.read())["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price and prev:
                return float(price), float(prev), int(meta.get("regularMarketTime") or 0)
        except Exception as e:  # noqa: BLE001
            err = e
    print(f"  ! price failed: {symbol} ({err})")
    return None


def fmt(cfg: dict, value: float, dp: int | None = None) -> str:
    dp = cfg.get("dp", 2) if dp is None else dp
    return f'{cfg.get("prefix", "")}{value:,.{dp}f}{cfg.get("suffix", "")}'


def level_dp(step: float) -> int:
    """Decimals a round level needs: step 50 -> 0 ("$4,050"), step 0.01 -> 2 ("1.17")."""
    text = f"{step:.6f}".rstrip("0").rstrip(".")
    return len(text.split(".")[1]) if "." in text else 0


def check_symbol(cfg: dict, price: float, prev: float, mtime: int, st: dict, now: float) -> dict | None:
    """Pure logic. Updates state `st` in place; returns one alert or None."""
    last = st.get("last")
    st["last"] = price
    chg = (price / prev - 1) * 100
    day = datetime.fromtimestamp(mtime or now, timezone.utc).strftime("%Y-%m-%d")
    done = st.setdefault("pct", {})
    for k in [k for k in done if k != day]:
        del done[k]
    today = done.setdefault(day, [])
    sign = "+" if chg >= 0 else "-"
    if last is None:
        # First time we see this market: just record it. Moves that ALREADY happened
        # today are marked as done, so we never post stale "catch-up" alerts.
        today.extend(f"{sign}{t}" for t in cfg.get("pct", []) if abs(chg) >= t)
        return None
    if mtime and now - mtime > STALE_SECONDS:
        return None
    alert_text = None

    # 1) daily % move thresholds (each once per day per direction)
    hit = [t for t in sorted(cfg.get("pct", [])) if abs(chg) >= t and f"{sign}{t}" not in today]
    if hit:
        for t in cfg["pct"]:
            if abs(chg) >= t:
                today.append(f"{sign}{t}")
        direction = "Up" if chg >= 0 else "Down"
        alert_text = f'{cfg["name"]} {direction} {abs(chg):.1f}% On The Day At {fmt(cfg, price)}'

    # 2) round-number levels crossed since the last run
    step = cfg.get("step")
    levels = st.setdefault("levels", {})
    for k in [k for k, ts in levels.items() if now - ts > config.PRICE_LEVEL_COOLDOWN_HOURS * 3600]:
        del levels[k]
    if step and price != last:
        if price > last:
            level = math.floor(price / step) * step
            crossed = level > last
            verb = "Rises Above"
        else:
            level = math.ceil(price / step) * step
            crossed = level < last
            verb = "Falls Below"
        key = f"{level:.6f}"
        if crossed and key not in levels:
            levels[key] = now
            if not alert_text:
                alert_text = f'{cfg["name"]} {verb} {fmt(cfg, level, level_dp(step))}, Now At {fmt(cfg, price)}'

    if not alert_text:
        return None
    tags = [cfg["tag"]] if cfg.get("tag") else []
    return {
        "text": alert_text, "flags": cfg.get("flag", "") or config.DEFAULT_FLAG, "countries": [],
        "tags": tags + [config.MARKET_TAG], "priority": 3,
        "focus": cfg.get("flag") in ("🇺🇸", "🇮🇳"), "words": [], "sources": ["Market Data"],
        "credit": [], "item_ids": [], "story_id": f'price:{cfg["symbol"]}:{int(now)}',
        "followup": False, "is_price": True,
    }


def price_alerts(state: dict, now: float | None = None) -> list[dict]:
    """Fetches every symbol, returns alerts. `state` is saved by the caller."""
    if not config.PRICE_ALERTS:
        return []
    now = now or time.time()
    alerts = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        quotes = list(pool.map(lambda c: fetch_quote(c["symbol"]), config.PRICE_SYMBOLS))
    for cfg, q in zip(config.PRICE_SYMBOLS, quotes):
        if not q:
            continue
        a = check_symbol(cfg, *q, state.setdefault(cfg["symbol"], {}), now)
        if a:
            alerts.append(a)
    return alerts
