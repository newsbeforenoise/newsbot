"""
News Before Noise - free global-markets squawk bot (First Squawk style).

Every run (every 5 minutes on GitHub Actions):
  1. Reads ~45 RSS feeds + official central-bank / statistics feeds.
  2. Confirms stories: 3 independent owners, or 1 official source.
  3. Adds live price alerts (indices, FX, commodities, crypto).
  4. Posts short Title Case headlines to Threads, Bluesky, Telegram, Mastodon, Discord.
  5. Sends you a one-tap "Post on X" link on Telegram.

Uses only the Python standard library - nothing to install.

Environment variables (set as GitHub Secrets / Variables):
  THREADS_ACCESS_TOKEN   long-lived Threads token
  THREADS_USER_ID        your Threads user id (or leave empty to use "me")
  TELEGRAM_BOT_TOKEN     from @BotFather
  TELEGRAM_CHAT_ID       your private chat id with the bot (X one-tap links)
  TELEGRAM_CHANNEL_ID    @YourChannel (public channel, auto-posts)
  BLUESKY_HANDLE / BLUESKY_APP_PASSWORD, MASTODON_INSTANCE / MASTODON_TOKEN, DISCORD_WEBHOOK_URL
  FB_PAGE_ID / FB_PAGE_TOKEN (Facebook Page), IG_USER_ID (Instagram, uses the Page token)
  BOT_ENABLED            "false" = kill switch (does nothing)
  DRY_RUN                "true"  = print what it would post, post nothing
"""

from __future__ import annotations

import email.utils
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import extras  # noqa: E402
import images  # noqa: E402
import prices  # noqa: E402
import recap  # noqa: E402
import daily_recap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
ITEMS_FILE = STATE_DIR / "items.json"
POSTED_FILE = STATE_DIR / "posted.json"
PRICES_FILE = STATE_DIR / "prices.json"
PREVIEW_DIR = ROOT / "previews"
DIGEST_FILE = STATE_DIR / "digest.json"
EXTRAS_FILE = STATE_DIR / "extras.json"     # market bells / calendar bookkeeping
STATS_FILE = STATE_DIR / "stats.json"       # errors & carousels for the daily report
RECAP_FILE = STATE_DIR / "recap.json"       # headline log for the daily reel / weekly recap

USER_AGENT = "Mozilla/5.0 (compatible; NewsHeadlineBot/1.0)"
ATOM = "{http://www.w3.org/2005/Atom}"

STOPWORDS = set("""
a an the and or but if of on in at to for from by with as is are was were be been being
it its this that these those he she they them his her their we our you your i me my
not no yes new news after before over under into about against amid says said say
will would can just more most than then also up down out off again still now today
first last top big how why what who when where which while report reports update
breaking latest live day week year years month amid set sets get gets got make makes
""".split())

SUFFIXES = ("ations", "ation", "ings", "ing", "ed", "es", "s")

KNOWN_OUTLETS = {x.lower() for x in list(config.OWNER_LABELS.values()) + [f["name"] for f in config.FEEDS] + [
    "Reuters", "AP", "Associated Press", "AFP", "Bloomberg", "Bloomberg.com", "The Wall Street Journal",
    "WSJ", "Financial Times", "FT", "CNBC", "CNN", "CNN Business", "BBC", "BBC News", "The Guardian",
    "Guardian", "NPR", "Al Jazeera", "Axios", "Politico", "Forbes", "Fortune", "Barron's", "MarketWatch",
    "Yahoo Finance", "Yahoo", "Fox Business", "Fox News", "Business Insider", "Nikkei Asia", "Nikkei",
    "South China Morning Post", "SCMP", "The Japan Times", "The Straits Times", "Economic Times",
    "The Economic Times", "ET", "ETMarkets", "Times of India", "The Times of India", "The Hindu",
    "BusinessLine", "Hindustan Times", "Mint", "Livemint", "Business Standard", "Moneycontrol",
    "NDTV", "NDTV Profit", "Indian Express", "The Indian Express", "CoinDesk", "Cointelegraph",
    "OilPrice.com", "Investing.com", "Seeking Alpha", "FXStreet", "DW", "France 24", "Euronews",
    "Sky News", "The Telegraph", "The Independent", "Le Monde", "Deutsche Welle", "Kyodo News",
]}


