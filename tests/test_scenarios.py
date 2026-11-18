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
        items = "".join(f"<item><title>{t}</title><pubDate>{time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}</pubDate></item>" for t in titles)
        return f"<rss><channel>{items}</channel></rss>".encode()

    def quote(self, sym):
        q = self.quotes.get(sym)
        return (q[0], q[1], int(time.time())) if q else None

    def _platform(self, url):
        for key, name in [("graph.facebook.com/v24.0/IGU", "Instagram"), ("graph.facebook.com", "Facebook"),
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
        return {"id": "C1", "uri": "at://post", "result": {"message_id": 1}}

    def http_post_file(self, url, fields, ff, fn, data, headers=None):
        name = self._platform(url)
        if name == "Telegram":
            name = "Telegram" if fields.get("chat_id") == "@NewsB4Noise" else "X-alert"
        self._maybe_fail(name)
        assert data[:2] == b"\xff\xd8", "not a JPEG"
        self.calls.append((name, "upload-image", {"published": fields.get("published"), "text": fields.get("message", "")}))
        return {"id": "PHOTO", "post_id": "PAGE_POST", "result": {"message_id": 2}}

    def http_get_json(self, url, params):
        if params.get("fields") == "images":
            return {"images": [{"width": 1080, "source": "https://fbcdn.example/card.jpg"}]}
        return {"status": "FINISHED", "status_code": "FINISHED"}

    def http_post_bytes(self, url, data, headers):
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
    bot.config.POST_SPACING_SECONDS = 0
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
    assert len(fb_feed) == 1 and len(uploads) == 5, net.calls                # cover + 4 cards
    assert all(u[2]["published"] == "false" for u in uploads)
    assert sum(1 for k in fb_feed[0][2] if k.startswith("attached_media")) == 5
    cap = fb_feed[0][2]["text"]
    assert cap.startswith("🕐 Global markets this hour (") and "1. " in cap and "4. " in cap, cap
    ig = [c for c in net.calls if c[0] == "Instagram"]
    children = [c for c in ig if c[1] == "media" and c[2].get("is_carousel_item") == "true"]
    parent = [c for c in ig if c[1] == "media" and c[2].get("children")]
    assert len(children) == 5 and len(parent) == 1 and len(parent[0][2]["children"].split(",")) == 5, ig
    assert [c for c in ig if c[1] == "media_publish"], ig
    assert not net.posts("Threads"), "text platforms re-posted"
    run(net)
    assert not any(c[0] in ("Facebook", "Instagram") for c in net.calls), "digest posted twice"
    return "after the hour: ONE Facebook post + ONE Instagram carousel (cover + 4 cards), not repeated"


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
    lim = bot.config.MAX_POSTS_PER_DAY
    fake = [{"ts": time.time() - 60, "text": "x", "words": [], "item_ids": [], "story_id": f"s{i}", "platforms": []}
            for i in range(lim)]
    bot.POSTED_FILE.write_text(json.dumps(fake))
    put(net, NIKKEI); run(net)
    assert net.posts("Threads") == []
    return f"daily limit ({lim}) reached: nothing more posted"


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
    assert net.calls == [] and len(slides) == 3 and "digest not posted" in out, (out, slides)
    return "DRY_RUN: hourly carousel saved as preview slides (cover + 2 cards), nothing posted"


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
