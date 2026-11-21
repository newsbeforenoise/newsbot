"""Stock Spotlight (update 17): when there's been no news for a while (quiet hours, weekends),
post a factual technical snapshot of one stock that is near its 52-week high or low, or one of
the biggest movers of the week.

Only data, never advice: price vs 52-week range, 50/200-day averages, RSI, volume, recent change,
plus a plain "technical tone" count of how many of those signals lean up vs down. Every post says
it is not financial advice and not a buy/sell recommendation.

Data: Yahoo Finance daily chart (same free source as the price alerts).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import config

UA = "Mozilla/5.0 (compatible; NewsHeadlineBot/1.0)"


def fetch_history(symbol: str) -> dict | None:
    """1 year of daily candles: {"close": [...], "volume": [...], "time": last_ts, "currency": "USD"}."""
    err: object = "no data"
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/"
               f"{urllib.parse.quote(symbol)}?interval=1d&range=1y")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                res = json.loads(r.read())["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = [(c, h, l, v) for c, h, l, v in zip(q["close"], q["high"], q["low"], q["volume"])
                    if c is not None and h is not None and l is not None]
            if len(rows) < 60:
                return None
            meta = res.get("meta", {})
            return {"close": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                    "volume": [r[3] or 0 for r in rows], "time": int(meta.get("regularMarketTime") or 0),
                    "currency": meta.get("currency", "USD"), "price": meta.get("regularMarketPrice")}
        except Exception as e:  # noqa: BLE001
            err = e
    print(f"  ! spotlight history failed: {symbol} ({err})")
    return None


def _sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _rsi(xs: list[float], n: int = 14) -> float | None:
    if len(xs) <= n:
        return None
    gains = losses = 0.0
    for a, b in zip(xs[-n - 1:-1], xs[-n:]):
        d = b - a
        gains += max(d, 0)
        losses += max(-d, 0)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def analyze(symbol: str, h: dict) -> dict:
    c = h["close"]
    price = float(h.get("price") or c[-1])
    hi, lo = max(h["high"]), min(h["low"])
    avg_vol = _sma(h["volume"][:-1], 20) or 0
    return {
        "symbol": symbol, "price": price, "high52": hi, "low52": lo,
        "from_high": (price / hi - 1) * 100, "from_low": (price / lo - 1) * 100,
        "chg1": (c[-1] / c[-2] - 1) * 100, "chg5": (c[-1] / c[-6] - 1) * 100,
        "sma50": _sma(c, 50), "sma200": _sma(c, 200), "rsi": _rsi(c),
        "vol_ratio": (h["volume"][-1] / avg_vol) if avg_vol else None,
        "currency": h.get("currency", "USD"), "time": h.get("time", 0),
    }


def setup_of(a: dict) -> str | None:
    """Why this stock is interesting: 'high' / 'low' / 'mover' / None."""
    if a["from_high"] >= -config.SPOTLIGHT_NEAR_PCT:
        return "high"
    if a["from_low"] <= config.SPOTLIGHT_NEAR_PCT:
        return "low"
    if abs(a["chg5"]) >= config.SPOTLIGHT_MOVER_PCT:
        return "mover"
    return None


def pick(analyses: list[dict], recent: list[str]) -> dict | None:
    """Prefer 52-week highs/lows (closest first), then the biggest 5-day move; skip recent picks."""
    fresh = [a for a in analyses if a["symbol"] not in recent and setup_of(a)]
    if not fresh:
        return None
    rank = {"high": 0, "low": 0, "mover": 1}
    def key(a):
        s = setup_of(a)
        closeness = abs(a["from_high"]) if s == "high" else a["from_low"] if s == "low" else -abs(a["chg5"])
        return (rank[s], closeness)
    return sorted(fresh, key=key)[0]


def _money(a: dict, x: float) -> str:
    sym = {"USD": "$", "INR": "₹"}.get(a["currency"], "")
    return f"{sym}{x:,.2f}" if sym else f"{x:,.2f} {a['currency']}"


def _pct(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x):.1f}%"


def signals(a: dict) -> list[tuple[str, int]]:
    """(plain-English fact, lean) where lean = +1 up, -1 down, 0 neutral."""
    out: list[tuple[str, int]] = []
    p = a["price"]
    if a["sma50"]:
        up = p >= a["sma50"]
        out.append((f"{'Above' if up else 'Below'} its 50-day average ({_money(a, a['sma50'])})", 1 if up else -1))
    if a["sma200"]:
        up = p >= a["sma200"]
        out.append((f"{'Above' if up else 'Below'} its 200-day average ({_money(a, a['sma200'])})", 1 if up else -1))
    if a["rsi"] is not None:
        r = a["rsi"]
        if r >= 70:
            out.append((f"RSI {r:.0f}: overbought zone (momentum stretched)", 0))
        elif r <= 30:
            out.append((f"RSI {r:.0f}: oversold zone (selling stretched)", 0))
        else:
            out.append((f"RSI {r:.0f}: {'positive' if r >= 50 else 'weak'} momentum", 1 if r >= 50 else -1))
    if a["vol_ratio"]:
        v = a["vol_ratio"]
        if v >= 1.5:
            out.append((f"Volume {v:.1f}× its 20-day average (heavy trading)", 1 if a["chg1"] >= 0 else -1))
        elif v <= 0.6:
            out.append((f"Volume {v:.1f}× its 20-day average (light trading)", 0))
    out.append((f"5-day change {_pct(a['chg5'])}", 1 if a["chg5"] > 1 else -1 if a["chg5"] < -1 else 0))
    return out


def tone(sigs: list[tuple[str, int]]) -> str:
    up = sum(1 for _, s in sigs if s > 0)
    down = sum(1 for _, s in sigs if s < 0)
    n = up + down
    if not n:
        return "Mixed / neutral"
    if up > down:
        return f"Leans positive ({up} of {n} trend signals up)"
    if down > up:
        return f"Leans negative ({down} of {n} trend signals down)"
    return f"Mixed ({up} up, {down} down)"


def compose(a: dict, name: str) -> dict:
    """{"text": Telegram/Threads text, "headline": short card line, "tags": [...]}"""
    s = setup_of(a)
    tick = a["symbol"].split(".")[0]
    who = f"{name} ({tick})" if name and name.upper() != tick else tick
    if s == "high":
        where = (f"at a new 52-week high" if a["from_high"] >= -0.3 else
                 f"{abs(a['from_high']):.1f}% below its 52-week high ({_money(a, a['high52'])})")
        head = f"{who} trades {where}"
    elif s == "low":
        where = (f"at a new 52-week low" if a["from_low"] <= 0.3 else
                 f"{a['from_low']:.1f}% above its 52-week low ({_money(a, a['low52'])})")
        head = f"{who} trades {where}"
    else:
        head = f"{who} {'jumps' if a['chg5'] > 0 else 'slides'} {abs(a['chg5']):.1f}% in 5 sessions"
    sigs = signals(a)
    lines = [
        f"🔍 STOCK SPOTLIGHT: {who}",
        "",
        f"📍 {_money(a, a['price'])} ({_pct(a['chg1'])} last session)",
        "🎯 " + (lambda t: t[:1].upper() + t[1:])(head.replace(who + " trades ", "").replace(who + " ", "")),
        f"📏 52-week range: {_money(a, a['low52'])} – {_money(a, a['high52'])}",
        "",
        "📊 Technical picture",
    ] + [f"• {t}" for t, _ in sigs] + [
        "",
        f"🧭 Technical tone: {tone(sigs)}",
        "",
        "⚠️ Data snapshot only, not financial advice and not a buy/sell recommendation. Do your own research.",
    ]
    india = a["symbol"].endswith(".NS")
    tags = ["#StockSpotlight", "#IndianStocks" if india else "#Stocks", "#" + tick.replace("-", "").replace("&", "")]
    card = f"{head} · RSI {a['rsi']:.0f}" if a["rsi"] is not None else head
    return {"text": "\n".join(lines), "headline": card, "tags": tags, "country": "IN" if india else "US",
            "symbol": a["symbol"], "setup": s}
