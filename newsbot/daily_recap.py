"""
Daily evening recap (update 10): one long "everything that happened today" post.

  * Global / US edition  - after the US close (5:15 PM ET)
  * India edition        - after the India close (4:30 PM IST)

Written by a free AI model (GitHub Models, using the workflow's own GITHUB_TOKEN)
from ONLY the day's confirmed headlines, their article summaries and the closing
prices. Safety net: any paragraph containing a number that isn't in that material
is replaced by the plain headline. If the AI is unavailable, a plain numbered
list is posted instead - the recap never depends on it.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime

import config
import extras
import recap


EDITIONS = {
    "us": {"title": "🧾 A LOT HAPPENED IN GLOBAL MARKETS TODAY", "tz": "America/New_York",
           "symbols": ["^GSPC", "^IXIC", "^DJI", "^VIX", "DX-Y.NYB", "GC=F", "CL=F", "BTC-USD"],
           "tags": ["#StockMarket", "#Markets", "#WallStreet"]},
    "in": {"title": "🧾 INDIA MARKETS: EVERYTHING THAT HAPPENED TODAY", "tz": "Asia/Kolkata",
           "symbols": ["^NSEI", "^BSESN", "INR=X", "GC=F", "CL=F"],
           "tags": ["#Nifty", "#Sensex", "#StockMarketIndia"]},
}


def pick(log: list[dict], edition: str, since: float, until: float) -> list[dict]:
    pool = [x for x in log if since <= x["ts"] < until]
    if edition == "in":
        pool = [x for x in pool if "IN" in (x.get("countries") or [])]
        n = config.DAILY_RECAP_ITEMS_IN
    else:
        pool = [x for x in pool if (x.get("countries") or []) != ["IN"]]
        n = config.DAILY_RECAP_ITEMS_US
    return recap.top_stories(pool, since, until, n)


def market_lines(price_state: dict, edition: str) -> list[str]:
    return [ln for ln in (extras.bell_line(s, (price_state.get(s) or {}).get("q"))
                          for s in EDITIONS[edition]["symbols"]) if ln]


# ----------------------------------------------------------------------------
# AI writing (GitHub Models - free, uses the workflow's GITHUB_TOKEN)
# ----------------------------------------------------------------------------
SYSTEM = (
    "You are the news editor of 'News Before Noise', a neutral markets news channel. "
    "Write a daily recap using ONLY the facts in the material provided. Never add facts, numbers, "
    "names, quotes, causes or context that are not in the material. No opinions, predictions, "
    "jokes or investment advice. Plain text only: no markdown, no asterisks, no emojis, no hashtags."
)


def build_prompt(stories: list[dict], markets: list[str], day: str) -> str:
    parts = [f"Date: {day}", "", "Closing prices:"] + (markets or ["(none)"]) + ["", "Stories:"]
    for i, x in enumerate(stories, 1):
        parts.append(f"[{i}] Headline: {x['headline']}")
        if x.get("summary"):
            parts.append(f"    Summary: {x['summary']}")
        src = ", ".join(x.get("sources") or ([x["credit"]] if x.get("credit") else []))
        if src:
            parts.append(f"    Sources: {src}")
    parts += ["", f"Write exactly {len(stories)} numbered paragraphs, one per story, in the same order, "
              "formatted '1. ...', '2. ...'. Each paragraph: 2 to 4 sentences, factual, built only from that "
              "story's headline and summary (if the summary is missing, one sentence restating the headline). "
              "End each paragraph with the source in brackets, e.g. (Reuters). Output only the paragraphs."]
    return "\n".join(parts)


def ai_write(prompt: str, token: str) -> str:
    last = None
    for model in config.DAILY_RECAP_MODELS:
        body = json.dumps({"model": model, "temperature": 0.2, "max_tokens": 1800,
                           "messages": [{"role": "system", "content": SYSTEM},
                                        {"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://models.github.ai/inference/chat/completions", data=body, headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                out = json.loads(r.read())["choices"][0]["message"]["content"]
                if out and out.strip():
                    return out.strip()
        except urllib.error.HTTPError as e:
            last = f"{model}: HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:150]}"
        except Exception as e:  # noqa: BLE001
            last = f"{model}: {e}"
    raise RuntimeError(f"AI writer unavailable ({last})")


# ----------------------------------------------------------------------------
# Fact check: every number in a paragraph must appear in the source material
# ----------------------------------------------------------------------------
def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", text)}


def split_paragraphs(text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for m in re.finditer(r"(?ms)^\s*(\d{1,2})[.)]\s+(.+?)(?=^\s*\d{1,2}[.)]\s+|\Z)", text):
        out[int(m.group(1))] = " ".join(m.group(2).split())
    return out


def checked_paragraphs(ai_text: str, stories: list[dict], material: str) -> tuple[list[str], int]:
    """Returns (paragraphs, how many fell back to the plain headline)."""
    allowed = _numbers(material)
    paras = split_paragraphs(ai_text)
    out, fallbacks = [], 0
    for i, x in enumerate(stories, 1):
        p = re.sub(r"[*#_`]+", "", paras.get(i, "")).strip()
        bad = _numbers(p) - allowed
        if not p or bad or len(p) > 900:
            fallbacks += 1
            p = plain_item(x)
        out.append(f"{i}. {p}")
    return out, fallbacks


def plain_item(x: dict) -> str:
    return x["headline"] + (f" ({x['credit']})" if x.get("credit") else "")


# ----------------------------------------------------------------------------
# Compose
# ----------------------------------------------------------------------------
def compose(edition: str, stories: list[dict], markets: list[str], now: float, token: str | None) -> dict:
    from zoneinfo import ZoneInfo
    ed = EDITIONS[edition]
    local = datetime.fromtimestamp(now, ZoneInfo(ed["tz"]))
    day = local.strftime("%A, %d %B %Y")
    head = f"{ed['title']} ({local:%d %b})"
    items, mode, fallbacks = [f"{i}. {plain_item(x)}" for i, x in enumerate(stories, 1)], "list", 0
    if token and config.DAILY_RECAP_AI:
        prompt = build_prompt(stories, markets, day)
        try:
            items, fallbacks = checked_paragraphs(ai_write(prompt, token), stories, prompt)
            mode = "ai"
        except Exception as e:  # noqa: BLE001
            print(f"  ~ daily recap: {e} - posting the plain list")
    body = [head, "", "Here's the full recap:", ""]
    if markets:
        body += ["📊 At the close:"] + markets + [""]
    body += ["\n\n".join(items), "", "Automated recap of confirmed headlines. Not financial advice.",
             " ".join(ed["tags"])]
    full = "\n".join(body)
    short = head + "\n" + ("\n".join(markets[:4]) + "\n" if markets else "") + \
        f"{len(stories)} stories today. Full recap on Telegram: t.me/{config.BRAND_HANDLE.lstrip('@')}"
    return {"text": full, "short": short[:480], "mode": mode, "fallbacks": fallbacks, "count": len(stories)}


def split_for_telegram(text: str, limit: int = 4000) -> list[str]:
    chunks, cur = [], ""
    for block in text.split("\n\n"):
        if len(cur) + len(block) + 2 > limit and cur:
            chunks.append(cur.rstrip())
            cur = ""
        cur += block + "\n\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks
