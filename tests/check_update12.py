"""Checks for the Update 12 fixes. Run: python3 tests/check_update12.py (kept out of pytest: it patches bot)."""
import sys, types, json, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent / "newsbot"
sys.path.insert(0, str(HERE))
import bot, config
bot.images.render = lambda *a, **k: b"JPEG"; bot.images.render_cover = lambda *a, **k: b"COVER"

d = Path(tempfile.mkdtemp()); bot.DIGEST_FILE = d / "digest.json"
bot.time.sleep = lambda s: None
bot.digest_platforms = lambda: ["Facebook", "Instagram"]
config.DIGEST_TIMEZONE = "UTC"
config.MARKET_TAG = getattr(config, "MARKET_TAG", "#Markets")

live = {"Facebook": [], "Instagram": []}   # fake accounts
calls = {"Facebook": 0, "Instagram": 0}
behaviour = {"Instagram": "ok", "Facebook": "ok"}
def poster(name):
    def f(dg):
        calls[name] += 1
        b = behaviour[name]
        if b == "publish_then_ratelimit":     # Instagram publishes but the API answers with an error
            live[name].insert(0, dg["caption"])
            raise RuntimeError('HTTP 403: {"error":{"message":"Application request limit reached","code":4,"error_subcode":2207051}}')
        if b == "down":
            raise RuntimeError("HTTP 500: server error")
        live[name].insert(0, dg["caption"]); return "id1"
    return f
bot.DIGEST_POSTERS = {n: poster(n) for n in live}
bot.recent_captions = lambda name: [bot._first_line(c) for c in live[name][:5]]

def item(h, ts): return {"ts": ts, "headline": h, "credit": "Bloomberg", "plain": h + " – Bloomberg",
                         "tags": ["#USA"], "priority": 3, "focus": True,
                         "story": {"priority": 3, "countries": ["US"], "followup": False, "is_price": False}}
H = 3600; t0 = 1795000000 - (1795000000 % H)   # start of an hour
def reset():
    for n in live: live[n].clear(); calls[n] = 0; behaviour[n] = "ok"
    bot.STATS.clear(); bot.DIGEST_FILE.unlink(missing_ok=True)
ok = 0
def check(cond, msg):
    global ok; assert cond, msg; ok += 1; print("PASS", msg)

# 1. normal hour posts once on each platform
reset(); bot.run_digest(t0 + 600, False, [item("Fed Holds Rates", t0 + 600)])
bot.run_digest(t0 + H + 60, False, [])
check(len(live["Facebook"]) == 1 and len(live["Instagram"]) == 1, "normal hour: one carousel per platform")
bot.run_digest(t0 + H + 360, False, []); bot.run_digest(t0 + H + 660, False, [])
check(len(live["Instagram"]) == 1, "later runs in the same hour post nothing more")

# 2. no new headlines -> nothing posted
reset(); bot.run_digest(t0 + 600, False, [item("Fed Holds Rates", t0 + 600)]); bot.run_digest(t0 + H + 60, False, [])
bot.run_digest(t0 + H + 600, False, [item("Fed Holds Rates", t0 + H + 600)])     # same headline again
bot.run_digest(t0 + 2 * H + 60, False, [])
check(len(live["Instagram"]) == 1 and len(live["Facebook"]) == 1, "repeat headline only: next hour posts nothing")
bot.run_digest(t0 + 2 * H + 600, False, [item("Fed Holds Rates", t0 + 2*H + 600), item("Oil Jumps 5%", t0 + 2*H + 700)])
bot.run_digest(t0 + 3 * H + 60, False, [])
check(len(live["Instagram"]) == 2 and "Oil Jumps" in live["Instagram"][0] and "Fed Holds" not in live["Instagram"][0],
      "mixed hour: only the new headline goes out")

# 3. Instagram publishes but returns rate-limit error -> no duplicate, no retry
reset(); behaviour["Instagram"] = "publish_then_ratelimit"
bot.run_digest(t0 + 600, False, [item("Citi Sees Romanian Carry Appeal", t0 + 600)])
for k in range(4): bot.run_digest(t0 + H + 60 + k * 300, False, [])
check(len(live["Instagram"]) == 1 and calls["Instagram"] == 1, "rate-limit error: posted once, never retried (today's duplicate bug)")
check(len(live["Facebook"]) == 1, "Facebook unaffected")
# next hour: still in cooldown -> Instagram skipped, Facebook posts
behaviour["Instagram"] = "ok"
bot.run_digest(t0 + H + 900, False, [item("Alibaba Profit Triples", t0 + H + 900)])
bot.run_digest(t0 + 2 * H + 60, False, [])
check(calls["Instagram"] == 1 and len(live["Facebook"]) == 2, "within 2h cooldown: Instagram rests, Facebook keeps posting")
bot.run_digest(t0 + 3 * H + 900, False, [item("Nvidia Beats Estimates", t0 + 3*H + 900)])
bot.run_digest(t0 + 4 * H + 60, False, [])
check(calls["Instagram"] == 2 and len(live["Instagram"]) == 2, "after cooldown: Instagram posts again")

# 4. a server error that actually published -> retry sees it is live and does not repost
reset()
def sneaky(dg):
    calls["Instagram"] += 1; live["Instagram"].insert(0, dg["caption"]); raise RuntimeError("HTTP 500: timeout")
bot.DIGEST_POSTERS["Instagram"] = sneaky
bot.run_digest(t0 + 600, False, [item("Gold Hits Record", t0 + 600)])
bot.run_digest(t0 + H + 60, False, []); bot.run_digest(t0 + H + 360, False, [])
check(len(live["Instagram"]) == 1 and calls["Instagram"] == 1, "error but actually live: retry detects it, no duplicate")
bot.DIGEST_POSTERS["Instagram"] = poster("Instagram")

# 5. platform genuinely down -> limited retries, then gives up
reset(); behaviour["Instagram"] = "down"
bot.run_digest(t0 + 600, False, [item("ECB Hikes", t0 + 600)])
for k in range(5): bot.run_digest(t0 + H + 60 + k * 300, False, [])
check(calls["Instagram"] == config.DIGEST_MAX_ATTEMPTS, f"real outage: {config.DIGEST_MAX_ATTEMPTS} attempts max")

# 6. rate-limit detector
check(bot.is_rate_limit('HTTP 403: {"error":{"message":"Application request limit reached","code":4,'), "detects code 4")
check(not bot.is_rate_limit("HTTP 500: server error"), "ordinary error is not a rate limit")

# 7. unlimited daily cap
check(config.MAX_POSTS_PER_DAY == 0 and (config.MAX_POSTS_PER_DAY or 10**9) - 200 > 1000, "Telegram: no daily cap")
print(f"\nALL {ok} CHECKS PASSED")
