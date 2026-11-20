"""
End-to-end scenario tests: run the whole bot (main()) several times against a
fake internet - fake news feeds, fake prices, fake Facebook / Instagram /
Threads / Bluesky / Telegram / Mastodon / Discord - and check what gets posted.

Run:  python3 tests/test_scenarios.py
"""
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "newsbot"))
import bot      # noqa: E402
import images   # noqa: E402
import prices   # noqa: E402

SECRETS = {
    "FB_PAGE_ID": "PAGE", "FB_PAGE_TOKEN": "PTOK", "IG_USER_ID": "IGU",
    "THREADS_ACCESS_TOKEN": "TT", "BLUESKY_HANDLE": "nbn.bsky.social", "BLUESKY_APP_PASSWORD": "pw",
    "TELEGRAM_BOT_TOKEN": "BOT", "TELEGRAM_CHANNEL_ID": "@NewsB4Noise", "TELEGRAM_CHAT_ID": "999",
    "MASTODON_INSTANCE": "https://masto.example", "MASTODON_TOKEN": "MT",
    "DISCORD_WEBHOOK_URL": "https://discord.example/api/webhooks/1/abc",
}
OWNERS = ["cnbc", "bbc", "nikkei", "guardian"]
ORIG_BELLS = list(bot.config.MARKET_BELLS)
ORIG_SYMBOLS = list(bot.config.PRICE_SYMBOLS)


class FakeInternet:
    def __init__(self):
        self.feeds: dict[str, list[str]] = {o: [] for o in OWNERS}
        self.fed: list[str] = []
        self.quotes: dict[str, tuple] = {}
        self.calls: list[tuple] = []          # (platform, kind, detail)
        self.fail: set[str] = set()           # platforms that should error

    # ---- network fakes
    def fetch(self, url, timeout=15):
        if "trends" in url:
            return b"<rss><channel><item><title>yen</title></item></channel></rss>"
        titles = self.fed if url == "fed" else self.feeds.get(url, [])
        items = "".join(f"<item><title>{t}</title><pubDate>{time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(time.time()))}</pubDate></item>" for t in titles)
        return f"<rss><channel>{items}</channel></rss>".encode()

    def quote(self, sym):
        q = self.quotes.get(sym)
        return (q[0], q[1], int(time.time())) if q else None

    def _platform(self, url):
        for key, name in [("graph.facebook.com/v24.0/IGU", "Instagram"), ("ig-api-upload", "Instagram"),
                          ("video-upload", "Facebook"), ("graph.facebook.com", "Facebook"),
                          ("threads.net", "Threads"), ("bsky.social", "Bluesky"), ("masto.example", "Mastodon"),
                          ("discord.example", "Discord")]:
            if key in url:
                return name
        if "api.telegram.org" in url:
            return "Telegram"
        return "?"

    def _maybe_fail(self, name):
        if name in self.fail:
            raise RuntimeError(f"HTTP 500: {name} is down")

    def http_post(self, url, params=None, json_body=None, headers=None):
        name = self._platform(url)
        body = params or json_body or {}
        if name == "Telegram":
            name = "Telegram" if body.get("chat_id") == "@NewsB4Noise" else "X-alert"
        self._maybe_fail(name)
        endpoint = url.rstrip("/").rsplit("/", 1)[-1]
        text = body.get("text") or body.get("status") or body.get("content") or body.get("caption") or \
            (body.get("record") or {}).get("text") or ""
        has_media = bool(body.get("media_ids[]") or (body.get("record") or {}).get("embed")
                         or body.get("media_type") == "IMAGE" or body.get("image_url"))
        extra = {k: v for k, v in body.items() if k in ("is_carousel_item", "children") or k.startswith("attached_media")}
        self.calls.append((name, endpoint, {"text": text or body.get("message", ""), "media": has_media, **extra}))
        if "createSession" in url:
            return {"did": "did:plc:x", "accessJwt": "jwt"}
        if endpoint == "video_reels" and body.get("upload_phase") == "start":
            return {"video_id": "VID", "upload_url": "https://rupload.facebook.com/video-upload/v24.0/VID"}
        return {"id": "C1", "uri": "at://post", "result": {"message_id": 1}}

    def http_post_file(self, url, fields, ff, fn, data, headers=None, content_type="image/jpeg"):
        name = self._platform(url)
        if name == "Telegram":
            name = "Telegram" if fields.get("chat_id") == "@NewsB4Noise" else "X-alert"
        self._maybe_fail(name)
        if content_type == "video/mp4":
            assert data[4:8] == b"ftyp", "not an MP4"
            self.calls.append((name, "upload-video", {"text": fields.get("caption", "")}))
            return {"result": {"message_id": 3}}
        assert data[:2] == b"\xff\xd8", "not a JPEG"
        self.calls.append((name, "upload-image", {"published": fields.get("published"), "text": fields.get("message", "")}))
        return {"id": "PHOTO", "post_id": "PAGE_POST", "result": {"message_id": 2}}

    def http_get_json(self, url, params):
        if "getChatMemberCount" in url:
            return {"ok": True, "result": 120}
        if params.get("fields") == "followers_count":
            return {"followers_count": 45}
        if params.get("fields") == "followers_count,fan_count":
            return {"followers_count": 12}
        if "threads_insights" in url:
            raise RuntimeError("HTTP 403: missing threads_manage_insights")
        if params.get("fields") == "images":
            return {"images": [{"width": 1080, "source": "https://fbcdn.example/card.jpg"}]}
        return {"status": "FINISHED", "status_code": "FINISHED"}

    def http_post_bytes(self, url, data, headers):
        if "rupload.facebook.com" in url:
            name = self._platform(url)
            self._maybe_fail(name)
            assert data[4:8] == b"ftyp", "not an MP4"
            assert headers.get("file_size") == str(len(data))
            self.calls.append((name, "upload-video", {}))
            return {"success": True}
        self.calls.append(("Bluesky", "upload-blob", {}))
        return {"blob": {"$type": "blob"}}

    # ---- helpers for assertions
    def posts(self, platform):
        """Posts on a platform: the call that carries the post text/image.
        (Threads & Instagram send text when creating the post; the publish step is checked separately.)"""
        if platform in ("Threads", "Instagram"):
            create, publish = {"Threads": ("threads", "threads_publish"), "Instagram": ("media", "media_publish")}[platform]
            made = [c for c in self.calls if c[0] == platform and c[1] == create]
            published = [c for c in self.calls if c[0] == platform and c[1] == publish]
            assert len(made) == len(published), f"{platform}: created {len(made)} but published {len(published)}"
            return made
        final = {"Facebook": "upload-image",
                 "Bluesky": "com.atproto.repo.createRecord", "Telegram": "sendMessage",
                 "Mastodon": "statuses", "Discord": "abc", "X-alert": "sendMessage"}
        return [c for c in self.calls if c[0] == platform and c[1] == final[platform]]


def setup():
    net = FakeInternet()
    d = Path(tempfile.mkdtemp())
    bot.STATE_DIR, bot.ITEMS_FILE, bot.POSTED_FILE = d, d / "items.json", d / "posted.json"
    bot.PRICES_FILE, bot.HEALTH_FILE, bot.PREVIEW_DIR = d / "prices.json", d / "health.json", d / "previews"
    bot.DIGEST_FILE = d / "digest.json"
    bot.config.FEEDS = [{"name": o.upper(), "owner": o, "url": o} for o in OWNERS] + \
        [{"name": "Federal Reserve", "owner": "fed", "official": True, "url": "fed"}]
    bot.config.PRICE_SYMBOLS = [
        {"symbol": "JPY=X", "name": "USD/JPY", "flag": "🇯🇵", "tag": "#USDJPY", "step": 1, "pct": [1, 1.5, 2], "dp": 2}]
    bot.config.MAX_POSTS_PER_RUN = 10
    bot.config.DIGEST_PLATFORMS = ["Facebook", "Instagram"]   # scenarios use Threads to check per-headline posting;
    bot.config.DIGEST_WINDOW_MINUTES = 60                        # the 30-min Threads roundup is in tests/check_update13.py
    bot.config.TRUSTED_OWNERS = []          # scenarios use cnbc/bbc/nikkei as stand-ins; s22 tests trusted
    bot.config.QUIET_ALARM = False          # alarms have their own checks (tests/check_update15.py)
    bot.config.HOURLY_REELS = False         # carousel scenarios; the reel alternation is s42-s45
    bot.config.POST_SPACING_SECONDS = 0
    bot.EXTRAS_FILE, bot.STATS_FILE = d / "extras.json", d / "stats.json"
    bot.config.MARKET_BELLS, bot.config.CALENDAR_ENABLED, bot.config.DAILY_REPORT = [], False, False
    bot.RECAP_FILE = d / "recap.json"
    bot.config.REEL_ENABLED = bot.config.WEEKLY_ENABLED = bot.config.WELCOME_ENABLED = False
    bot.config.REPORT_FOLLOWERS = False
    bot.config.THREADS_MAX_PER_HOUR, bot.config.THREADS_MIN_PRIORITY = 1000, 1
    bot.config.THREADS_MIN_GAP_MINUTES, bot.config.THREADS_DAILY_MAX = 0, 1000
    bot.STATS.clear()
    bot.config.DAILY_RECAP_ENABLED = False
    os.environ.pop("GH_MODELS_TOKEN", None)
    bot.fetch, prices.fetch_quote = net.fetch, net.quote
    bot.http_post, bot.http_post_file = net.http_post, net.http_post_file
    bot.http_get_json, bot.http_post_bytes = net.http_get_json, net.http_post_bytes
    bot.time.sleep = lambda s: None
    bot._bsky_session.clear()
    for k in list(os.environ):
        if k in SECRETS or k in ("DRY_RUN", "BOT_ENABLED", "INSTAGRAM_ACCESS_TOKEN"):
            os.environ.pop(k)
    os.environ.update(SECRETS)
    return net


def run(net, quiet=True):
    net.calls.clear()
    bot._bsky_session.clear()
    if quiet:
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()) as out:
            bot.main()
        return out.getvalue()
    bot.main()
    return ""


def put(net, story_lines: list[str], owners=OWNERS[:3]):
    for o, line in zip(owners, story_lines):
        net.feeds[o].append(line)


NIKKEI = ["Japan's Nikkei jumps 2.4% as yen weakens past 160 per dollar",
          "Nikkei jumps 2.4% in Tokyo as yen weakens past 160",
          "Yen weakens past 160 per dollar, Nikkei jumps 2.4%"]
VOLGOGRAD = ["Russia's Volgograd region reports four dead after Ukrainian attack",
             "Four dead in Volgograd region after Ukrainian attack, Russia says",
             "Ukrainian attack on Russia's Volgograd region leaves four dead"]
MSFT = ["Microsoft outage hits Teams and Outlook users worldwide",
        "Global Microsoft outage hits Outlook and Teams users",
        "Microsoft Teams, Outlook outage hits users worldwide"]
MSFT_UPDATE = ["Microsoft restores Teams and Outlook after outage",
               "Microsoft says Outlook, Teams restored after global outage",
               "Microsoft restores Outlook and Teams services after outage"]
MSFT_LATE_COPY = ["Users worldwide hit by Microsoft Outlook, Teams outage",
                  "Microsoft outage: Teams and Outlook users hit globally",
                  "Microsoft Teams and Outlook outage hits users around the world"]
RUMOUR = ["Apple reportedly in talks to buy Disney", "Apple reportedly eyeing Disney deal, sources say",
          "Apple could buy Disney, sources said"]
LOOKALIKE = ["Asian stocks rise as oil prices fall", "European stocks fall as oil prices rise",
             "US stocks rise while oil prices fall"]
OLD = ["Tesla recalls 200,000 vehicles in US over camera fault",
       "Tesla recalls 200,000 US vehicles over rear camera fault",
       "US: Tesla recalls 200,000 vehicles, camera fault"]


# =============================================================================
# Scenarios
# =============================================================================
def s01_first_run_posts_nothing():
    net = setup()
    put(net, OLD)
    net.quotes["JPY=X"] = (159.5, 159.0)
    run(net)
    assert net.calls == [], net.calls
    assert bot.ITEMS_FILE.exists() and json.loads(bot.PRICES_FILE.read_text())["JPY=X"]["last"] == 159.5
    return "first run saves a baseline and posts nothing"


def s02_full_news_cycle():
    net = setup()
    put(net, OLD); net.quotes["JPY=X"] = (159.5, 159.0)
    run(net)                                                     # baseline
    put(net, NIKKEI); put(net, VOLGOGRAD); put(net, MSFT); put(net, RUMOUR); put(net, LOOKALIKE)
    net.fed += ["Federal Reserve issues FOMC statement",
                "Federal Reserve Board announces termination of enforcement action"]
    net.quotes["JPY=X"] = (160.08, 159.0)
    run(net)
    threads = [c[2]["text"] for c in net.posts("Threads")]
    joined = " | ".join(threads)
    assert any("Nikkei Jumps 2.4%" in t for t in threads), joined
    assert any("Volgograd" in t for t in threads), joined
    assert any("Microsoft" in t for t in threads), joined
    assert any("FOMC Statement" in t for t in threads), joined
    assert any("USD/JPY Rises Above 160, Now At 160.08" in t for t in threads), joined
    assert not any("Disney" in t for t in threads), "rumour posted!"
    assert not any("Asian Stocks" in t or "European Stocks" in t for t in threads), "look-alikes posted!"
    assert not any("Tesla" in t for t in threads), "baseline story posted!"
    assert not any("Enforcement" in t for t in threads), "routine Fed notice posted!"
    assert len(threads) == 5, joined
    return f"5 correct posts out of 9 candidates (rumour, look-alikes, baseline, routine notice all blocked)"


def s03_live_text_now_facebook_instagram_wait_for_digest():
    net = setup()
    run(net)
    put(net, NIKKEI)
    run(net)
    for name in ("Threads", "Bluesky", "Telegram", "Mastodon", "Discord", "X-alert"):
        posts = net.posts(name)
        assert len(posts) == 1, (name, net.calls)
        assert not posts[0][2]["media"], f"{name} got an image"
    assert not any(c[0] in ("Facebook", "Instagram") for c in net.calls), "Facebook/Instagram posted per story"
    assert net.posts("Threads")[0][2]["text"] == "🇯🇵 Nikkei Jumps 2.4% In Tokyo As Yen Weakens Past 160 – BBC"
    q = json.loads(bot.DIGEST_FILE.read_text())["queue"]
    assert len(q) == 1 and "Nikkei" in q[0]["headline"]
    return "headline posted live as text on 6 platforms; Facebook/Instagram queued it for the hourly carousel"