# ----------------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------------
def clean_headline(title: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", title or ""))
    t = re.sub(r"\s+", " ", t).strip()
    # drop " - Reuters" / " | CNBC" style suffixes, but only for known outlet names
    m = re.search(r"\s+[\|\-–—:]\s+([^|\-–—]{2,40})$", t)
    if m and m.group(1).strip().lower().rstrip(".") in KNOWN_OUTLETS:
        t = t[: m.start()]
    # drop leading labels
    t = re.sub(r"^(breaking( news)?|exclusive|update|just in)\s*[:\-–—]\s*", "", t, flags=re.I)
    return t.strip(" .")


def stem(word: str) -> str:
    for suf in SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return word


def key_words(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9&]+", title.lower())
    return {stem(w) for w in words if w not in STOPWORDS and (len(w) > 2 or w.isdigit())}


def is_blocked(title: str) -> bool:
    low = f" {title.lower()} "
    # "since May", "in May 2026", "May 15": the month, not the word "may"
    low = re.sub(r"\b(in|since|from|until|till|by|of|last|this|next|early|late|mid|end)\s+may\b", r"\1 month", low)
    low = re.sub(r"\bmay\s+(?=\d)", "month ", low)
    if title.startswith("May "):
        low = " month " + low[5:]
    plain = title.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    low = low.replace("’", "'").replace("‘", "'")
    if plain.lstrip("'\" ").startswith(tuple(config.BLOCKED_STARTS)):
        return True
    # TV/podcast soundbites: "Anthropic's Valuation Seems Justified: Thakker"
    if re.search(r":\s+[A-Z][\w.'-]*(?:'s)?(?:\s+[A-Z][\w.'-]*){0,2}$", plain) and not re.search(r"\d", plain.split(":")[-1]):
        return True
    return any(p in low for p in config.BLOCKED_PHRASES)


def on_topic(title: str, keywords: list[str]) -> bool:
    return _mentions(title, keywords)


US_RE = re.compile(r"(?<![A-Za-z])(U\.S\.A?\.?|USA|US)(?![A-Za-z])")


def _word_pos(low: str, w: str) -> int:
    """Position of word/phrase w in lowercase text, or -1. Single words match whole words."""
    if " " in w or "&" in w or "-" in w or "/" in w:
        return low.find(w)
    m = re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", low)
    return m.start() if m else -1


def _mentions(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(_word_pos(low, w) >= 0 for w in words)


def _mask_analyst_firms(low: str) -> str:
    """'citi sees romanian carry...' -> the firm is giving a view, so its name shouldn't add 🇺🇸."""
    verbs = set(getattr(config, "ANALYST_VERBS", []))
    for firm in sorted(getattr(config, "ANALYST_FIRMS", []), key=len, reverse=True):
        pos = _word_pos(low, firm)
        if pos < 0:
            continue
        after = re.findall(r"[a-z']+", low[pos + len(firm):])[:2]
        if after and (after[0] in verbs or after[0] in ("'s", "s") and len(after) > 1 and after[1] in verbs):
            low = low[:pos] + " " * len(firm) + low[pos + len(firm):]
    return low


def detect_countries(text: str) -> list[str]:
    """Country codes mentioned in the text, in order of first appearance. An analyst firm only
    giving a view ('Citi Sees Romanian...') doesn't count when another country is named."""
    masked = _detect_countries(text, _mask_analyst_firms(text.lower()))
    return masked or _detect_countries(text, text.lower())


def _detect_countries(text: str, low: str) -> list[str]:
    found = []
    for code, d in config.COUNTRIES.items():
        positions = [p for p in (_word_pos(low, w) for w in d["words"]) if p >= 0]
        if code == "US":
            m = US_RE.search(text)
            if m:
                positions.append(m.start())
        if positions:
            found.append((min(positions), code))
    return [c for _, c in sorted(found)]


def flags_for(codes: list[str]) -> str:
    if not config.SHOW_FLAGS:
        return ""
    return "".join(config.COUNTRIES[c]["flag"] for c in codes[: config.MAX_FLAGS]) or config.DEFAULT_FLAG


def camel_tag(phrase: str) -> str:
    return "#" + "".join(w[:1].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", phrase))


def trending_terms() -> list[str]:
    """Today's trending searches from Google Trends' free RSS."""
    if not config.USE_TRENDING:
        return []
    terms = []
    for raw in fetch_all(config.TRENDS_FEEDS).values():
        if raw:
            terms += [e["title"] for e in parse_feed(raw) if e["title"]]
    return terms


def hashtags_for(headline: str, all_text: str, countries: list[str], trends: list[str],
                 priority: int = 3) -> list[str]:
    """Best-first list of hashtags for a story."""
    tags: list[str] = []
    # 1. specific topic tags found in the chosen headline, then in other outlets' headlines
    for text in (headline, all_text):
        for tag, words in config.HASHTAG_RULES:
            if _mentions(text, words):
                tags.append(tag)
    # 2. a trending search that appears in the headline (all its words present)
    head_toks = set(re.findall(r"[a-z0-9]+", headline.lower()))
    for t in trends:
        words = re.findall(r"[a-z0-9]+", t.lower())
        if 0 < len(words) <= 3 and len(t) <= 25 and all(w in head_toks for w in words) \
                and not all(w in STOPWORDS for w in words):
            tags.insert(1 if tags else 0, camel_tag(t))
            break
    # 3. countries (headline order), 4. broad category
    tags += [config.COUNTRIES[c]["tag"] for c in countries]
    tags.append(config.MARKET_TAG if priority >= 3 else config.GEO_TAG)
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen and len(t) > 2:
            seen.add(t.lower())
            out.append(t)
    return out


def threads_topic(tags: list[str]) -> str:
    """Threads topic tag: no '#', no '.' or '&', max 50 chars."""
    for t in tags:
        clean = t.lstrip("#").replace(".", "").replace("&", "")
        if clean and len(clean) <= 50:
            return clean
    return ""


GENERIC_WORDS: set[str] = set()


def _generic() -> set[str]:
    if not GENERIC_WORDS:
        GENERIC_WORDS.update(key_words(" ".join(config.GENERIC_WORDS)))
    return GENERIC_WORDS


def similar(a: set[str], b: set[str]) -> bool:
    """Same story? Needs enough shared key words AND enough shared *specific* words
    (names, places, numbers) - generic words like stocks/oil/rise can't confirm a story alone."""
    if not a or not b:
        return False
    shared = a & b
    specific = shared - _generic()
    return (len(shared) >= config.MIN_SHARED_WORDS
            and len(shared) / min(len(a), len(b)) >= config.MIN_OVERLAP
            and len(specific) >= config.MIN_SPECIFIC_WORDS)


# ----------------------------------------------------------------------------
# Feeds
# ----------------------------------------------------------------------------
def fetch_all(urls: list[str]) -> dict[str, bytes | None]:
    """Fetches many URLs at the same time (much faster than one by one)."""
    with ThreadPoolExecutor(max_workers=16) as pool:
        return dict(zip(urls, pool.map(fetch, urls)))


def fetch(url: str, timeout: int = 15) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f"  ! feed failed: {url} ({e})")
        return None


def parse_date(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return email.utils.parsedate_to_datetime(text).timestamp()
    except Exception:  # noqa: BLE001
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa: BLE001
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def clean_summary(text: str) -> str:
    """Plain-text article summary from an RSS description (HTML removed, max 600 chars)."""
    if not text:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(text)))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(Continue reading|Read more|The post .* appeared first on).*$", "", text, flags=re.I).strip()
    return text[:600]


def parse_feed(raw: bytes) -> list[dict]:
    """Returns [{title, link, published}] from RSS 2.0, RSS 1.0 (RDF) or Atom.
    Falls back to a forgiving regex parser when the XML is broken."""
    out = []
    try:
        root = ET.fromstring(raw)
        for el in root.iter():
            if _local(el.tag) not in ("item", "entry"):
                continue
            title = link = date = summary = ""
            for ch in el:
                name = _local(ch.tag)
                if name == "title":
                    title = "".join(ch.itertext()).strip()
                elif name in ("description", "summary", "encoded", "content") and not summary:
                    summary = "".join(ch.itertext()).strip()
                elif name == "link" and not link:
                    link = (ch.text or ch.get("href") or "").strip()
                elif name in ("pubdate", "published", "updated", "date") and not date:
                    date = (ch.text or "").strip()
            out.append({"title": title, "link": link, "published": parse_date(date),
                        "summary": clean_summary(summary)})
        return out
    except ET.ParseError:
        pass
    text = raw.decode("utf-8", "ignore")
    for block in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", text, re.S | re.I):
        t = re.search(r"<title[^>]*>(.*?)</title>", block, re.S | re.I)
        d = re.search(r"<(?:pubDate|published|updated|dc:date)[^>]*>(.*?)</", block, re.S | re.I)
        if t:
            title = re.sub(r"^<!\[CDATA\[|\]\]>$", "", t.group(1).strip())
            out.append({"title": title, "link": "", "published": parse_date(d.group(1).strip() if d else "")})
    return out


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return default


def save(path: Path, data) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


# ----------------------------------------------------------------------------
# Core logic (pure - easy to test)
# ----------------------------------------------------------------------------
def collect(items: dict, feed: dict, entries: list[dict], now: float) -> int:
    """Adds new feed entries to the items store. Returns how many were new."""
    added = 0
    for e in entries:
        title = clean_headline(e["title"])
        if not title:
            continue
        iid = hashlib.sha1(f'{feed["owner"]}|{title.lower()}'.encode()).hexdigest()[:16]
        if iid in items:
            continue
        items[iid] = {
            "title": title,
            "outlet": feed["name"],
            "owner": feed["owner"],
            "published": e.get("published"),
            "seen": now,
            "words": sorted(key_words(title)),
            "official": bool(feed.get("official")),
            "summary": e.get("summary", ""),
        }
        added += 1
    return added


def source_credit(group: list[dict], best: dict | None = None) -> list[str]:
    """Owner labels, one per owner: the outlet whose headline we use first (like First
    Squawk's "– FT"), then official sources, then whoever reported it first."""
    out = []
    ordered = sorted(group, key=lambda g: (g is not best, not g.get("official"),
                                           g.get("published") or g["seen"], g["seen"]))
    for g in ordered:
        label = config.OWNER_LABELS.get(g["owner"], g["outlet"])
        if label not in out:
            out.append(label)
    return out


def has_signal(words: set[str]) -> bool:
    return any(any(ch.isdigit() for ch in w) or any(w.startswith(sig) for sig in config.FOLLOWUP_SIGNALS)
               for w in words)


_PLACE_STEMS: set[str] = set()
_BIG = ("US", "CN", "IN", "EU", "GB", "JP", "DE", "FR", "RU", "UA", "IR", "IL")   # in the news all day


def _places() -> set[str]:
    """Names of the less-common countries/places (Greenland, Senegal, Romania...)."""
    if not _PLACE_STEMS:
        for code, d in config.COUNTRIES.items():
            if code not in _BIG:
                _PLACE_STEMS.update(stem(w) for w in d["words"] if " " not in w)
    return _PLACE_STEMS


def same_topic(a: set[str], b: set[str]) -> bool:
    """Looser than similar(), for reworded repeats: both headlines name the same less-common
    place AND share at least one more specific word. ('Trump's Greenland Deal To Take Effect' vs
    'Denmark ... Approves US Military Expansion Deal In Greenland'.) Tested on a day of real
    headlines: catches the Greenland pair, leaves different Trump/Anthropic/APEC stories alone."""
    shared = (a & b) - _generic()
    return len(shared) >= 2 and bool(shared & _places())


def followup_parent(related: list[dict], posted: list[dict], words: set[str], now: float) -> str | None:
    """If this headline is a genuine update to a posted story, return that story's id."""
    if not config.FOLLOWUPS:
        return None
    for p in related:
        sid = p.get("story_id")
        if not sid:
            continue
        thread = [q for q in posted if q.get("story_id") == sid]
        first_ts = min(q["ts"] for q in thread)
        if now - first_ts > config.FOLLOWUP_HOURS * 3600 or len(thread) > config.MAX_FOLLOWUPS:
            return None
        known = set().union(*(set(q["words"]) for q in thread))
        new = words - known
        if len(new) >= config.FOLLOWUP_MIN_NEW_WORDS and has_signal(new):
            return sid
        return None
    return None


def find_stories(items: dict, posted: list, now: float, trends: list[str] | None = None) -> list[dict]:
    """Groups items into stories confirmed by >= MIN_SOURCES different owners."""
    fresh_cutoff = now - config.FRESH_HOURS * 3600
    already_used = {i for p in posted for i in p.get("item_ids", [])}
    pool = []
    for iid, it in items.items():
        if iid in already_used or it.get("baseline"):
            continue
        ts = it.get("published") or it["seen"]
        if ts < fresh_cutoff or it["seen"] < fresh_cutoff:
            continue
        if is_blocked(it["title"]):
            continue
        if it.get("official") and (not on_topic(it["title"], config.OFFICIAL_KEYWORDS)
                                   or on_topic(it["title"], config.OFFICIAL_SKIP)):
            continue  # routine official notice
        pool.append({**it, "id": iid, "wset": set(it["words"])})

    stories, used = [], set()

    # newest first so we react to the latest wording
    pool.sort(key=lambda x: x["seen"], reverse=True)
    for anchor in pool:
        if anchor["id"] in used:
            continue
        group = [anchor] + [
            o for o in pool
            if o["id"] != anchor["id"] and o["id"] not in used and similar(anchor["wset"], o["wset"])
        ]
        owners = {g["owner"] for g in group}
        official = [g for g in group if g.get("official")]
        trusted = [g for g in group if g["owner"] in config.TRUSTED_OWNERS
                   and g["seen"] >= now - config.TRUSTED_MAX_AGE_MINUTES * 60
                   and (g.get("published") or now) >= now - 2 * config.TRUSTED_MAX_AGE_MINUTES * 60]
        if len(owners) < config.MIN_SOURCES and not official and not trusted:
            continue
        for g in group:
            used.add(g["id"])
        # official wording wins; otherwise the most specific (has numbers), then shortest
        best = official[0] if official else min(
            [g for g in group if len(g["title"]) <= config.MAX_HEADLINE_CHARS] or group,
            key=lambda g: (not re.search(r"\d", g["title"]), len(g["title"])))
        all_text = " | ".join(g["title"] for g in group)
        countries = detect_countries(best["title"]) or detect_countries(all_text)
        focus = any(c in config.FOCUS_COUNTRIES for c in countries)
        if config.REQUIRE_FOCUS_COUNTRY and not focus:
            continue
        if official or any(on_topic(g["title"], config.MARKET_KEYWORDS) for g in group):
            priority = 3          # tier 1: markets / official releases
        elif len(countries) >= 2 or any(on_topic(g["title"], config.GEO_KEYWORDS) for g in group):
            priority = 2          # tier 2: geopolitics & politics
        else:
            priority = 1          # tier 3: general news
        if priority == 1 and not config.INCLUDE_GENERAL_NEWS:
            continue
        union_words = set().union(*(g["wset"] for g in group))
        best_words = key_words(best["title"])
        related = [p for p in posted
                   if similar(anchor["wset"], set(p["words"])) or similar(union_words & set(p["words"]), set(p["words"]))
                   or (not p.get("is_price") and not p.get("kind")
                       and p["ts"] > now - getattr(config, "SAME_TOPIC_HOURS", 0) * 3600
                       and same_topic(best_words, set(p["words"])))]
        followup_of = None
        if related:
            followup_of = followup_parent(related, posted, best_words, now)
            if not followup_of:
                continue  # same story, nothing new -> skip
        story_id = followup_of or anchor["id"]
        stories.append({
            "text": best["title"],
            "flags": flags_for(countries),
            "countries": countries,
            "tags": hashtags_for(best["title"], all_text, countries, trends or [], priority),
            "priority": priority,
            "focus": focus,
            "words": sorted(union_words),
            "sources": sorted({g["outlet"] for g in group}),
            "credit": source_credit(group, best),
            "item_ids": [g["id"] for g in group],
            "story_id": story_id,
            "followup": bool(followup_of),
            "official": bool(official),
            "all_text": all_text,
            "summary": max((g.get("summary", "") for g in group), key=len, default=""),
        })
    # tier 1 first, then tier 2, then tier 3; US/India first within a tier
    stories.sort(key=lambda s: (s["priority"], s["focus"]), reverse=True)
    return stories


# ----------------------------------------------------------------------------
# Posting
# ----------------------------------------------------------------------------
def http_post(url: str, params: dict | None = None, json_body: dict | None = None,
              headers: dict | None = None) -> dict:
    h = {"User-Agent": USER_AGENT, **(headers or {})}
    if json_body is not None:
        data = json.dumps(json_body).encode()
        h["Content-Type"] = "application/json"
    else:
        data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    except urllib.error.HTTPError as e:  # show the platform's reason (never the URL: it can hold tokens)
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"network error: {e.reason}") from None
    try:
        return json.loads(body or b"{}")
    except ValueError:
        return {}


def env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


# --- Image cards on every platform ---------------------------------------------
def wants_card(name: str) -> bool:
    return name in config.CARD_PLATFORMS and images.available()


def ensure_image_url(p: dict) -> str:
    """Public URL of the card (needed by Threads/Instagram). Hosted on the Facebook Page."""
    if not p.get("image_url") and env("FB_PAGE_ID") and env("FB_PAGE_TOKEN"):
        fb_upload(p, published=False)
    return p.get("image_url", "")


def with_card(name: str, p: dict, card_fn, text_fn) -> str:
    """Posts the image card; if anything about the image fails, posts plain text instead."""
    if wants_card(name):
        try:
            return card_fn()
        except Exception as e:  # noqa: BLE001
            print(f"    ~ {name}: image failed ({e}), posting text instead")
    return text_fn()


# --- Threads (card via public URL, or text) + 1 topic tag ---------------------
def post_threads(p: dict) -> str:
    token = env("THREADS_ACCESS_TOKEN")
    base = f"https://graph.threads.net/v1.0/{env('THREADS_USER_ID') or 'me'}"

    def publish(params: dict) -> str:
        params.update({"text": p["plain"][:500], "access_token": token})
        if p["topic"]:
            params["topic_tag"] = p["topic"]
        cid = http_post(f"{base}/threads", params)["id"]
        for _ in range(10):  # wait until Threads has processed the container
            time.sleep(3)
            st = http_get_json(f"https://graph.threads.net/v1.0/{cid}", {"fields": "status", "access_token": token})
            if st.get("status") in ("FINISHED", None):
                break
            if st.get("status") == "ERROR":
                raise RuntimeError("Threads could not process the post")
        return http_post(f"{base}/threads_publish", {"creation_id": cid, "access_token": token}).get("id", "")

    def card() -> str:
        url = ensure_image_url(p)
        if not url:
            raise RuntimeError("no public image URL (add the Facebook Page secrets to enable Threads images)")
        return publish({"media_type": "IMAGE", "image_url": url})

    return with_card("Threads", p, card, lambda: publish({"media_type": "TEXT"}))