def s04_geopolitics_skips_facebook_instagram():
    net = setup()
    run(net)
    put(net, VOLGOGRAD)
    run(net)
    assert not net.posts("Facebook") and not net.posts("Instagram"), net.calls
    assert len(net.posts("Threads")) == 1 and len(net.posts("Telegram")) == 1
    assert len(json.loads(bot.DIGEST_FILE.read_text())["queue"]) == 1
    return "geopolitics story: live text now, included in the next hourly carousel"


def s05_followup_and_late_copies():
    net = setup()
    run(net)
    put(net, MSFT); run(net)
    assert len(net.posts("Threads")) == 1
    for o in OWNERS[:3]:
        net.feeds[o] = []
    put(net, MSFT_LATE_COPY, OWNERS[1:4]); run(net)
    assert net.posts("Threads") == [], "late copy posted as new story"
    put(net, MSFT_UPDATE); run(net)
    t = net.posts("Threads")
    assert len(t) == 1 and "Restore" in t[0][2]["text"], net.calls
    return "real update posted as follow-up; late copies with nothing new skipped"


def s06_no_repeats_across_runs():
    net = setup()
    run(net)
    put(net, NIKKEI); run(net)
    first = len(net.posts("Threads"))
    run(net); run(net)
    assert first == 1 and net.posts("Threads") == []
    return "same story never posted twice across runs"


def s07_one_platform_down_others_still_post():
    net = setup()
    run(net)
    net.fail = {"Bluesky"}
    put(net, NIKKEI); out = run(net)
    assert not net.posts("Bluesky") and len(net.posts("Threads")) == 1 and len(net.posts("Telegram")) == 1
    assert "Bluesky failed: HTTP 500" in out
    return "Bluesky down: logged with reason, every other platform still posted"


def s08_all_platforms_down_retry_next_run():
    net = setup()
    run(net)
    net.fail = {"Facebook", "Instagram", "Threads", "Bluesky", "Telegram", "Mastodon", "Discord", "X-alert"}
    put(net, NIKKEI); run(net)
    assert json.loads(bot.POSTED_FILE.read_text()) == []
    assert not net.posts("X-alert"), "X link sent although nothing posted"
    assert not json.loads(bot.DIGEST_FILE.read_text())["queue"] if bot.DIGEST_FILE.exists() else True
    net.fail = set(); run(net)
    assert len(net.posts("Threads")) == 1 and len(net.posts("Telegram")) == 1
    assert len(json.loads(bot.DIGEST_FILE.read_text())["queue"]) == 1      # queued for the hourly carousel only once
    return "everything down: story kept, no X alert; posted on the next run once platforms recovered"


def s09_hourly_carousel_on_facebook_and_instagram():
    net = setup()
    put(net, OLD); net.quotes["JPY=X"] = (159.5, 159.0)
    run(net)
    put(net, NIKKEI); put(net, VOLGOGRAD); put(net, MSFT)
    net.quotes["JPY=X"] = (160.08, 159.0)
    run(net)                                                     # 4 headlines go live as text
    assert not any(c[0] in ("Facebook", "Instagram") for c in net.calls)
    age_queue(3600)                                              # ...an hour passes
    run(net)
    fb_feed = [c for c in net.calls if c[0] == "Facebook" and c[1] == "feed"]
    uploads = [c for c in net.calls if c[0] == "Facebook" and c[1] == "upload-image"]
    assert len(fb_feed) == 1 and len(uploads) == 4, net.calls                # 4 headline cards, no cover
    assert all(u[2]["published"] == "false" for u in uploads)
    assert sum(1 for k in fb_feed[0][2] if k.startswith("attached_media")) == 4
    cap = fb_feed[0][2]["text"]
    assert cap.startswith("🕐 Global markets this hour (") and "1. " in cap and "4. " in cap, cap
    ig = [c for c in net.calls if c[0] == "Instagram"]
    children = [c for c in ig if c[1] == "media" and c[2].get("is_carousel_item") == "true"]
    parent = [c for c in ig if c[1] == "media" and c[2].get("children")]
    assert len(children) == 4 and len(parent) == 1 and len(parent[0][2]["children"].split(",")) == 4, ig
    assert [c for c in ig if c[1] == "media_publish"], ig
    assert not net.posts("Threads"), "text platforms re-posted"
    run(net)
    assert not any(c[0] in ("Facebook", "Instagram") for c in net.calls), "digest posted twice"
    return "after the hour: ONE Facebook post + ONE Instagram carousel (4 headline cards), not repeated"


def s10_dry_run_sends_nothing_but_makes_previews():
    net = setup()
    run(net)
    os.environ["DRY_RUN"] = "true"
    put(net, NIKKEI); out = run(net)
    os.environ.pop("DRY_RUN")
    assert net.calls == [] and "DRY_RUN - not posted" in out
    previews = list(bot.PREVIEW_DIR.glob("*.jpg"))
    assert len(previews) == 1 and previews[0].read_bytes()[:2] == b"\xff\xd8"
    return "DRY_RUN: nothing sent anywhere, card preview saved"


def s11_kill_switch():
    net = setup()
    run(net)
    os.environ["BOT_ENABLED"] = "false"
    put(net, NIKKEI); out = run(net)
    os.environ.pop("BOT_ENABLED")
    assert net.calls == [] and "kill switch" in out
    return "BOT_ENABLED=false: does nothing"


def s12_no_pillow_text_still_works():
    net = setup()
    run(net)
    real = images.available
    images.available = lambda: False
    try:
        put(net, NIKKEI); run(net)
    finally:
        images.available = real
    assert not net.posts("Facebook") and not net.posts("Instagram") and len(net.posts("Threads")) == 1
    return "Pillow missing: Facebook/Instagram skipped, text platforms unaffected"


def s13_only_some_secrets():
    net = setup()
    run(net)
    for k in list(SECRETS):
        if not k.startswith(("THREADS", "TELEGRAM")):
            os.environ.pop(k)
    put(net, NIKKEI); out = run(net)
    assert "Auto-posting to: Threads, Telegram" in out, out
    assert len(net.posts("Threads")) == 1 and len(net.posts("Telegram")) == 1 and not net.posts("Facebook")
    return "only Threads + Telegram set up: posts there, skips the rest quietly"


def s14_feed_outage_health_alert():
    net = setup()
    put(net, OLD, OWNERS)
    run(net)
    assert not [c for c in net.calls if "news feeds working" in c[2]["text"]], "false alarm"
    bot.fetch = lambda url, timeout=15: None if url in OWNERS + ["fed"] else b"<rss/>"
    run(net)
    warn = [c for c in net.calls if c[0] == "X-alert" and "news feeds working" in c[2]["text"]]
    assert len(warn) == 1, net.calls
    run(net)
    assert not [c for c in net.calls if "news feeds working" in c[2]["text"]], "warning repeated within 6h"
    return "most feeds down: one private Telegram warning, not repeated"