# --- Bluesky (card as an uploaded image + clickable hashtags) -----------------
_bsky_session: dict = {}


def bluesky_facets(text: str) -> list[dict]:
    """Makes #hashtags clickable. Bluesky wants UTF-8 byte offsets."""
    facets = []
    for m in re.finditer(r"(?<!\w)#([A-Za-z][A-Za-z0-9_]*)", text):
        start = len(text[: m.start()].encode())
        end = len(text[: m.end()].encode())
        facets.append({"index": {"byteStart": start, "byteEnd": end},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return facets


def http_post_bytes(url: str, data: bytes, headers: dict) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}") from None


def post_bluesky(p: dict) -> str:
    host = env("BLUESKY_PDS") or "https://bsky.social"
    if not _bsky_session:  # one login per run (Bluesky allows 300 logins/day)
        _bsky_session.update(http_post(f"{host}/xrpc/com.atproto.server.createSession", json_body={
            "identifier": env("BLUESKY_HANDLE"), "password": env("BLUESKY_APP_PASSWORD")}))
    auth = {"Authorization": f"Bearer {_bsky_session['accessJwt']}"}
    text = p["tagged"] if len(p["tagged"]) <= 300 else p["plain"][:300]
    record = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
              "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    facets = bluesky_facets(text)
    if facets:
        record["facets"] = facets

    def create(rec: dict) -> str:
        return http_post(f"{host}/xrpc/com.atproto.repo.createRecord", headers=auth, json_body={
            "repo": _bsky_session["did"], "collection": "app.bsky.feed.post", "record": rec}).get("uri", "")

    def card() -> str:
        blob = http_post_bytes(f"{host}/xrpc/com.atproto.repo.uploadBlob", card_image(p),
                               {**auth, "Content-Type": "image/jpeg"})["blob"]
        return create({**record, "embed": {"$type": "app.bsky.embed.images", "images": [{
            "alt": p["alt"], "image": blob, "aspectRatio": {"width": images.W, "height": images.H}}]}})

    return with_card("Bluesky", p, card, lambda: create(record))


# --- Telegram public channel (photo + caption, or text) -----------------------
def sent_but_unconfirmed(err: Exception) -> bool:
    """A timeout means the request reached the server but no answer came back in time.
    Telegram still delivers these (seen 19 Nov: posts arrived ~5 min late), so retrying
    would post the same headline twice."""
    return isinstance(err, TimeoutError) or "timed out" in str(err).lower()


def post_telegram_channel(p: dict) -> str:
    api = f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
    chat = env("TELEGRAM_CHANNEL_ID")

    def guarded(send) -> str:
        try:
            return send()
        except Exception as e:  # noqa: BLE001
            if sent_but_unconfirmed(e):
                print("    ~ Telegram: no reply in time - it usually still delivers, so NOT retrying (no duplicate)")
                return "unconfirmed"
            raise

    def card() -> str:
        r = http_post_file(f"{api}/sendPhoto", {"chat_id": chat, "caption": p["tagged"][:1024]},
                           "photo", "card.jpg", card_image(p))
        return str(r.get("result", {}).get("message_id", ""))

    def text() -> str:
        r = http_post(f"{api}/sendMessage", {"chat_id": chat, "text": p["tagged"], "disable_web_page_preview": "true"})
        return str(r.get("result", {}).get("message_id", ""))

    return with_card("Telegram", p, lambda: guarded(card), lambda: guarded(text))


# --- Mastodon (media upload + status, or text) --------------------------------
def post_mastodon(p: dict) -> str:
    host = env("MASTODON_INSTANCE").rstrip("/")
    auth = {"Authorization": f"Bearer {env('MASTODON_TOKEN')}"}
    status = {"status": p["tagged"][:500], "visibility": "public", "language": "en"}

    def send(extra: dict) -> str:
        return http_post(f"{host}/api/v1/statuses", {**status, **extra}, headers={
            **auth, "Idempotency-Key": hashlib.sha1(p["tagged"].encode()).hexdigest()}).get("id", "")

    def card() -> str:
        media = http_post_file(f"{host}/api/v2/media", {"description": p["alt"]}, "file", "card.jpg",
                               card_image(p), headers=auth)
        time.sleep(2)  # give the server a moment to process the image
        return send({"media_ids[]": media["id"]})

    return with_card("Mastodon", p, card, lambda: send({}))


# --- Discord (webhook with the card attached, or text) ------------------------
def post_discord(p: dict) -> str:
    url = env("DISCORD_WEBHOOK_URL")

    def card() -> str:
        http_post_file(url, {"payload_json": json.dumps({"content": p["tagged"][:2000]})},
                       "files[0]", "card.jpg", card_image(p))
        return "ok"

    def text() -> str:
        http_post(url, json_body={"content": p["tagged"][:2000]})
        return "ok"

    return with_card("Discord", p, card, text)


# --- Facebook Page + Instagram (image cards) ---------------------------------
def http_get_json(url: str, params: dict) -> dict:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}") from None


def http_post_file(url: str, fields: dict, file_field: str, filename: str, data: bytes,
                   headers: dict | None = None, content_type: str = "image/jpeg") -> dict:
    """multipart/form-data upload using only the standard library."""
    boundary = "----nbn" + hashlib.sha1(data[:64] + str(time.time()).encode()).hexdigest()
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
             f"Content-Type: {content_type}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": USER_AGENT, "Content-Type": f"multipart/form-data; boundary={boundary}", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}") from None


def graph(path: str) -> str:
    return f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{path}"


def card_image(p: dict) -> bytes:
    if "image" not in p:
        if not images.available():
            raise RuntimeError("Pillow not installed - image cards unavailable")
        p["image"] = images.render(p["story"], p["headline"], p["credit_main"])
    return p["image"]


def fb_upload(p: dict, published: bool) -> str:
    """Uploads the card to the Facebook Page; stores its public image URL in p for Instagram."""
    token = env("FB_PAGE_TOKEN")
    r = http_post_file(graph(f"{env('FB_PAGE_ID')}/photos"),
                       {"message": p["social_caption"], "published": "true" if published else "false",
                        "access_token": token}, "source", "card.jpg", card_image(p))
    photo_id = r.get("id", "")
    imgs = http_get_json(graph(photo_id), {"fields": "images", "access_token": token}).get("images", [])
    if imgs:
        p["image_url"] = max(imgs, key=lambda i: i.get("width", 0))["source"]
    return r.get("post_id") or photo_id


def post_facebook(p: dict) -> str:
    return fb_upload(p, published=True)


def post_instagram(p: dict) -> str:
    token = env("INSTAGRAM_ACCESS_TOKEN") or env("FB_PAGE_TOKEN")
    if not p.get("image_url"):          # Facebook posting off/failed: host the image unpublished
        fb_upload(p, published=False)
    if not p.get("image_url"):
        raise RuntimeError("could not get a public image URL from Facebook")
    ig = env("IG_USER_ID")
    container = http_post(graph(f"{ig}/media"), {"image_url": p["image_url"], "caption": p["ig_caption"],
                                                 "access_token": token})["id"]
    for _ in range(10):                 # wait until Instagram has processed the image
        status = http_get_json(graph(container), {"fields": "status_code", "access_token": token})
        if status.get("status_code") in ("FINISHED", None):
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError("Instagram could not process the image")
        time.sleep(3)
    return http_post(graph(f"{ig}/media_publish"), {"creation_id": container, "access_token": token}).get("id", "")


IMAGE_PLATFORMS = {"Facebook", "Instagram"}


# name -> (function, secrets it needs). A platform is ON when its secrets exist.
PLATFORMS = {   # Facebook first: its public image URL is reused by Instagram and Threads
    "Facebook":  (post_facebook,         ["FB_PAGE_ID", "FB_PAGE_TOKEN"]),
    "Instagram": (post_instagram,        ["IG_USER_ID", "FB_PAGE_ID", "FB_PAGE_TOKEN"]),
    "Threads":   (post_threads,          ["THREADS_ACCESS_TOKEN"]),
    "Bluesky":   (post_bluesky,          ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"]),
    "Telegram":  (post_telegram_channel, ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"]),
    "Mastodon":  (post_mastodon,         ["MASTODON_INSTANCE", "MASTODON_TOKEN"]),
    "Discord":   (post_discord,          ["DISCORD_WEBHOOK_URL"]),
}


def enabled_platforms() -> list[str]:
    on = [n for n, (_, keys) in PLATFORMS.items() if all(env(k) for k in keys)]
    if not config.FACEBOOK_PUBLISH and "Facebook" in on:
        on.remove("Facebook")
    if not images.available():
        if IMAGE_PLATFORMS & set(on):
            print("  ! Pillow not installed: skipping Facebook/Instagram, other platforms post text")
        on = [n for n in on if n not in IMAGE_PLATFORMS]
    return on


def platform_wants(name: str, story: dict, posted: list, now: float) -> bool:
    """Image platforms only get important stories, within their own daily cap.
    Digest platforms get nothing per story: they post once an hour (see run_digest)."""
    if name in config.DIGEST_PLATFORMS:
        return False
    if name == "Threads":                      # new accounts get "action is blocked" if they post too fast
        if story["priority"] < config.THREADS_MIN_PRIORITY and not story.get("breaking"):
            return False
        return threads_ok(posted, now)
    if name not in IMAGE_PLATFORMS:
        return True
    if story["priority"] < config.IMAGE_MIN_PRIORITY:
        return False
    used = sum(1 for q in posted if q["ts"] > now - 86400 and name in q.get("platforms", []))
    return used < config.IMAGE_DAILY_LIMITS.get(name, 25)


def threads_blocked_until(now: float) -> float:
    """When Threads says "we restrict certain activity" (subcode 2207051), every retry keeps the
    block alive. Stay completely quiet on Threads for THREADS_COOLDOWN_HOURS after the last one."""
    last = max((f["ts"] for f in STATS.get("fails", [])
                if f.get("platform", "").startswith("Threads") and "2207051" in f.get("error", "")), default=0)
    return last + config.THREADS_COOLDOWN_HOURS * 3600 if last else 0


def threads_ok(posted: list, now: float) -> bool:
    """Threads pacing: cooldown after a block, a minimum gap, an hourly and a daily cap."""
    if now < threads_blocked_until(now):
        return False
    times = [q["ts"] for q in posted if "Threads" in q.get("platforms", [])]
    if any(t > now - config.THREADS_MIN_GAP_MINUTES * 60 for t in times):
        return False
    if sum(1 for t in times if t > now - 3600) >= config.THREADS_MAX_PER_HOUR:
        return False
    return sum(1 for t in times if t > now - 86400) < config.THREADS_DAILY_MAX


# --- Hourly digest: one carousel per hour on Facebook / Instagram ------------
def _tz():
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(config.DIGEST_TIMEZONE)
    except Exception:  # noqa: BLE001
        return timezone.utc


def _window_start(ts: float) -> datetime:
    m = max(1, int(getattr(config, "DIGEST_WINDOW_MINUTES", 60)))
    dt = datetime.fromtimestamp(ts, _tz()).replace(second=0, microsecond=0)
    mins = (dt.hour * 60 + dt.minute) // m * m
    return dt.replace(hour=mins // 60, minute=mins % 60)


def hour_key(ts: float) -> str:
    """Key of the roundup window a time falls in (every DIGEST_WINDOW_MINUTES, default 30)."""
    return _window_start(ts).strftime("%Y-%m-%d %H:%M")


def hour_window(first_ts: float, last_ts: float) -> str:
    """'14:00–14:30 EST' (or '13:30–14:30 EST' if several windows were batched)."""
    a = _window_start(first_ts)
    b = _window_start(last_ts) + timedelta(minutes=max(1, int(getattr(config, "DIGEST_WINDOW_MINUTES", 60))))
    return f"{a:%H:%M}–{b:%H:%M} {a.tzname() or config.DIGEST_TIMEZONE}"


def queue_for_digest(p: dict, story: dict, now: float) -> dict:
    return {"ts": now, "headline": p["headline"], "credit": p["credit_main"], "plain": p["plain"],
            "words": list(story.get("words", [])),
            "tags": story.get("tags", []), "priority": story["priority"], "focus": story.get("focus", False),
            "story": {k: story.get(k) for k in ("priority", "countries", "followup", "is_price")}}


def platform_window(name: str) -> int:
    return int(getattr(config, "DIGEST_PLATFORM_WINDOWS", {}).get(name, getattr(config, "DIGEST_WINDOW_MINUTES", 60)))


def build_digest(items: list[dict], minutes: int | None = None, end_ts: float | None = None) -> dict:
    """Slides (JPEG bytes) + caption for one roundup carousel. `minutes` = this platform's
    roundup length (e.g. Instagram's 60 while the base window is 30)."""
    picked = sorted(items, key=lambda q: (q["priority"], q.get("focus", False), q["ts"]), reverse=True)
    cover = config.DIGEST_COVER and len(items) > 1
    picked = picked[: config.DIGEST_MAX_SLIDES - (1 if cover else 0)]
    base = int(getattr(config, "DIGEST_WINDOW_MINUTES", 60))
    if minutes and minutes != base:
        end = (_window_start(end_ts) if end_ts else
               _window_start(max(q["ts"] for q in items)) + timedelta(minutes=base))
        start = end - timedelta(minutes=minutes)
        window = f"{start:%H:%M}–{end:%H:%M} {start.tzname() or config.DIGEST_TIMEZONE}"
    else:
        window = hour_window(min(q["ts"] for q in items), max(q["ts"] for q in items))
    when = datetime.fromtimestamp(max(q["ts"] for q in items), _tz())
    slides = []
    if cover:
        slides.append(images.render_cover([q["headline"] for q in picked], window, len(items), when))
    for q in picked:
        slides.append(images.render(q["story"], q["headline"], q["credit"], when))
    from collections import Counter
    counts = Counter(t for q in items for t in q["tags"] if t not in (config.MARKET_TAG, config.GEO_TAG))
    tags = [t for t, _ in counts.most_common(config.MAX_HASHTAGS_INSTAGRAM - 1)] + [config.MARKET_TAG]
    mins = int(minutes or getattr(config, "DIGEST_WINDOW_MINUTES", 60))
    span = "this hour" if mins == 60 else f"last {mins} min"
    head = (f"🕐 Global markets {span} ({window})" if len(items) > 1 else picked[0]["plain"])
    promo = getattr(config, "TELEGRAM_PROMO", "")
    swipe = ("Swipe for every headline ➡️" if len(slides) >= len(items) else "Swipe for the top headlines ➡️")
    tail = " ".join(tags) + ("\n\n" + swipe if len(slides) > 1 else "") + "\nAutomated headline alerts. Not financial advice."
    # update 14: the caption lists EVERY headline that fits (slides are capped at DIGEST_MAX_SLIDES)
    ranked = sorted(items, key=lambda q: (q["priority"], q.get("focus", False), q["ts"]), reverse=True)
    budget = 2150 - len(head) - len(promo) - len(tail) - 60
    lines: list[str] = []
    for i, q in enumerate(ranked, 1):
        line = f"{i}. {q['plain']}"
        if sum(len(x) + 1 for x in lines) + len(line) > budget:
            break
        lines.append(line)
    more = len(items) - len(lines)
    if more > 0:
        lines.append(f"+{more} more on Telegram")
    caption = head + (f"\n{promo}" if promo else "") + "\n\n" + \
        ("\n".join(lines) + "\n\n" if len(items) > 1 else "") + tail
    slide_keys = ([f"cover|{window}"] if cover else []) + [headline_key(q["headline"]) for q in picked]
    return {"slides": slides, "slide_keys": slide_keys, "caption": caption[:2150], "window": window, "count": len(items),
            "picked": picked, "head": head, "tags": tags}


def threads_caption(dg: dict) -> str:
    """Threads allows 500 characters: the header plus as many headlines as fit."""
    picked = dg.get("picked", [])
    if len(picked) == 1:
        return picked[0]["plain"][:490]
    lines, out = [dg["head"], ""], 0
    for q in picked:
        line = "• " + q["plain"].rsplit(" – ", 1)[0]
        if len("\n".join(lines + [line])) > 440:
            break
        lines.append(line)
        out += 1
    more = dg["count"] - out
    lines += ["", (f"+{more} more ➡️ swipe" if more > 0 else "Swipe ➡️") + " · Not financial advice"]
    return "\n".join(lines)[:500]


def fb_photo(data: bytes, published: bool, message: str = "") -> tuple[str, str, str]:
    """Uploads one JPEG to the Page. Returns (photo_id, public_image_url, post_id)."""
    token = env("FB_PAGE_TOKEN")
    fields = {"published": "true" if published else "false", "access_token": token}
    if message:
        fields["message"] = message
    r = http_post_file(graph(f"{env('FB_PAGE_ID')}/photos"), fields, "source", "card.jpg", data)
    pid = r.get("id", "")
    imgs = http_get_json(graph(pid), {"fields": "images", "access_token": token}).get("images", [])
    url = max(imgs, key=lambda i: i.get("width", 0))["source"] if imgs else ""
    return pid, url, r.get("post_id", "")


CARD_CACHE: dict = {}   # headline key -> {"url", "photo_id", "used_fb", "ts"}; saved in digest.json


def _host_slides(dg: dict, need_ids: bool = False) -> list[str]:
    """Public URLs of all slides (uploaded to the Page unpublished). Each card is uploaded ONCE:
    Instagram and Threads reuse the URL Facebook already has (update 13.4 - halves the API calls
    that trigger 'Application request limit reached'). need_ids=True (Facebook's own multi-photo
    post) needs photos not yet attached to another Facebook post."""
    if dg.get("urls") and (not need_ids or dg.get("photo_ids")):
        return dg["urls"]
    keys = dg.get("slide_keys") or [None] * len(dg["slides"])
    ids, urls = [], []
    for data, key in zip(dg["slides"], keys):
        hit = CARD_CACHE.get(key) if key else None
        if hit and hit.get("url") and not (need_ids and hit.get("used_fb")):
            ids.append(hit.get("photo_id", ""))
            urls.append(hit["url"])
            continue
        pid, url, _ = fb_photo(data, published=False)
        ids.append(pid)
        urls.append(url)
        if key and url:
            CARD_CACHE[key] = {"url": url, "photo_id": pid, "used_fb": False, "ts": time.time()}
    dg["photo_ids"], dg["urls"] = ids, urls
    return dg["urls"]


def post_facebook_digest(dg: dict) -> str:
    if len(dg["slides"]) == 1:
        pid, url, post_id = fb_photo(dg["slides"][0], published=True, message=dg["caption"])
        dg.setdefault("urls", [url])
        return post_id or pid
    _host_slides(dg, need_ids=True)
    params = {"message": dg["caption"], "access_token": env("FB_PAGE_TOKEN")}
    for i, pid in enumerate(dg["photo_ids"]):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    pid = http_post(graph(f"{env('FB_PAGE_ID')}/feed"), params).get("id", "")
    for key in dg.get("slide_keys") or []:
        if key in CARD_CACHE:
            CARD_CACHE[key]["used_fb"] = True         # attached now; a later FB post needs a fresh upload
    return pid


def _ig_wait(container: str, token: str) -> None:
    """Waits until Instagram has processed a container. Images are usually ready in a few
    seconds, so wait first and check rarely: every check counts against the API call limit."""
    for _ in range(8):
        time.sleep(4)
        st = http_get_json(graph(container), {"fields": "status_code", "access_token": token}).get("status_code")
        if st in ("FINISHED", None):
            return
        if st == "ERROR":
            raise RuntimeError("Instagram could not process the media")
    raise RuntimeError("Instagram media still processing after 32 s")


def post_instagram_digest(dg: dict) -> str:
    token = env("INSTAGRAM_ACCESS_TOKEN") or env("FB_PAGE_TOKEN")
    ig = env("IG_USER_ID")
    urls = [u for u in _host_slides(dg) if u]
    if len(urls) != len(dg["slides"]):
        raise RuntimeError("could not get public image URLs from Facebook")
    urls = urls[: config.DIGEST_SLIDE_LIMITS.get("Instagram", 10)]
    if len(urls) == 1:
        container = http_post(graph(f"{ig}/media"), {"image_url": urls[0], "caption": dg["caption"],
                                                     "access_token": token})["id"]
    else:
        children = [http_post(graph(f"{ig}/media"), {"image_url": u, "is_carousel_item": "true",
                                                     "access_token": token})["id"] for u in urls]
        time.sleep(10)              # images process in a few seconds; checking each child costs calls
        _ig_wait(children[-1], token)
        container = http_post(graph(f"{ig}/media"), {"media_type": "CAROUSEL", "children": ",".join(children),
                                                     "caption": dg["caption"], "access_token": token})["id"]
    _ig_wait(container, token)
    return http_post(graph(f"{ig}/media_publish"), {"creation_id": container, "access_token": token}).get("id", "")


def _threads_wait(cid: str, token: str) -> None:
    for _ in range(8):
        time.sleep(4)
        st = http_get_json(f"https://graph.threads.net/v1.0/{cid}", {"fields": "status", "access_token": token})
        if st.get("status") in ("FINISHED", None):
            return
        if st.get("status") == "ERROR":
            raise RuntimeError("Threads could not process the media")
    raise RuntimeError("Threads media still processing after 32 s")


def post_threads_digest(dg: dict) -> str:
    """One Threads post per roundup: a swipeable carousel of the cards (up to 20) with the
    headlines in the text. Falls back to a text-only post if the images can't be hosted."""
    token = env("THREADS_ACCESS_TOKEN")
    base = f"https://graph.threads.net/v1.0/{env('THREADS_USER_ID') or 'me'}"
    text = threads_caption(dg)
    params = {"text": text, "access_token": token}
    topic = threads_topic(dg.get("tags", []))
    if topic:
        params["topic_tag"] = topic
    urls: list[str] = []
    if env("FB_PAGE_ID") and env("FB_PAGE_TOKEN"):
        try:
            urls = [u for u in _host_slides(dg) if u][: config.DIGEST_SLIDE_LIMITS.get("Threads", 20)]
        except Exception as e:  # noqa: BLE001
            print(f"    ~ Threads: images unavailable ({e}), posting text only")
    if len(urls) >= 2:
        children = [http_post(f"{base}/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true",
                                                  "access_token": token})["id"] for u in urls]
        for c in children:
            _threads_wait(c, token)
        params.update({"media_type": "CAROUSEL", "children": ",".join(children)})
    elif len(urls) == 1:
        params.update({"media_type": "IMAGE", "image_url": urls[0]})
    else:
        params["media_type"] = "TEXT"
    cid = http_post(f"{base}/threads", params)["id"]
    _threads_wait(cid, token)
    return http_post(f"{base}/threads_publish", {"creation_id": cid, "access_token": token}).get("id", "")


DIGEST_POSTERS = {"Facebook": post_facebook_digest, "Instagram": post_instagram_digest,
                  "Threads": post_threads_digest}

RATE_LIMIT_MARKERS = ('"code":4,', '"code":17,', '"code":32,', '"code":613,', "request limit",
                      "2207042", "2207051", "HTTP 429")


def is_rate_limit(err: Exception | str) -> bool:
    """Meta 'Application request limit reached' / 'too many calls' / publishing-cap errors.
    Retrying these never helps (and the post may already be live), so they are never retried."""
    text = str(err).replace(" ", "")
    return any(m.replace(" ", "") in text for m in RATE_LIMIT_MARKERS)


def digest_cooldown_until(name: str) -> float:
    last = max((f["ts"] for f in STATS.get("fails", [])
                if f.get("platform") == name and is_rate_limit(f.get("error", ""))), default=0)
    return last + config.DIGEST_RATE_LIMIT_COOLDOWN_HOURS * 3600 if last else 0


def headline_key(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))[:120]


def _first_line(text: str) -> str:
    return headline_key((text or "").strip().split("\n", 1)[0])


def recent_captions(name: str) -> list[str]:
    """First lines of the account's 5 newest posts (1 cheap API call)."""
    if name == "Instagram":
        token = env("INSTAGRAM_ACCESS_TOKEN") or env("FB_PAGE_TOKEN")
        r = http_get_json(graph(f"{env('IG_USER_ID')}/media"),
                          {"fields": "caption,timestamp", "limit": "5", "access_token": token})
        return [_first_line(m.get("caption", "")) for m in r.get("data", [])]
    if name == "Threads":
        r = http_get_json(f"https://graph.threads.net/v1.0/{env('THREADS_USER_ID') or 'me'}/threads",
                          {"fields": "text,timestamp", "limit": "5", "access_token": env("THREADS_ACCESS_TOKEN")})
        return [_first_line(m.get("text", "")) for m in r.get("data", [])]
    if name == "Facebook":
        r = http_get_json(graph(f"{env('FB_PAGE_ID')}/posts"),
                          {"fields": "message,created_time", "limit": "5", "access_token": env("FB_PAGE_TOKEN")})
        return [_first_line(m.get("message", "")) for m in r.get("data", [])]
    return []


def already_live(name: str, dg: dict, retry: bool) -> bool:
    """True if this exact carousel is already on the account (e.g. an earlier attempt got an
    error back even though Instagram published it). If the check itself fails on a retry,
    play safe and assume it is live, so we never post twice."""
    if not config.DIGEST_DUP_CHECK:
        return False
    try:
        mine = threads_caption(dg) if name == "Threads" else dg["caption"]
        return _first_line(mine) in recent_captions(name)
    except Exception as e:  # noqa: BLE001
        print(f"    ! {name} duplicate check failed: {e}")
        return retry


def digest_platforms() -> list[str]:
    on = set(enabled_platforms()) | ({"Instagram"} if all(env(k) for k in PLATFORMS["Instagram"][1])
                                     and images.available() else set())
    if env("THREADS_ACCESS_TOKEN"):
        on.add("Threads")
    return [n for n in config.DIGEST_PLATFORMS if n in on and n in DIGEST_POSTERS]


def run_digest(now: float, dry: bool, new_items: list[dict]) -> None:
    """Adds this run's stories to the queue; once a new hour starts, posts the previous
    hour(s) as one carousel per digest platform (retrying a failed platform up to 3 times)."""
    platforms = digest_platforms()
    if not platforms and not dry:
        return
    st = load(DIGEST_FILE, {"queue": [], "batch": None})
    CARD_CACHE.clear()
    CARD_CACHE.update({k: v for k, v in st.get("cards", {}).items() if v.get("ts", 0) > now - 3 * 3600})
    st["queue"] = [q for q in (st["queue"] + new_items)[-300:]
                   if q["ts"] >= now - config.DIGEST_MAX_AGE_HOURS * 3600]   # drop stale leftovers
    cur = hour_key(now)
    used = {k: t for k, t in st.get("used", {}).items() if t > now - 2 * 86400}   # headlines already in a carousel
    st["used"] = used
    if not st.get("batch"):
        ready = [q for q in st["queue"] if hour_key(q["ts"]) < cur]
        st["queue"] = [q for q in st["queue"] if hour_key(q["ts"]) >= cur]
        if config.DIGEST_SKIP_IF_NO_NEW:
            recent_words = [set(w["words"]) for w in st.get("used_words", [])
                            if w["ts"] > now - config.DIGEST_SIMILAR_HOURS * 3600]
            fresh, seen = [], set()
            for q in sorted(ready, key=lambda q: (q["priority"], q.get("focus", False)), reverse=True):
                k, words = headline_key(q["headline"]), set(q.get("words", []))
                if not k or k in used or k in seen:
                    continue                                    # exact repeat
                st_info = q.get("story") or {}
                if st_info.get("followup") or st_info.get("is_price"):
                    words = set()                               # real updates & new price levels are new news
                if words and any(similar(words, w) for w in recent_words):
                    continue                                    # same story, reworded
                seen.add(k)
                recent_words.append(words)
                fresh.append(q)
            fresh.sort(key=lambda q: q["ts"])
            if ready and not fresh:
                print("\n=== Hourly digest: no new headlines since the last carousel - nothing posted ===")
            ready = fresh
        # Platforms with a longer roundup (Instagram: 60 min) collect the 30-min batches and post
        # only when their own window closes.
        hold = st.setdefault("hold", {})
        w0 = _window_start(now)
        minute_of_day = w0.hour * 60 + w0.minute
        per: dict[str, list] = {}
        for name in platforms:
            win = platform_window(name)
            hold[name] = [q for q in hold.get(name, []) if q["ts"] > now - (win + 60) * 60]
            if win > int(getattr(config, "DIGEST_WINDOW_MINUTES", 60)) and minute_of_day % win:
                hold[name] += ready                     # not this platform's turn yet
                continue
            items_p = hold.pop(name, []) + ready
            if items_p:
                per[name] = items_p
        if per:
            st["batch"] = {"items": ready, "per": per, "done": [], "skipped": [], "attempts": 0,
                           "end_ts": w0.timestamp()}
    batch = st.get("batch")
    if batch:
        per = batch.get("per") or {n: batch["items"] for n in platforms}
        dgs: dict[str, dict] = {}

        def dg_for(name: str) -> dict:
            key = "|".join(headline_key(q["headline"]) for q in per[name])
            if key not in dgs:
                win = platform_window(name)
                dgs[key] = build_digest(per[name], win, batch.get("end_ts"))
                saved = batch.setdefault("urls_by", {}).get(key[:300])
                if saved:                               # reuse slides uploaded by an earlier attempt
                    dgs[key]["urls"], dgs[key]["photo_ids"] = saved["urls"], saved.get("photo_ids", [])
                print(f"\n=== Roundup {dgs[key]['window']}: {dgs[key]['count']} headlines, "
                      f"{len(dgs[key]['slides'])} slides ===")
            return dgs[key]

        if dry:
            PREVIEW_DIR.mkdir(exist_ok=True)
            for name in per:
                dg_for(name)
            for n, d in enumerate(dgs.values()):        # one set of previews per distinct roundup
                for i, data in enumerate(d["slides"], 1):
                    (PREVIEW_DIR / (f"digest_{i:02d}.jpg" if n == 0 else f"digest_{n}_{i:02d}.jpg")).write_bytes(data)
            print("    (DRY_RUN - digest not posted; slides saved as previews)")
            st["batch"] = None
        else:
            batch["attempts"] += 1
            batch.setdefault("skipped", [])
            for name in [n for n in platforms if n not in per and n not in batch["skipped"]]:
                batch["skipped"].append(name)           # nothing for this platform in this batch (held)
            for name in [n for n in platforms if n not in batch["done"] + batch["skipped"]]:
                dg = dg_for(name)
                if now < digest_cooldown_until(name) or (name == "Threads" and now < threads_blocked_until(now)):
                    print(f"    - {name}: rate-limited recently, skipping this carousel")
                    batch["skipped"].append(name)
                    continue
                if already_live(name, dg, retry=batch["attempts"] > 1):
                    print(f"    ✓ {name} carousel already live - not posting it again")
                    batch["done"].append(name)
                    continue
                try:
                    pid = DIGEST_POSTERS[name](dg)
                    batch["done"].append(name)
                    print(f"    ✓ {name} carousel {pid}")
                except Exception as e:  # noqa: BLE001
                    print(f"    ! {name} digest failed (attempt {batch['attempts']}): {e}")
                    record_fail(name, e, now)
                    if is_rate_limit(e):
                        batch["skipped"].append(name)   # never retry a rate limit (it may even be live)
            for key, d in dgs.items():
                if d.get("urls"):
                    batch.setdefault("urls_by", {})[key[:300]] = {"urls": d["urls"], "photo_ids": d.get("photo_ids", [])}
            finished = set(platforms) <= set(batch["done"] + batch["skipped"])
            if finished or batch["attempts"] >= config.DIGEST_MAX_ATTEMPTS:
                STATS.setdefault("digests", []).append({"ts": now, "done": list(batch["done"])})
                if batch["done"]:
                    for q in batch["items"]:
                        used[headline_key(q["headline"])] = now
                    st["used_words"] = [w for w in st.get("used_words", [])
                                        if w["ts"] > now - config.DIGEST_SIMILAR_HOURS * 3600] + \
                        [{"ts": now, "words": q.get("words", [])} for q in batch["items"] if q.get("words")]
                st["batch"] = None
    st["cards"] = dict(CARD_CACHE)
    save(DIGEST_FILE, st)


# --- X: one-tap link sent privately to you on Telegram -----------------------
def notify_x_link(p: dict, sources: list[str]) -> None:
    """Private Telegram message: the card (save it, attach on X) + a one-tap X link."""
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    text = p["tagged"]
    x_link = "https://x.com/intent/tweet?text=" + urllib.parse.quote(text)
    msg = f"{text}\n\nConfirmed by: {', '.join(sources)}\n\n👉 Post on X: {x_link}"
    api = f"https://api.telegram.org/bot{token}"
    if wants_card("X"):
        try:
            http_post_file(f"{api}/sendPhoto", {"chat_id": chat, "caption": msg[:1024]}, "photo", "card.jpg",
                           card_image(p))
            return
        except Exception as e:  # noqa: BLE001
            print(f"    ~ X alert image failed ({e}), sending text")
    http_post(f"{api}/sendMessage", {"chat_id": chat, "text": msg, "disable_web_page_preview": "true"})


HEALTH_FILE = STATE_DIR / "health.json"


def health_check(feeds_ok: int, now: float) -> None:
    """Private Telegram warning if most feeds fail (max once every 6 hours)."""
    if feeds_ok >= len(config.FEEDS) * 0.25:
        return
    h = load(HEALTH_FILE, {})
    if now - h.get("last_warn", 0) < 6 * 3600:
        return
    h["last_warn"] = now
    save(HEALTH_FILE, h)
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            http_post(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat,
                      "text": f"⚠️ {config.BRAND_NAME}: only {feeds_ok}/{len(config.FEEDS)} news feeds working. "
                              f"Check the latest GitHub Actions run log."})
        except Exception as e:  # noqa: BLE001
            print(f"  ! health alert failed: {e}")