def s15_daily_post_limit():
    net = setup()
    run(net)
    old_lim, lim = bot.config.MAX_POSTS_PER_DAY, 50      # live setting is 0 = unlimited; test the cap logic
    bot.config.MAX_POSTS_PER_DAY = lim
    try:
        fake = [{"ts": time.time() - 60, "text": "x", "words": [], "item_ids": [], "story_id": f"s{i}",
                 "platforms": []} for i in range(lim)]
        bot.POSTED_FILE.write_text(json.dumps(fake))
        put(net, NIKKEI); run(net)
        assert net.posts("Threads") == []
    finally:
        bot.config.MAX_POSTS_PER_DAY = old_lim
    return f"optional daily limit ({lim}) reached: nothing more posted (default is unlimited)"


def s20_price_alerts_never_crowd_out_news():
    net = setup()
    bot.config.MAX_POSTS_PER_RUN = 2
    bot.config.PRICE_SYMBOLS = [
        {"symbol": s, "name": n, "flag": "", "tag": "", "step": 0, "pct": [2], "dp": 0}
        for s, n in [("A", "Gold"), ("B", "Silver"), ("C", "Oil"), ("D", "Bitcoin")]]
    for s in "ABCD":
        net.quotes[s] = (100.0, 100.0)
    put(net, OLD); run(net)                                   # baseline (no moves yet)
    for s in "ABCD":
        net.quotes[s] = (95.0, 100.0)                         # 4 markets fall 5%...
    put(net, NIKKEI); put(net, MSFT); put(net, VOLGOGRAD)     # ...while 3 news stories break
    run(net)
    texts = [c[2]["text"] for c in net.posts("Threads")]
    news = [t for t in texts if "On The Day" not in t]
    alerts = [t for t in texts if "On The Day" in t]
    assert len(news) == 2 and len(alerts) == 4, texts         # news uses its 2 slots, alerts all still post
    return "busy market: 2 news slots used AND all 4 price alerts posted (alerts have their own allowance)"


def s21_no_stale_alerts_after_setup():
    net = setup()
    bot.config.PRICE_SYMBOLS = [{"symbol": "G", "name": "Gold", "flag": "", "tag": "", "step": 0, "pct": [2, 3], "dp": 1}]
    net.quotes["G"] = (3727.2, 3862.0)                        # already -3.5% when the bot starts
    run(net)
    net.quotes["G"] = (3725.0, 3862.0)
    run(net)
    assert not net.posts("Threads"), "posted a move that happened before the bot started"
    net.quotes["G"] = (3700.0, 3862.0)                        # still within the -3% level: nothing new
    run(net)
    assert not net.posts("Threads")
    return "moves that happened before setup are not posted as 'news' (the day-one burst you saw)"


def s22_trusted_outlet_breaking_news_posts_alone():
    net = setup()
    bot.config.TRUSTED_OWNERS = ["cnbc"]
    run(net)
    net.feeds["cnbc"].append("Nvidia names Colette Kress permanent CEO")
    net.feeds["guardian"].append("Nvidia board meets to discuss leadership")          # untrusted single: waits
    run(net)
    t = [c[2]["text"] for c in net.posts("Threads")]
    assert t == ["🇺🇸 Nvidia Names Colette Kress Permanent CEO – CNBC"], t
    net.feeds["bbc"].append("Nvidia names Kress as permanent chief executive")       # later copy: not reposted
    run(net)
    assert net.posts("Threads") == []
    return "trusted outlet (CNBC) breaking headline posted alone; untrusted single waited; later copy skipped"


def s23_old_leftovers_never_reach_the_carousel():
    net = setup()
    run(net)
    put(net, NIKKEI); run(net)
    age_queue(5 * 3600)                                       # e.g. queued in test mode hours ago
    put(net, MSFT); run(net)
    age_queue(3600); run(net)
    ig = [c for c in net.calls if c[0] == "Instagram" and c[1] == "media"]
    assert len(ig) == 1 and not ig[0][2].get("children"), ig   # only the fresh Microsoft story, as a single image
    return "headlines older than 2 hours are dropped from the hourly carousel (no stale leftovers)"


def age_queue(seconds):
    """Pretend time passed: move everything in the digest queue back in time."""
    st = json.loads(bot.DIGEST_FILE.read_text())
    for q in st["queue"]:
        q["ts"] -= seconds
    bot.DIGEST_FILE.write_text(json.dumps(st))


def s16_single_story_hour_posts_one_image():
    net = setup()
    run(net)
    put(net, NIKKEI); run(net)
    age_queue(3600); run(net)
    fb = [c for c in net.calls if c[0] == "Facebook"]
    assert len(fb) == 1 and fb[0][1] == "upload-image" and fb[0][2]["published"] == "true", fb
    ig = [c for c in net.calls if c[0] == "Instagram" and c[1] == "media"]
    assert len(ig) == 1 and not ig[0][2].get("children") and not ig[0][2].get("is_carousel_item"), ig
    return "only 1 headline in the hour: a normal single image (no cover slide) on Facebook + Instagram"


def s17_quiet_hour_posts_nothing():
    net = setup()
    run(net)
    run(net); run(net)
    assert not any(c[0] in ("Facebook", "Instagram") for c in net.calls)
    return "no headlines in the hour: no Facebook/Instagram post"


def s18_instagram_down_retried_without_duplicating_facebook():
    net = setup()
    run(net)
    put(net, NIKKEI); put(net, MSFT); run(net)
    age_queue(3600)
    net.fail = {"Instagram"}
    out = run(net)
    assert len([c for c in net.calls if c[0] == "Facebook" and c[1] == "feed"]) == 1 and "Instagram digest failed" in out
    net.fail = set()
    run(net)
    assert not [c for c in net.calls if c[0] == "Facebook" and c[1] == "feed"], "Facebook posted twice"
    assert [c for c in net.calls if c[0] == "Instagram" and c[1] == "media_publish"], "Instagram not retried"
    return "Instagram down at the hour: Facebook posted once, Instagram retried next run and succeeded"


def s19_dry_run_digest_previews():
    net = setup()
    run(net)
    os.environ["DRY_RUN"] = "true"
    put(net, NIKKEI); put(net, MSFT); run(net)
    age_queue(3600); out = run(net)
    os.environ.pop("DRY_RUN")
    slides = sorted(bot.PREVIEW_DIR.glob("digest_*.jpg"))
    assert net.calls == [] and len(slides) == 2 and "digest not posted" in out, (out, slides)
    return "DRY_RUN: hourly carousel saved as preview slides (2 headline cards), nothing posted"


# ---- update 7: breaking label, market open/close, calendar, daily report -----
import datetime as _dt
_REAL_TIME = time.time


def at_et(y, mo, d, h, mi):
    """Unix time for a New York wall-clock time (EST in November = UTC-5)."""
    return _dt.datetime(y, mo, d, h + 5, mi, tzinfo=_dt.timezone.utc).timestamp() if h + 5 < 24 else \
        _dt.datetime(y, mo, d, h + 5 - 24, mi, tzinfo=_dt.timezone.utc).timestamp() + 86400


def run_at(net, ts):
    bot.time.time = lambda: ts
    try:
        return run(net)
    finally:
        bot.time.time = _REAL_TIME


def s24_breaking_label_on_big_news_only():
    net = setup()
    run(net)
    put(net, NIKKEI)
    net.fed += ["Federal Reserve issues FOMC statement"]
    run(net)
    texts = [c[2]["text"] for c in net.posts("Threads")]
    fomc = [t for t in texts if "FOMC" in t][0]
    nikkei = [t for t in texts if "Nikkei" in t][0]
    assert fomc.startswith("🔴 BREAKING: "), fomc
    assert "BREAKING" not in nikkei, nikkei
    # daily cap
    old = bot.config.BREAKING_MAX_PER_DAY
    bot.config.BREAKING_MAX_PER_DAY = 1
    try:
        net.fed += ["Federal Reserve announces emergency rate decision"]
        run(net)
        later = [c[2]["text"] for c in net.posts("Threads")]
        assert later and not any("BREAKING" in t for t in later), later
    finally:
        bot.config.BREAKING_MAX_PER_DAY = old
    return "Fed statement labelled 🔴 BREAKING, ordinary market story not; daily cap respected"


def _bell_setup(net):
    bot.config.MARKET_BELLS = ORIG_BELLS
    bot.config.PRICE_SYMBOLS = ORIG_SYMBOLS
    for sym, (p, prev) in {"^GSPC": (6810.4, 6782.0), "^IXIC": (23450, 23310), "^DJI": (47120, 47170),
                           "^VIX": (15.2, 15.7), "DX-Y.NYB": (99.1, 99.0), "GC=F": (3750.9, 3721.0),
                           "CL=F": (61.2, 61.9), "BTC-USD": (91000, 90100)}.items():
        net.quotes[sym] = (p, prev)


def s25_us_close_summary_once_per_day():
    net = setup()
    _bell_setup(net)
    try:
        run_at(net, at_et(2026, 11, 18, 15, 50))        # baseline run (Wednesday)
        run_at(net, at_et(2026, 11, 18, 16, 6))
        posts = [c[2]["text"] for c in net.posts("Threads")]
        assert len(posts) == 1 and posts[0].startswith("🔔 US Stocks Close\nS&P 500 6,810 ▲ +0.42%"), posts
        assert "Nasdaq 23,450" in posts[0] and "Dow Jones 47,120 ▼ -0.11%" in posts[0], posts[0]
        assert "Gold $3,750.9" in posts[0], posts[0]
        assert len(net.posts("Telegram")) == 1 and len(net.posts("X-alert")) == 1
        assert not any(c[0] in ("Facebook", "Instagram") for c in net.calls)
        run_at(net, at_et(2026, 11, 18, 16, 11))
        assert not net.posts("Threads"), "close summary repeated"
        # Saturday: nothing
        run_at(net, at_et(2026, 11, 21, 16, 6))
        assert not net.posts("Threads"), "posted on a weekend"
    finally:
        bot.config.MARKET_BELLS, bot.config.PRICE_SYMBOLS = [], ORIG_SYMBOLS
    return "🔔 US close summary posted once at 4:05 PM (indices, VIX, dollar, gold, oil, Bitcoin); no repeat, none at weekends"


def s26_market_holiday_no_summary():
    net = setup()
    _bell_setup(net)
    stale = at_et(2026, 11, 25, 16, 0)                    # last trade the day before
    net.quote = lambda sym: (net.quotes[sym][0], net.quotes[sym][1], int(stale)) if sym in net.quotes else None
    prices.fetch_quote = net.quote
    try:
        run_at(net, at_et(2026, 11, 26, 9, 0))           # Thanksgiving
        run_at(net, at_et(2026, 11, 26, 9, 36))
        assert not net.posts("Threads"), net.posts("Threads")
    finally:
        bot.config.MARKET_BELLS, bot.config.PRICE_SYMBOLS = [], ORIG_SYMBOLS
    return "market holiday (no fresh prices): no open summary posted"


CAL_JSON = json.dumps([
    {"title": "CPI y/y", "country": "USD", "date": "2026-11-18T08:30:00-05:00", "impact": "High",
     "forecast": "2.9%", "previous": "3.0%"},
    {"title": "Core CPI m/m", "country": "USD", "date": "2026-11-18T08:30:00-05:00", "impact": "High",
     "forecast": "0.3%", "previous": "0.3%"},
    {"title": "Crude Oil Inventories", "country": "USD", "date": "2026-11-18T10:30:00-05:00", "impact": "Medium",
     "forecast": "", "previous": "1.2M"},
    {"title": "Bank Holiday", "country": "JPY", "date": "2026-11-18T00:00:00-05:00", "impact": "Holiday"},
    {"title": "AUD Employment Change", "country": "AUD", "date": "2026-11-18T19:30:00-05:00", "impact": "High"},
]).encode()


def s27_economic_calendar_morning_list_and_heads_up():
    net = setup()
    bot.config.CALENDAR_ENABLED = True
    real_fetch = net.fetch
    net.fetch = bot.fetch = lambda url, timeout=15: CAL_JSON if url == bot.config.CALENDAR_URL else real_fetch(url)
    try:
        run_at(net, at_et(2026, 11, 18, 6, 0))            # baseline
        run_at(net, at_et(2026, 11, 18, 7, 5))
        daily = [c[2]["text"] for c in net.posts("Threads")]
        assert len(daily) == 1 and daily[0].startswith("🗓 Today's Key Data (EST)"), daily
        assert "8:30 AM 🇺🇸 CPI y/y (F 2.9%)" in daily[0] and "Crude" not in daily[0] and "AUD" not in daily[0], daily
        run_at(net, at_et(2026, 11, 18, 8, 10))
        assert not net.posts("Threads"), "heads-up too early"
        run_at(net, at_et(2026, 11, 18, 8, 15))
        hu = [c[2]["text"] for c in net.posts("Threads")]
        assert len(hu) == 1 and hu[0].startswith("⏰ Coming Up At 8:30 AM EST\n🇺🇸 CPI y/y – Forecast 2.9%, Previous 3.0%"), hu
        assert "Core CPI m/m" in hu[0]
        run_at(net, at_et(2026, 11, 18, 8, 20))
        assert not net.posts("Threads"), "heads-up repeated"
        run_at(net, at_et(2026, 11, 18, 7, 10))
        assert not net.posts("Threads"), "morning list repeated"
    finally:
        bot.config.CALENDAR_ENABLED = False
    return "7 AM 'Today's key data' list + one '⏰ Coming up' 15 min before CPI; no repeats, medium/other countries filtered"


def s28_calendar_down_never_breaks_news():
    net = setup()
    bot.config.CALENDAR_ENABLED = True
    try:
        run(net)
        put(net, NIKKEI)
        run(net)                                            # calendar URL returns junk in the fake internet
        assert len(net.posts("Threads")) == 1
    finally:
        bot.config.CALENDAR_ENABLED = False
    return "calendar unavailable: news still posts normally"


def s29_daily_report_in_private_chat():
    net = setup()
    bot.config.DAILY_REPORT = True
    try:
        run_at(net, at_et(2026, 11, 18, 20, 0))
        put(net, NIKKEI)
        net.fail = {"Mastodon"}
        run_at(net, at_et(2026, 11, 18, 20, 30))
        net.fail = set()
        run_at(net, at_et(2026, 11, 18, 21, 5))
        msgs = [c[2]["text"] for c in net.posts("X-alert") if c[2]["text"].startswith("📊")]
        assert len(msgs) == 1, net.calls
        r = msgs[0]
        assert "Headlines: 1" in r and "Threads 1" in r and "Mastodon 0" in r, r
        assert "Errors: Mastodon 1" in r and "⚠️ Check: Mastodon posted nothing" in r, r
        run_at(net, at_et(2026, 11, 18, 21, 10))
        assert not [c for c in net.posts("X-alert") if c[2]["text"].startswith("📊")], "report sent twice"
    finally:
        bot.config.DAILY_REPORT = False
    return "9 PM report in your private chat: counts per platform, errors with last message, warning flags"