# --- Error log + daily health report (private Telegram) -----------------------
STATS: dict = {}


def record_fail(platform: str, err: Exception, now: float) -> None:
    STATS.setdefault("fails", []).append({"ts": now, "platform": platform, "error": str(err)[:200]})


def save_stats(now: float) -> None:
    for key in ("fails", "digests", "reels"):
        STATS[key] = [x for x in STATS.get(key, []) if x["ts"] > now - 2 * 86400][-500:]
    save(STATS_FILE, STATS)


def send_private(text: str) -> None:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if token and chat:
        http_post(f"https://api.telegram.org/bot{token}/sendMessage",
                  {"chat_id": chat, "text": text, "disable_web_page_preview": "true"})


def record_day(day: str, posted: list, now: float) -> None:
    """One line of history per day (kept 21 days) for the weekly growth report."""
    since = now - 86400
    posts: dict[str, int] = {}
    for p in posted:
        if p["ts"] > since:
            for name in p.get("platforms", []):
                posts[name] = posts.get(name, 0) + 1
    for d in STATS.get("digests", []):
        if d["ts"] > since:
            for name in d.get("done", []):
                posts[name] = posts.get(name, 0) + 1
    fails: dict[str, int] = {}
    for f in STATS.get("fails", []):
        if f["ts"] > since:
            fails[f["platform"]] = fails.get(f["platform"], 0) + 1
    hist = STATS.setdefault("history", {})
    hist[day] = {"followers": dict(STATS.get("followers") or {}), "posts": posts, "fails": fails}
    for old in sorted(hist)[:-21]:
        del hist[old]