# ---- update 8: daily reel, weekly recap, welcome post, follower counts ----------
def _three_stories(net, ts):
    put(net, NIKKEI); put(net, VOLGOGRAD)
    net.fed.append("Federal Reserve issues FOMC statement")
    run_at(net, ts)


def s30_daily_reel_with_music_on_instagram_facebook_telegram():
    net = setup()
    bot.config.REEL_ENABLED = True
    try:
        run_at(net, at_et(2026, 11, 18, 17, 0))              # baseline
        _three_stories(net, at_et(2026, 11, 18, 17, 10))
        run_at(net, at_et(2026, 11, 18, 18, 5))               # hourly carousel goes out
        assert not [c for c in net.calls if c[1] == "upload-video"], "reel too early"
        run_at(net, at_et(2026, 11, 18, 18, 35))
        ig = [c for c in net.calls if c[0] == "Instagram"]
        assert [c[1] for c in ig] == ["media", "upload-video", "media_publish"], ig
        assert ig[0][2]["text"].startswith("📰 Today's top 3 stories"), ig[0]
        fb = [c[1] for c in net.calls if c[0] == "Facebook"]
        assert fb == ["video_reels", "upload-video", "video_reels"], fb
        tg = [c for c in net.calls if c[0] == "Telegram" and c[1] == "upload-video"]
        assert len(tg) == 1 and "FOMC" in tg[0][2]["text"], tg
        run_at(net, at_et(2026, 11, 18, 18, 40))
        assert not [c for c in net.calls if c[1] == "upload-video"], "reel posted twice"
    finally:
        bot.config.REEL_ENABLED = False
    return "6:30 PM: one reel (top stories + music) on Instagram Reels, Facebook Reels and Telegram; not repeated"


def s31_reel_instagram_down_retried_only_there():
    net = setup()
    bot.config.REEL_ENABLED = True
    try:
        run_at(net, at_et(2026, 11, 18, 17, 0))
        _three_stories(net, at_et(2026, 11, 18, 17, 10))
        run_at(net, at_et(2026, 11, 18, 18, 5))
        net.fail = {"Instagram"}
        run_at(net, at_et(2026, 11, 18, 18, 35))
        assert len([c for c in net.calls if c[0] == "Facebook" and c[1] == "upload-video"]) == 1
        net.fail = set()
        run_at(net, at_et(2026, 11, 18, 18, 40))
        assert [c[1] for c in net.calls if c[0] == "Instagram"] == ["media", "upload-video", "media_publish"]
        assert not [c for c in net.calls if c[0] in ("Facebook", "Telegram") and c[1] == "upload-video"]
    finally:
        bot.config.REEL_ENABLED = False
    return "Instagram down at reel time: retried next run; Facebook/Telegram not duplicated"


def s32_quiet_day_no_reel():
    net = setup()
    bot.config.REEL_ENABLED = True
    try:
        run_at(net, at_et(2026, 11, 18, 17, 0))
        put(net, NIKKEI)
        run_at(net, at_et(2026, 11, 18, 17, 10))
        run_at(net, at_et(2026, 11, 18, 18, 35))
        assert not [c for c in net.calls if c[1] == "upload-video"]
    finally:
        bot.config.REEL_ENABLED = False
    return "fewer than 3 stories in the day: no reel"


def s33_weekly_recap_sunday():
    net = setup()
    bot.config.WEEKLY_ENABLED = True
    try:
        run_at(net, at_et(2026, 11, 17, 9, 0))
        put(net, NIKKEI); run_at(net, at_et(2026, 11, 17, 9, 10))
        put(net, VOLGOGRAD); run_at(net, at_et(2026, 11, 19, 9, 10))
        net.fed.append("Federal Reserve issues FOMC statement"); run_at(net, at_et(2026, 11, 20, 14, 0))
        net.feeds = {o: [] for o in OWNERS}; net.fed = []          # old headlines have left the feeds
        run_at(net, at_et(2026, 11, 22, 11, 5))                    # Sunday
        fb = [c for c in net.calls if c[0] == "Facebook" and c[1] == "feed"]
        assert len(fb) == 1 and fb[0][2]["text"].startswith("📅 The Week In Markets (16 Nov–22 Nov)"), net.calls
        ig = [c for c in net.calls if c[0] == "Instagram"]
        assert sum(1 for c in ig if c[2].get("is_carousel_item")) == 3, ig      # 3 cards
        assert [c[1] for c in ig].count("media_publish") == 1, ig               # one carousel
        th = [c[2]["text"] for c in net.posts("Threads")]
        assert len(th) == 1 and th[0].startswith("📅 The Week In Markets") and "1. " in th[0] and len(th[0]) <= 500
        run_at(net, at_et(2026, 11, 22, 11, 10))
        assert not net.posts("Threads"), "weekly posted twice"
    finally:
        bot.config.WEEKLY_ENABLED = False
    return "Sunday 11 AM: 'The Week In Markets' carousel on Facebook + Instagram, list on Threads/Telegram"


def s34_welcome_post_once_and_pinned():
    net = setup()
    bot.config.WELCOME_ENABLED = True
    try:
        run(net)
        run(net)
        tg = [c[2]["text"] for c in net.posts("Telegram")]
        assert len(tg) == 1 and tg[0].startswith("👋 Welcome to News Before Noise"), tg
        assert len(net.posts("Threads")) == 1
        assert any(c[1] == "pinChatMessage" for c in net.calls), "not pinned"
        run(net)
        assert not net.posts("Telegram"), "welcome repeated"
    finally:
        bot.config.WELCOME_ENABLED = False
    return "welcome post once on Telegram (pinned) and Threads; never repeated"


def s35_followers_in_daily_report():
    net = setup()
    bot.config.DAILY_REPORT = bot.config.REPORT_FOLLOWERS = True
    try:
        run_at(net, at_et(2026, 11, 18, 20, 0))
        put(net, NIKKEI); run_at(net, at_et(2026, 11, 18, 20, 30))
        run_at(net, at_et(2026, 11, 18, 21, 5))
        r = [c[2]["text"] for c in net.posts("X-alert") if c[2]["text"].startswith("📊")][0]
        assert "👥 Followers: Telegram 120 | Instagram 45 | Facebook 12 | Threads n/a" in r, r
    finally:
        bot.config.DAILY_REPORT = bot.config.REPORT_FOLLOWERS = False
    return "daily report shows followers per platform (Threads 'n/a' until insights permission is added)"



def s36_threads_paced_telegram_gets_everything():
    net = setup()
    bot.config.THREADS_MAX_PER_HOUR, bot.config.THREADS_MIN_PRIORITY = 2, 3
    run(net)
    put(net, NIKKEI); put(net, VOLGOGRAD)
    net.fed += ["Federal Reserve issues FOMC statement", "Federal Reserve Board announces discount rate decision"]
    run(net)
    th = [c[2]["text"] for c in net.posts("Threads")]
    tg = [c[2]["text"] for c in net.posts("Telegram")]
    assert len(tg) == 4, tg
    assert len(th) == 2 and not any("Volgograd" in t for t in th), th
    return "Threads: max 2/hour here (3 live), markets/breaking only; Telegram still got all 4"