def is_report_sunday(now: float) -> bool:
    return datetime.fromtimestamp(now, _zone(config.DAILY_REPORT_TIMEZONE)).weekday() == 6


def _zone(name: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return timezone.utc


def weekly_report(day: str) -> str:
    """7-day growth summary: followers now vs a week ago, posts and errors per platform."""
    hist = STATS.get("history", {})
    days = [d for d in sorted(hist) if d <= day][-7:]
    if not days:
        return "📈 Weekly report: not enough history yet (starts filling from today)."
    first, last = hist[days[0]], hist[days[-1]]
    lines = [f"📈 WEEK IN NUMBERS ({days[0]} → {days[-1]}, {len(days)} days of data)"]
    fol_now, fol_then = last.get("followers") or {}, first.get("followers") or {}
    if fol_now:
        bits = []
        for k, v in sorted(fol_now.items(), key=lambda kv: -(kv[1] or 0)):
            if v is None:
                continue
            then = fol_then.get(k)
            delta = f" ({v - then:+,})" if isinstance(then, int) and len(days) > 1 else ""
            bits.append(f"{k} {v:,}{delta}")
        lines.append("👥 Followers: " + " | ".join(bits))
    posts: dict[str, int] = {}
    fails: dict[str, int] = {}
    for d in days:
        for k, v in hist[d].get("posts", {}).items():
            posts[k] = posts.get(k, 0) + v
        for k, v in hist[d].get("fails", {}).items():
            fails[k] = fails.get(k, 0) + v
    if posts:
        lines.append("📤 Posts: " + " | ".join(f"{k} {v:,}" for k, v in sorted(posts.items(), key=lambda kv: -kv[1])))
    lines.append("⚠️ Errors: " + (" | ".join(f"{k} {v}" for k, v in sorted(fails.items(), key=lambda kv: -kv[1]))
                                 if fails else "none"))
    grew = [k for k, v in fol_now.items() if isinstance(v, int) and isinstance(fol_then.get(k), int) and v > fol_then[k]]
    lines.append("🏆 Growing: " + (", ".join(grew) if grew else "no platform grew this week"))
    return "\n".join(lines)


def send_daily_report(now: float, dry: bool, posted: list) -> None:
    day = extras.report_due(STATS, now)
    if not day:
        return
    if config.REPORT_FOLLOWERS:
        counts = follower_counts()
        prev = STATS.get("followers") or {}
        STATS["followers_prev"], STATS["followers"] = prev, counts
    text = extras.build_report(posted, STATS, enabled_platforms(), digest_platforms(), now)
    record_day(day, posted, now)
    if getattr(config, "WEEKLY_REPORT", False) and is_report_sunday(now):
        text += "\n\n" + weekly_report(day)
    print("\n=== Daily report ===\n" + text)
    if not dry:
        send_private(text)
    STATS["report_day"] = day


# --- Market open/close + economic calendar posts --------------------------------
def special_post(text: str, tags: list[str], kind: str) -> dict:
    """A post that isn't a news headline (multi-line text, no source)."""
    tagged = text
    use = []
    for t in tags[: config.MAX_HASHTAGS_X]:
        if len(text) + 2 + len(" ".join(use + [t])) <= 280:
            use.append(t)
    if use:
        tagged = f"{text}\n\n{' '.join(use)}"
    return {"plain": text[:500], "tagged": tagged, "topic": threads_topic(tags),
            "story": {"priority": 3, "countries": [], "kind": kind}, "headline": text, "credit_main": "",
            "social_caption": tagged, "alt": f"{config.BRAND_NAME}: {text}",
            "ig_caption": f"{tagged}\n\nAutomated alert. Not financial advice."}


def publish_special(p: dict, kind: str, now: float, dry: bool, posted: list, platforms: list[str]) -> bool:
    print(f"\n>>> [{kind}] {p['tagged']}")
    done: list[str] = []
    ids: dict = {}
    if dry:
        print("    (DRY_RUN - not posted)")
    else:
        targets = [n for n in platforms if n not in IMAGE_PLATFORMS and n not in config.DIGEST_PLATFORMS]
        if "Threads" in targets and not threads_ok(posted, now):
            targets.remove("Threads")
        for name in targets:
            try:
                pid = PLATFORMS[name][0](p)
                done.append(name)
                ids[name] = pid
                print(f"    ✓ {name} {pid}")
            except Exception as e:  # noqa: BLE001
                print(f"    ! {name} failed: {e}")
                record_fail(name, e, now)
        if targets and not done:
            return False                     # all failed: try again next run
        try:
            notify_x_link(p, ["Market Data" if kind == "market" else "Economic Calendar"])
        except Exception as e:  # noqa: BLE001
            print(f"    ! X alert failed: {e}")
    posted.append({"ts": now, "text": p["tagged"], "words": [], "sources": [], "item_ids": [],
                   "story_id": f"{kind}:{int(now)}", "platforms": done, "kind": kind,
                   "telegram_id": ids.get("Telegram", "")})
    return True


def run_extras(now: float, dry: bool, posted: list, price_state: dict, platforms: list[str], room: int) -> None:
    st = load(EXTRAS_FILE, {"bells": {}, "cal": {}})
    cal = st.setdefault("cal", {})
    todo: list[tuple[dict, str, callable]] = []

    for bell in extras.due_bells(price_state, st.setdefault("bells", {}), now):
        def mark(b=bell):
            st["bells"][b["id"]] = b["day"]
        todo.append((special_post(bell["title"] + "\n" + "\n".join(bell["lines"]), bell["tags"], "market"),
                     "market", mark))

    if config.CALENDAR_ENABLED:
        if now - cal.get("fetched", 0) > config.CALENDAR_REFRESH_HOURS * 3600:
            raw = fetch(config.CALENDAR_URL)
            events = extras.parse_calendar(raw)
            if raw and (events or raw.strip().startswith(b"[")):
                cal["events"] = events
                cal["fetched"] = now
                print(f"Economic calendar: {len(events)} key events this week")
            else:
                cal["fetched"] = now - config.CALENDAR_REFRESH_HOURS * 3600 + 1800   # retry in 30 min
                print("  ! economic calendar unavailable")
        events = [e for e in cal.get("events", []) if e["ts"] > now - 86400]
        cal["events"] = events
        daily = extras.daily_calendar_post(events, cal.get("daily", ""), now)
        if daily:
            if daily["text"]:
                todo.append((special_post(daily["text"], daily["tags"], "calendar"), "calendar",
                             lambda d=daily: cal.__setitem__("daily", d["day"])))
            else:
                cal["daily"] = daily["day"]
        sent = cal.setdefault("sent", [])
        for hu in extras.heads_up_posts(events, sent, now):
            todo.append((special_post(hu["text"], hu["tags"], "calendar"), "calendar",
                         lambda h=hu: sent.extend(h["keys"])))

    for p, kind, mark in todo:
        if room <= 0:
            print("  daily post limit reached - skipping market/calendar posts")
            break
        if publish_special(p, kind, now, dry, posted, platforms):
            mark()
            room -= 1
    cal["sent"] = cal.get("sent", [])[-300:]
    save(EXTRAS_FILE, st)


# --- Daily reel, weekly recap, welcome post, follower counts (update 8) --------
RECAP_LOG: list = []      # stories posted in this run (merged into recap.json by run_recaps)


def rupload(url: str, data: bytes, token: str) -> dict:
    return http_post_bytes(url, data, {"Authorization": f"OAuth {token}", "offset": "0",
                                       "file_size": str(len(data)), "Content-Type": "application/octet-stream"})


def post_instagram_reel(rl: dict) -> str:
    token = env("INSTAGRAM_ACCESS_TOKEN") or env("FB_PAGE_TOKEN")
    ig = env("IG_USER_ID")
    c = http_post(graph(f"{ig}/media"), {"media_type": "REELS", "upload_type": "resumable", "share_to_feed": "true",
                                         "caption": rl["caption"], "access_token": token})["id"]
    rupload(f"https://rupload.facebook.com/ig-api-upload/{config.GRAPH_API_VERSION}/{c}", rl["video"], token)
    for _ in range(40):                      # video processing can take a minute or two
        st = http_get_json(graph(c), {"fields": "status_code", "access_token": token}).get("status_code")
        if st in ("FINISHED", None):
            break
        if st == "ERROR":
            raise RuntimeError("Instagram could not process the reel")
        time.sleep(5)
    return http_post(graph(f"{ig}/media_publish"), {"creation_id": c, "access_token": token}).get("id", "")


def post_facebook_reel(rl: dict) -> str:
    token, page = env("FB_PAGE_TOKEN"), env("FB_PAGE_ID")
    start = http_post(graph(f"{page}/video_reels"), {"upload_phase": "start", "access_token": token})
    vid = start["video_id"]
    rupload(start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{config.GRAPH_API_VERSION}/{vid}",
            rl["video"], token)
    http_post(graph(f"{page}/video_reels"), {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                             "description": rl["caption"], "access_token": token})
    return vid


def post_telegram_reel(rl: dict) -> str:
    api = f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
    r = http_post_file(f"{api}/sendVideo", {"chat_id": env("TELEGRAM_CHANNEL_ID"), "caption": rl["caption"][:1024],
                                            "supports_streaming": "true", "width": "1080", "height": "1920"},
                       "video", "reel.mp4", rl["video"], content_type="video/mp4")
    return str(r.get("result", {}).get("message_id", ""))


def youtube_access_token() -> str:
    return http_post("https://oauth2.googleapis.com/token", {
        "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
        "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"})["access_token"]


def youtube_upload(video: bytes, meta: dict, token: str) -> str:
    """Resumable upload: start a session (metadata), then send the bytes. Returns the video id."""
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(), method="POST", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(video))})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            location = r.headers.get("Location")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}") from None
    if not location:
        raise RuntimeError("YouTube did not return an upload URL")
    put = urllib.request.Request(location, data=video, method="PUT", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
    try:
        with urllib.request.urlopen(put, timeout=300) as r:
            return json.loads(r.read() or b"{}").get("id", "")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}") from None


def post_youtube_short(rl: dict) -> str:
    title = rl.get("title") or "Today's Top Market Stories"
    meta = {"snippet": {"title": f"{title} #Shorts"[:100], "description": rl["caption"][:4900],
                        "tags": [t.lstrip("#") for t in config.REEL_HASHTAGS] + ["Shorts", "News Before Noise"],
                        "categoryId": config.YOUTUBE_CATEGORY_ID, "defaultLanguage": "en"},
            "status": {"privacyStatus": config.YOUTUBE_PRIVACY, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": False}}
    return youtube_upload(rl["video"], meta, youtube_access_token())


def post_private_reel(rl: dict) -> str:
    """Copy of the reel in your private Telegram chat (handy while YouTube uploads are still private)."""
    api = f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
    r = http_post_file(f"{api}/sendVideo", {"chat_id": env("TELEGRAM_CHAT_ID"),
                                            "caption": ("🎬 Today's reel (for manual upload if needed)\n\n"
                                                        + rl["caption"])[:1024], "supports_streaming": "true"},
                       "video", "reel.mp4", rl["video"], content_type="video/mp4")
    return str(r.get("result", {}).get("message_id", ""))


REEL_POSTERS = {"YouTube": (post_youtube_short, ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]),
                "Private": (post_private_reel, ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]),
                "Instagram": (post_instagram_reel, ["IG_USER_ID", "FB_PAGE_TOKEN"]),
                "Facebook": (post_facebook_reel, ["FB_PAGE_ID", "FB_PAGE_TOKEN"]),
                "Telegram": (post_telegram_reel, ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"])}


def run_recaps(now: float, dry: bool, posted: list, platforms: list[str]) -> None:
    st = load(RECAP_FILE, {"log": []})
    st["log"] = [x for x in st.get("log", []) + RECAP_LOG if x["ts"] > now - 8 * 86400][-3000:]
    RECAP_LOG.clear()
    tz = _tz()
    local = datetime.fromtimestamp(now, tz)

    # 🎬 daily reel
    reel = st.setdefault("reel", {})
    day = config.REEL_ENABLED and recap.due(config.REEL_AT, config.DIGEST_TIMEZONE, reel.get("day", ""), now)
    if day:
        if reel.get("pending") != day:
            reel.update({"pending": day, "done": [], "attempts": 0})
        top = recap.top_stories(st["log"], now - 86400, now + 1, config.REEL_STORIES)
        targets = [n for n in config.REEL_PLATFORMS if n in REEL_POSTERS
                   and all(env(k) for k in REEL_POSTERS[n][1]) and n not in reel["done"]]
        if len(top) < 3:
            print("Daily reel: fewer than 3 stories today - skipped")
            reel["day"] = day
        elif not recap.ffmpeg_exe() or not images.available():
            print("Daily reel: video tool missing - will retry")
            reel["attempts"] += 1
        else:
            rl = recap.build_reel(top, local)
            print(f"\n=== Daily reel: {rl['count']} stories, {len(rl['video']) // 1024} KB ===")
            if dry:
                PREVIEW_DIR.mkdir(exist_ok=True)
                (PREVIEW_DIR / "reel.mp4").write_bytes(rl["video"])
                print("    (DRY_RUN - reel not posted; saved as preview)")
                targets = []
                reel["done"] = list(config.REEL_PLATFORMS)
            reel["attempts"] += 1
            for name in targets:
                try:
                    pid = REEL_POSTERS[name][0](rl)
                    reel["done"].append(name)
                    print(f"    ✓ {name} reel {pid}")
                except Exception as e:  # noqa: BLE001
                    print(f"    ! {name} reel failed (attempt {reel['attempts']}): {e}")
                    record_fail(f"{name} reel", e, now)
            remaining = [n for n in targets if n not in reel["done"]]
            if not remaining or reel["attempts"] >= config.REEL_MAX_ATTEMPTS:
                reel["day"] = day
                STATS.setdefault("reels", []).append({"ts": now, "done": list(reel["done"])})
        if reel.get("attempts", 0) >= config.REEL_MAX_ATTEMPTS:
            reel["day"] = day

    # 📅 weekly recap (Sunday)
    wk = st.setdefault("weekly", {})
    wday = config.WEEKLY_ENABLED and recap.due(config.WEEKLY_AT, config.DIGEST_TIMEZONE, wk.get("day", ""),
                                               now, weekday=6)
    if wday:
        top = recap.top_stories(st["log"], now - 7 * 86400, now + 1, config.WEEKLY_STORIES)
        wk["day"] = wday
        if len(top) >= 3 and images.available():
            start = datetime.fromtimestamp(now - 6 * 86400, tz)
            dg = recap.build_weekly(top, start, local)
            print(f"\n=== Weekly recap {dg['window']}: {dg['count']} stories ===")
            if dry:
                PREVIEW_DIR.mkdir(exist_ok=True)
                for i, data in enumerate(dg["slides"], 1):
                    (PREVIEW_DIR / f"weekly_{i:02d}.jpg").write_bytes(data)
            else:
                for name in digest_platforms():
                    try:
                        print(f"    ✓ {name} weekly {DIGEST_POSTERS[name](dg)}")
                    except Exception as e:  # noqa: BLE001
                        print(f"    ! {name} weekly failed: {e}")
                        record_fail(f"{name} weekly", e, now)
            publish_special(special_post(dg["text"], ["#WeekInReview", "#Markets"], "recap"), "recap",
                            now, dry, posted, platforms)

    # 🧾 daily evening recaps (Global/US + India)
    if config.DAILY_RECAP_ENABLED:
        dr = st.setdefault("daily_recap", {})
        for ed, at in (("us", config.DAILY_RECAP_US_AT), ("in", config.DAILY_RECAP_IN_AT)):
            info = dr.setdefault(ed, {})
            tzname = daily_recap.EDITIONS[ed]["tz"]
            day = recap.due(at, tzname, info.get("day", ""), now, window_hours=4)
            if not day or datetime.fromtimestamp(now, _zone(tzname)).weekday() >= 5:
                continue
            info["day"] = day
            since = max(info.get("ts", 0), now - 26 * 3600)
            stories = daily_recap.pick(st["log"], ed, since, now + 1)
            if len(stories) < config.DAILY_RECAP_MIN_ITEMS:
                print(f"Daily recap ({ed}): only {len(stories)} stories - skipped")
                continue
            info["ts"] = now
            r = daily_recap.compose(ed, stories, daily_recap.market_lines(PRICE_STATE, ed), now,
                                    env("GH_MODELS_TOKEN"))
            print(f"\n=== Daily recap ({ed}): {r['count']} stories, {r['mode']}, "
                  f"{r['fallbacks']} plain fallbacks ===\n{r['text']}")
            publish_daily_recap(r, ed, now, dry, posted, platforms)

    # 👋 one-time welcome post
    if config.WELCOME_ENABLED and not st.get("welcome_done"):
        p = special_post(config.WELCOME_TEXT, [], "welcome")
        if publish_special(p, "welcome", now, dry, posted, platforms):
            st["welcome_done"] = True
            if not dry:
                pin_latest_telegram(posted[-1])
    save(RECAP_FILE, st)


def _zone(name: str):
    from zoneinfo import ZoneInfo
    return ZoneInfo(name)


PRICE_STATE: dict = {}


def publish_daily_recap(r: dict, edition: str, now: float, dry: bool, posted: list, platforms: list[str]) -> None:
    done: list[str] = []
    if not dry:
        targets = [n for n in config.DAILY_RECAP_PLATFORMS if n in platforms or n == "Facebook"]
        if "Telegram" in targets and env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHANNEL_ID"):
            try:
                api = f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
                for chunk in daily_recap.split_for_telegram(r["text"]):
                    http_post(f"{api}/sendMessage", {"chat_id": env("TELEGRAM_CHANNEL_ID"), "text": chunk,
                                                     "disable_web_page_preview": "true"})
                done.append("Telegram")
            except Exception as e:  # noqa: BLE001
                print(f"    ! Telegram recap failed: {e}")
                record_fail("Telegram recap", e, now)
        if "Facebook" in targets and env("FB_PAGE_ID") and env("FB_PAGE_TOKEN") and config.FACEBOOK_PUBLISH:
            try:
                http_post(graph(f"{env('FB_PAGE_ID')}/feed"), {"message": r["text"],
                                                               "access_token": env("FB_PAGE_TOKEN")})
                done.append("Facebook")
            except Exception as e:  # noqa: BLE001
                print(f"    ! Facebook recap failed: {e}")
                record_fail("Facebook recap", e, now)
        if "Threads" in targets and threads_ok(posted, now):
            try:
                post_threads(special_post(r["short"], daily_recap.EDITIONS[edition]["tags"], "recap"))
                done.append("Threads")
            except Exception as e:  # noqa: BLE001
                print(f"    ! Threads recap failed: {e}")
                record_fail("Threads recap", e, now)
        try:
            tg_link = f"t.me/{config.BRAND_HANDLE.lstrip('@')}"
            x_text = r["short"].split("\n")[0] + f"\n\nFull recap: {tg_link}"
            send_private("📝 Daily recap (copy for X):\n\n" + r["text"][:3500] + "\n\n👉 Post on X: "
                         "https://x.com/intent/tweet?text=" + urllib.parse.quote(x_text))
        except Exception as e:  # noqa: BLE001
            print(f"    ! recap X alert failed: {e}")
        print(f"    ✓ daily recap posted on: {', '.join(done) or 'nothing'}")
    posted.append({"ts": now, "text": r["short"], "words": [], "sources": [], "item_ids": [],
                   "story_id": f"recap:{edition}:{int(now)}", "platforms": done, "kind": "recap"})


def pin_latest_telegram(entry: dict) -> None:
    """Pins the welcome message in the Telegram channel (bot needs the 'pin messages' right)."""
    mid = entry.get("telegram_id")
    if not mid:
        return
    try:
        http_post(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/pinChatMessage",
                  {"chat_id": env("TELEGRAM_CHANNEL_ID"), "message_id": mid, "disable_notification": "true"})
        print("    ✓ welcome post pinned on Telegram")
    except Exception as e:  # noqa: BLE001
        print(f"    ~ could not pin on Telegram ({e}) - pin it in the app")


def follower_counts() -> dict:
    """Current followers per platform (None = not available)."""
    out: dict = {}

    def safe(name, fn):
        try:
            v = fn()
            out[name] = int(v) if v is not None else None
        except Exception as e:  # noqa: BLE001
            print(f"  ~ {name} followers unavailable: {str(e)[:120]}")
            out[name] = None

    if env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHANNEL_ID"):
        safe("Telegram", lambda: http_get_json(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
                                               f"/getChatMemberCount", {"chat_id": env("TELEGRAM_CHANNEL_ID")})
             .get("result"))
    if env("IG_USER_ID") and env("FB_PAGE_TOKEN"):
        safe("Instagram", lambda: http_get_json(graph(env("IG_USER_ID")), {
            "fields": "followers_count", "access_token": env("INSTAGRAM_ACCESS_TOKEN") or env("FB_PAGE_TOKEN")})
             .get("followers_count"))
    if env("FB_PAGE_ID") and env("FB_PAGE_TOKEN"):
        safe("Facebook", lambda: (lambda r: r.get("followers_count", r.get("fan_count")))(
            http_get_json(graph(env("FB_PAGE_ID")), {"fields": "followers_count,fan_count",
                                                     "access_token": env("FB_PAGE_TOKEN")})))
    if env("THREADS_ACCESS_TOKEN"):
        def threads():
            r = http_get_json(f"https://graph.threads.net/v1.0/{env('THREADS_USER_ID') or 'me'}/threads_insights",
                              {"metric": "followers_count", "access_token": env("THREADS_ACCESS_TOKEN")})
            return r["data"][0]["total_value"]["value"]
        safe("Threads", threads)
    return out


def title_case(text: str) -> str:
    """Squawk-style Title Case. Keeps acronyms (US, RBI), numbers and words like iPhone."""
    def fix(w: str) -> str:
        if any(c.isdigit() for c in w):
            return w
        i = next((k for k, c in enumerate(w) if c.isalpha()), None)
        if i is None or any(c.isupper() for c in w[i + 1:]) or not w[i].islower():
            return w
        return w[:i] + w[i].upper() + w[i + 1:]
    return " ".join("-".join(fix(part) for part in word.split("-")) for word in text.split(" "))


_QUOTE_CACHE: dict = {}


def stock_move_text(headline: str, now: float | None = None) -> str:
    """' ($AMD −8.2%)' for companies named in the headline, using the live price.
    Shown only when the market is open (fresh quote) and the move is at least STOCK_MOVE_MIN_PCT."""
    if not getattr(config, "SHOW_STOCK_MOVE", False):
        return ""
    now = now or time.time()
    low = " " + re.sub(r"[^a-z0-9& ]+", " ", headline.lower()) + " "
    found: list[tuple[int, str]] = []
    for name in sorted(config.STOCK_TICKERS, key=len, reverse=True):     # longest name first
        sym = config.STOCK_TICKERS[name]
        pos = low.find(f" {name} ")
        if pos >= 0 and sym not in [x[1] for x in found]:
            found.append((pos, sym))
            low = low.replace(f" {name} ", " " + "#" * len(name) + " ")   # keep positions, block shorter overlaps
    syms = [sym for _, sym in sorted(found)][: config.STOCK_MOVE_MAX_TICKERS]   # order as in the headline
    bits = []
    for sym in syms:
        if sym not in _QUOTE_CACHE:
            try:
                _QUOTE_CACHE[sym] = prices.fetch_quote(sym)
            except Exception:  # noqa: BLE001  a price lookup must never block a headline
                _QUOTE_CACHE[sym] = None
        q = _QUOTE_CACHE[sym]
        if not q or not q[0] or not q[1] or (len(q) > 2 and q[2] and now - q[2] > config.STOCK_MOVE_MAX_AGE_MIN * 60):
            continue
        pct = (q[0] / q[1] - 1) * 100
        if abs(pct) < config.STOCK_MOVE_MIN_PCT:
            continue
        label = sym.split(".")[0].split("-")[0]
        bits.append(f"${label} {'+' if pct > 0 else '−'}{abs(pct):.1f}%")
    return f" ({', '.join(bits)})" if bits else ""


def build_posts(story: dict) -> dict:
    """plain  = flag + headline (Threads)
    tagged = flag + headline + up to MAX_HASHTAGS_X hashtags, <= 280 chars (X, Bluesky, Telegram...)
    topic  = single Threads topic tag"""
    headline = title_case(story["text"]) if config.TITLE_CASE else story["text"]
    prefix = config.POST_PREFIX + (config.FOLLOWUP_PREFIX if story.get("followup") else "")
    move = "" if story.get("is_price") or story.get("kind") else stock_move_text(headline)
    head = f'{story["flags"]} {prefix}{headline}{move}'.strip()
    if story.get("breaking"):
        head = config.BREAKING_LABEL + head
    credit = [c for c in story.get("credit", []) if c.lower() not in headline.lower()] if config.SHOW_SOURCES else []
    credit = credit[: config.MAX_SOURCES_SHOWN]
    while credit and len(head) + 3 + len(", ".join(credit)) > 250:
        credit = credit[:-1]  # keep room for hashtags on X
    if credit:
        head += " – " + ", ".join(credit)
    tags = story.get("tags", [])
    x_tags = []
    for t in tags[: config.MAX_HASHTAGS_X]:
        if len(head) + 2 + len(" ".join(x_tags + [t])) <= 280:
            x_tags.append(t)
    tagged = f"{head}\n\n{' '.join(x_tags)}" if x_tags else head[:280]
    ig_tags = " ".join(tags[: config.MAX_HASHTAGS_INSTAGRAM])
    return {"plain": head, "tagged": tagged, "topic": threads_topic(tags), "story": story,
            "headline": (config.FOLLOWUP_PREFIX if story.get("followup") else "") + headline,
            "credit_main": credit[0] if credit else "",
            "social_caption": tagged,
            "alt": f"{config.BRAND_NAME} headline card: {headline}" + (f" (Source: {credit[0]})" if credit else ""),
            "ig_caption": f"{head}\n\n{ig_tags}\n\nAutomated headline alert. Not financial advice.".strip()}


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def needs_video() -> bool:
    """Used by the workflow: install the video tool only around reel time."""
    st = load(RECAP_FILE, {})
    return bool(config.REEL_ENABLED and recap.due(config.REEL_AT, config.DIGEST_TIMEZONE,
                                                     (st.get("reel") or {}).get("day", ""), time.time()))


def main() -> int:
    if "--needs-video" in sys.argv:
        return 0 if needs_video() else 1
    if os.environ.get("BOT_ENABLED", "true").lower() == "false":
        print("BOT_ENABLED=false -> kill switch on, doing nothing.")
        return 0
    dry = os.environ.get("DRY_RUN", "false").lower() == "true"
    now = time.time()

    items = load(ITEMS_FILE, {})
    posted = load(POSTED_FILE, [])
    STATS.clear()
    STATS.update(load(STATS_FILE, {}))
    RECAP_LOG.clear()
    first_run = not ITEMS_FILE.exists()

    print(f"Reading {len(config.FEEDS)} feeds...")
    raws = fetch_all([f["url"] for f in config.FEEDS])
    feeds_ok = 0
    for feed in config.FEEDS:
        raw = raws.get(feed["url"])
        entries = parse_feed(raw) if raw else []
        if entries:
            feeds_ok += 1
            n = collect(items, feed, entries, now)
            print(f"  {feed['name']}: +{n}")
        elif raw:
            print(f"  ! {feed['name']}: no headlines in response")
    print(f"Feeds working: {feeds_ok}/{len(config.FEEDS)}")
    health_check(feeds_ok, now)

    # forget old stuff so the state files stay small
    items = {k: v for k, v in items.items() if v["seen"] > now - 12 * 3600}
    posted = [p for p in posted if p["ts"] > now - 3 * 86400]

    price_state = load(PRICES_FILE, {})
    print("Checking live prices...")
    alerts = prices.price_alerts(price_state, now)
    save(PRICES_FILE, price_state)
    PRICE_STATE.clear()
    PRICE_STATE.update(price_state)

    if first_run:
        for it in items.values():
            it["baseline"] = True
        print("First run: saved current headlines and prices as a baseline, posting nothing.")
        save(ITEMS_FILE, items)
        save(POSTED_FILE, posted)
        return 0

    trends = trending_terms()
    print(f"Trending searches loaded: {len(trends)}")
    if config.REQUIRE_FOCUS_COUNTRY:
        alerts = [a for a in alerts if a.get("focus")]
    stories = find_stories(items, posted, now, trends) + alerts
    stories.sort(key=lambda s: (s["priority"], s.get("focus", False), not s.get("is_price")), reverse=True)
    print(f"Price alerts: {len(alerts)}")
    last_24h = sum(1 for p in posted if p["ts"] > now - 86400)
    day_cap = config.MAX_POSTS_PER_DAY or 10**9                                           # 0 = unlimited
    budget = min(config.MAX_POSTS_PER_RUN, day_cap - last_24h)                          # news
    day_left = day_cap - last_24h                                                       # everything
    print(f"Confirmed stories: {len(stories)} | posts in last 24h: {last_24h} | news slots now: {max(budget, 0)}")

    platforms = enabled_platforms()
    print(f"Auto-posting to: {', '.join(platforms) or 'NONE (add secrets)'}")

    done_this_run: list[set[str]] = []
    digest_items: list[dict] = []
    count = 0
    news_count = 0
    for story in stories:
        if count >= max(day_left, 0):
            break                                  # daily limit reached
        if not story.get("is_price") and news_count >= max(budget, 0):
            continue                               # news slots used; price alerts have their own allowance
        words = set(story["words"])
        if words and not story["followup"] and any(similar(words, d) for d in done_this_run):
            continue  # same story found twice in this run
        story["breaking"] = extras.is_breaking(story, story.get("all_text", ""), posted, now)
        p = build_posts(story)
        print(f"\n>>> {'[follow-up] ' if story['followup'] else ''}{p['tagged']}"
              f"\n    Threads topic: {p['topic']} | sources: {', '.join(story['sources'])}")
        if dry:
            print("    (DRY_RUN - not posted)")
            if images.available() and count < 10:
                PREVIEW_DIR.mkdir(exist_ok=True)
                (PREVIEW_DIR / f"card_{count + 1}.jpg").write_bytes(card_image(p))
            done_platforms: list[str] = []
        else:
            if count:
                time.sleep(config.POST_SPACING_SECONDS)  # natural spacing, like a squawk desk
            ok = tried = 0
            done_platforms = []
            for name in platforms:
                if not platform_wants(name, story, posted, now):
                    continue
                tried += 1
                try:
                    pid = PLATFORMS[name][0](p)
                    ok += 1
                    done_platforms.append(name)
                    print(f"    ✓ {name} {pid}")
                except Exception as e:  # noqa: BLE001  one platform failing never stops the others
                    print(f"    ! {name} failed: {e}")
                    record_fail(name, e, now)
            if tried and ok == 0:
                continue  # everything failed - try again next run (no X alert either)
            try:
                notify_x_link(p, story["sources"])
            except Exception as e:  # noqa: BLE001
                print(f"    ! X alert failed: {e}")
        count += 1
        if not story.get("is_price"):
            news_count += 1
        done_this_run.append(words)
        if story["priority"] >= config.DIGEST_MIN_PRIORITY:
            digest_items.append(queue_for_digest(p, story, now))
            if not story.get("is_price"):
                RECAP_LOG.append(recap.log_item(p, story, now))
        posted.append({"ts": now, "text": p["tagged"], "words": story["words"], "sources": story["sources"],
                       "item_ids": story["item_ids"], "story_id": story["story_id"],
                       "platforms": done_platforms, "breaking": bool(story.get("breaking")),
                       "is_price": bool(story.get("is_price"))})

    try:
        run_extras(now, dry, posted, price_state, platforms, day_left - count)
    except Exception as e:  # noqa: BLE001  extras must never break live posting
        print(f"  ! extras error: {e}")
    save(ITEMS_FILE, items)
    save(POSTED_FILE, posted)
    if config.DIGEST_PLATFORMS:
        try:
            run_digest(now, dry, digest_items)
        except Exception as e:  # noqa: BLE001  the digest must never break live posting
            print(f"  ! digest error: {e}")
    try:
        run_recaps(now, dry, posted, platforms)
    except Exception as e:  # noqa: BLE001  recaps must never break live posting
        print(f"  ! recap error: {e}")
    save(POSTED_FILE, posted)          # again: recaps/welcome add entries
    try:
        STATS["feeds"] = [feeds_ok, len(config.FEEDS)]
        send_daily_report(now, dry, posted)
    except Exception as e:  # noqa: BLE001
        print(f"  ! daily report error: {e}")
    save_stats(now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