def s37_youtube_short_and_private_copy():
    net = setup()
    bot.config.REEL_ENABLED = True
    os.environ.update({"YT_CLIENT_ID": "cid", "YT_CLIENT_SECRET": "sec", "YT_REFRESH_TOKEN": "rt"})
    uploads = []
    real = (bot.youtube_access_token, bot.youtube_upload)
    bot.youtube_access_token = lambda: "AT"
    bot.youtube_upload = lambda video, meta, token: uploads.append((video, meta, token)) or "YTID"
    try:
        run_at(net, at_et(2026, 11, 18, 17, 0))
        _three_stories(net, at_et(2026, 11, 18, 17, 10))
        run_at(net, at_et(2026, 11, 18, 18, 5))
        run_at(net, at_et(2026, 11, 18, 18, 35))
        assert len(uploads) == 1, uploads
        video, meta, token = uploads[0]
        assert video[4:8] == b"ftyp" and token == "AT"
        t = meta["snippet"]["title"]
        assert t.endswith("#Shorts") and len(t) <= 100 and "18 Nov 2026" in t, t
        assert meta["snippet"]["categoryId"] == "25" and meta["status"]["selfDeclaredMadeForKids"] is False
        priv = [c for c in net.calls if c[0] == "X-alert" and c[1] == "upload-video"]
        assert len(priv) == 1 and priv[0][2]["text"].startswith("🎬 Today's reel"), priv
        run_at(net, at_et(2026, 11, 18, 18, 40))
        assert len(uploads) == 1, "uploaded twice"
    finally:
        bot.config.REEL_ENABLED = False
        bot.youtube_access_token, bot.youtube_upload = real
        for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
            os.environ.pop(k, None)
    return "YouTube Short uploaded once (title, #Shorts, News category) + copy in your private chat"



INDIA = [["RBI keeps repo rate unchanged at 6.5% as India inflation eases",
          "India's RBI holds repo rate at 6.5% as inflation eases",
          "RBI leaves repo rate at 6.5%, India inflation eases"],
         ["India's Sensex closes at record high as Reliance and HDFC Bank rally",
          "Sensex hits record close in India as Reliance, HDFC Bank rally",
          "India Sensex record close led by Reliance and HDFC Bank rally"],
         ["Infosys wins $2 billion AI deal, India IT stocks climb",
          "India's Infosys bags $2 billion AI contract, IT stocks climb",
          "Infosys signs $2 billion AI deal; India IT shares climb"]]


def _recap_day(net, ed):
    import daily_recap
    calls = []
    def fake_ai(prompt, token):
        calls.append(prompt)
        n = prompt.count("Headline:")
        paras = [f"{i}. Paragraph about story {i} with 2.4% from the summary (BBC)." for i in range(1, n + 1)]
        paras[1] = "2. This one invents a number: shares jumped 37.9% (BBC)."        # not in the material
        return "\n\n".join(paras)
    daily_recap.ai_write = fake_ai
    return calls


def s38_daily_us_recap_ai_with_fact_check():
    import daily_recap
    real = daily_recap.ai_write
    net = setup()
    bot.config.DAILY_RECAP_ENABLED = True
    os.environ["GH_MODELS_TOKEN"] = "ghtok"
    try:
        calls = _recap_day(net, "us")
        run_at(net, at_et(2026, 11, 18, 9, 0))
        put(net, NIKKEI); run_at(net, at_et(2026, 11, 18, 10, 0))
        put(net, VOLGOGRAD); run_at(net, at_et(2026, 11, 18, 12, 0))
        net.fed.append("Federal Reserve issues FOMC statement"); run_at(net, at_et(2026, 11, 18, 14, 0))
        run_at(net, at_et(2026, 11, 18, 17, 20))
        assert len(calls) == 1 and "Stories:" in calls[0]
        tg = [c[2]["text"] for c in net.posts("Telegram") if "GLOBAL MARKETS TODAY" in c[2]["text"]]
        assert len(tg) == 1, net.calls
        t = tg[0]
        assert "1. Paragraph about story 1 with 2.4%" in t, t
        assert "37.9%" not in t and "\n2. " in t, t                         # invented number removed
        fb = [c for c in net.calls if c[0] == "Facebook" and c[1] == "feed" and "GLOBAL MARKETS" in c[2]["text"]]
        assert len(fb) == 1
        th = [c[2]["text"] for c in net.posts("Threads") if "GLOBAL MARKETS" in c[2]["text"]]
        assert len(th) == 1 and "t.me/NewsB4Noise" in th[0] and len(th[0]) <= 500, th
        priv = [c for c in net.posts("X-alert") if c[2]["text"].startswith("📝 Daily recap")]
        assert len(priv) == 1
        run_at(net, at_et(2026, 11, 18, 17, 25))
        assert not [c for c in net.posts("Telegram") if "GLOBAL MARKETS" in c[2]["text"]], "recap twice"
    finally:
        daily_recap.ai_write = real
        bot.config.DAILY_RECAP_ENABLED = False
        os.environ.pop("GH_MODELS_TOKEN", None)
    return "5:15 PM: AI-written recap on Telegram + Facebook, short version on Threads; made-up number caught"


def s39_daily_recap_without_ai_posts_plain_list():
    net = setup()
    bot.config.DAILY_RECAP_ENABLED = True
    try:
        run_at(net, at_et(2026, 11, 18, 9, 0))
        put(net, NIKKEI); run_at(net, at_et(2026, 11, 18, 10, 0))
        put(net, VOLGOGRAD); run_at(net, at_et(2026, 11, 18, 12, 0))
        net.fed.append("Federal Reserve issues FOMC statement"); run_at(net, at_et(2026, 11, 18, 14, 0))
        run_at(net, at_et(2026, 11, 18, 17, 20))                       # no GH_MODELS_TOKEN -> plain list
        t = [c[2]["text"] for c in net.posts("Telegram") if "GLOBAL MARKETS" in c[2]["text"]][0]
        assert "1. Federal Reserve Issues FOMC Statement" in t and "Not financial advice" in t, t
    finally:
        bot.config.DAILY_RECAP_ENABLED = False
    return "AI unavailable: recap still posts as a clean numbered list"


def s40_india_recap_only_india_stories():
    net = setup()
    bot.config.DAILY_RECAP_ENABLED = True
    try:
        # India day: 9 AM - 3 PM IST = 22:30 - 04:30 ET (previous evening)
        run_at(net, at_et(2026, 11, 17, 22, 0))
        put(net, NIKKEI); run_at(net, at_et(2026, 11, 17, 23, 0))
        for st in INDIA:
            put(net, st); run_at(net, at_et(2026, 11, 18, 1, 0) + 600 * INDIA.index(st))
        run_at(net, at_et(2026, 11, 18, 6, 5))                          # 4:35 PM IST
        t = [c[2]["text"] for c in net.posts("Telegram") if "INDIA MARKETS" in c[2]["text"]]
        assert len(t) == 1, [c[2]["text"][:60] for c in net.posts("Telegram")]
        assert "Repo Rate" in t[0] and "Sensex" in t[0] and "Infosys" in t[0] and "Yen" not in t[0], t[0]
    finally:
        bot.config.DAILY_RECAP_ENABLED = False
    return "4:30 PM IST: India edition with only India stories (Japan story left for the global edition)"


def s41_threads_block_triggers_cooldown():
    net = setup()
    real = bot.post_threads
    calls = []
    def blocked(p):
        calls.append(p)
        raise RuntimeError('HTTP 400: {"error":{"code":1,"error_subcode":2207051,"error_user_msg":"We restrict certain activity"}}')
    bot.post_threads = blocked
    bot.PLATFORMS["Threads"] = (blocked, bot.PLATFORMS["Threads"][1])
    try:
        run(net)
        put(net, NIKKEI)
        run(net)
        assert len(calls) == 1, calls                      # first try is blocked...
        net.fed += ["Federal Reserve issues FOMC statement", "Federal Reserve Board announces discount rate decision"]
        run(net)
        assert len(calls) == 1, "kept hammering Threads during cooldown"
        tg = [c[2]["text"] for c in net.posts("Telegram")]
        assert len(tg) == 2, tg                             # ...but Telegram keeps going
    finally:
        bot.post_threads = real
        bot.PLATFORMS["Threads"] = (real, bot.PLATFORMS["Threads"][1])
    return "Threads 'restricted activity' block -> 6h quiet period, Telegram unaffected"


# --- update 16: hourly carousel / reel alternation ---------------------------
def _reel_setup(net, video_ok=True):
    bot.config.HOURLY_REELS = True
    bot.config.HOURLY_REEL_PLATFORMS = ["Instagram", "Facebook", "YouTube"]
    bot.config.HOURLY_REEL_EVERY_HOURS = 2
    bot.config.HOURLY_REEL_MIN_STORIES = 3
    bot.config.DIGEST_PLATFORM_WINDOWS = {"Instagram": 60, "Facebook": 60}
    reels = []
    def fake_build(items, window, when):
        if not video_ok:
            raise RuntimeError("ffmpeg not available")
        return {"video": b"MP4", "caption": f"Top {len(items)} " + window, "count": len(items),
                "title": items[0]["headline"], "keys": []}
    bot.recap.build_hour_reel = fake_build
    for n in ("Instagram", "Facebook", "YouTube"):
        bot.REEL_POSTERS[n] = (lambda rl, n=n: reels.append((n, rl)) or f"{n}-reel", bot.REEL_POSTERS[n][1])
    os.environ.update({"YT_CLIENT_ID": "x", "YT_CLIENT_SECRET": "x", "YT_REFRESH_TOKEN": "x"})
    return reels


_ORIG_REEL = dict(bot.REEL_POSTERS)
_ORIG_BUILD = bot.recap.build_hour_reel


def _reel_teardown():
    bot.REEL_POSTERS.update(_ORIG_REEL)
    bot.recap.build_hour_reel = _ORIG_BUILD
    bot.config.HOURLY_REELS = False
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        os.environ.pop(k, None)


def _reel_stories(net, t):
    run_at(net, t)
    put(net, NIKKEI); put(net, VOLGOGRAD); put(net, MSFT)
    run_at(net, t + 60)


def s42_odd_hour_reel_even_hour_carousel():
    net = setup()
    reels = _reel_setup(net)
    try:
        _reel_stories(net, at_et(2026, 11, 20, 10, 5))          # stories 10:05 -> roundup at 11:00 (odd)
        run_at(net, at_et(2026, 11, 20, 11, 1))
        names = sorted(n for n, _ in reels)
        assert names == ["Facebook", "Instagram", "YouTube"], names
        assert not [c for c in net.calls if c[0] == "Facebook" and c[1] == "feed"], "carousel posted at reel hour"
        assert not net.posts("Instagram")
        reels.clear()
        put(net, MSFT_UPDATE); put(net, RUMOUR)                    # new stories 11:10 -> 12:00 (even)
        run_at(net, at_et(2026, 11, 20, 11, 10))
        run_at(net, at_et(2026, 11, 20, 12, 1))
        assert not reels, reels
        assert [c for c in net.calls if c[0] == "Facebook" and c[2].get("published") != "false"], net.calls
        assert len([c for c in net.calls if c[0] == "Instagram" and c[1] == "media_publish"]) == 1
    finally:
        _reel_teardown()
    return "11 AM: reel on Facebook + Instagram + YouTube (no carousel); 12 PM: carousel, no reel"


def s43_few_stories_carousel_youtube_waits():
    net = setup()
    reels = _reel_setup(net)
    try:
        run_at(net, at_et(2026, 11, 20, 12, 5))
        put(net, NIKKEI)
        run_at(net, at_et(2026, 11, 20, 12, 6))                  # one headline only
        run_at(net, at_et(2026, 11, 20, 13, 1))
        assert not reels, reels
        assert len([c for c in net.calls if c[0] == "Instagram" and c[1] == "media_publish"]) == 1
        hold = json.loads(bot.DIGEST_FILE.read_text())["hold"]
        assert len(hold.get("YouTube", [])) == 1, hold            # YouTube keeps it for its next reel
    finally:
        _reel_teardown()
    return "1 headline at a reel hour: normal post on Facebook/Instagram; YouTube waits (no thin reel)"


def s44_no_video_tool_falls_back_to_carousel():
    net = setup()
    reels = _reel_setup(net, video_ok=False)
    try:
        _reel_stories(net, at_et(2026, 11, 20, 14, 5))
        run_at(net, at_et(2026, 11, 20, 15, 1))
        assert not reels
        assert len([c for c in net.calls if c[0] == "Instagram" and c[1] == "media_publish"]) == 1
        assert len([c for c in net.calls if c[0] == "Facebook" and c[1] == "feed"]) == 1
    finally:
        _reel_teardown()
    return "video tool missing at a reel hour: Facebook/Instagram post the carousel instead; YouTube skipped"


def s45_ambiguous_reel_error_never_reposts():
    net = setup()
    reels = _reel_setup(net)
    tries = []
    def flaky(rl):
        tries.append(1)
        raise RuntimeError("The read operation timed out")
    bot.REEL_POSTERS["Instagram"] = (flaky, bot.REEL_POSTERS["Instagram"][1])
    try:
        _reel_stories(net, at_et(2026, 11, 20, 16, 5))
        run_at(net, at_et(2026, 11, 20, 17, 1))
        run_at(net, at_et(2026, 11, 20, 17, 6))
        run_at(net, at_et(2026, 11, 20, 17, 11))
        assert len(tries) == 1, tries
        assert sorted(n for n, _ in reels) == ["Facebook", "YouTube"]
    finally:
        _reel_teardown()
    return "Instagram reel timed out (may be live): not uploaded again; Facebook + YouTube once each"


SCENARIOS = [v for k, v in sorted(globals().items()) if k.startswith("s") and k[1:3].isdigit()]

if __name__ == "__main__":
    fails = 0
    print(f"{'#':<4}{'scenario':<45}result")
    for fn in SCENARIOS:
        name = fn.__name__
        try:
            note = fn()
            print(f"PASS {name:<44}{note}")
        except Exception:
            fails += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len(SCENARIOS) - fails}/{len(SCENARIOS)} scenarios passed")
    sys.exit(1 if fails else 0)
