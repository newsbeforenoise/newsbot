"""Checks for the 30-minute roundups (Update 13). Run: python3 tests/check_update13.py"""
import sys, types, tempfile, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "newsbot"))
import bot, config
bot.images.render = lambda *a, **k: b"JPEG"; bot.images.available = lambda: True
d = Path(tempfile.mkdtemp()); bot.DIGEST_FILE = d / "digest.json"
bot.time.sleep = lambda s: None
config.DIGEST_TIMEZONE = "UTC"
config.DIGEST_PLATFORM_WINDOWS = {}   # these checks: every platform on 30 min (Instagram hourly: check_update13_2.py)
import os
for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN", "IG_USER_ID", "THREADS_ACCESS_TOKEN", "THREADS_USER_ID"):
    os.environ[k] = "x"
bot.digest_platforms = lambda: ["Facebook", "Instagram", "Threads"]
bot.STATS.clear()

# fake Meta APIs
calls = []; live = {"Facebook": [], "Instagram": [], "Threads": []}; n = [0]
def http_post(url, params=None, json_body=None, headers=None):
    n[0] += 1; params = params or {}
    plat = "Threads" if "threads.net" in url else ("Instagram" if "/x/media" in url or "media_publish" in url else "Facebook")
    calls.append((plat, url.rsplit("/", 1)[-1], dict(params)))
    if url.endswith("threads_publish") or url.endswith("media_publish"):
        cap = [c[2] for c in calls if c[0] == plat and c[2].get("media_type") in ("CAROUSEL", "IMAGE", "TEXT") or (c[0]==plat and c[2].get("caption"))][-1]
        live[plat].insert(0, cap.get("text") or cap.get("caption"))
    if url.endswith("/feed"):
        live["Facebook"].insert(0, params["message"])
    return {"id": f"c{n[0]}"}
def http_get_json(url, params):
    if params.get("fields") in ("caption,timestamp", "text,timestamp", "message,created_time"):
        plat = "Instagram" if "caption" in params["fields"] else ("Threads" if "text" in params["fields"] else "Facebook")
        key = {"Instagram": "caption", "Threads": "text", "Facebook": "message"}[plat]
        return {"data": [{key: t} for t in live[plat][:5]]}
    if params.get("fields") == "images":
        return {"images": [{"width": 1080, "source": "https://cdn/single.jpg"}]}
    return {"status": "FINISHED", "status_code": "FINISHED"}
def http_post_file(url, fields, file_field, filename, data, headers=None, content_type="image/jpeg"):
    n[0] += 1; calls.append(("Facebook", "photos", dict(fields)))
    if fields.get("published") == "true": live["Facebook"].insert(0, fields.get("message", ""))
    return {"id": f"ph{n[0]}", "post_id": f"pp{n[0]}"}
bot.http_post, bot.http_get_json, bot.http_post_file = http_post, http_get_json, http_post_file
def host(dg, need_ids=False):
    if not dg.get("urls"):
        dg["urls"] = [f"https://cdn/{i}.jpg" for i in range(len(dg["slides"]))]
        dg["photo_ids"] = [f"p{i}" for i in range(len(dg["slides"]))]
    return dg["urls"]
bot._host_slides = host

def item(h, ts, words=None, prio=3):
    return {"ts": ts, "headline": h, "credit": "Bloomberg", "plain": "🇺🇸 " + h + " – Bloomberg",
            "words": sorted(words or bot.key_words(h)), "tags": ["#USA", "#Markets"],
            "priority": prio, "focus": True, "story": {"priority": prio, "countries": ["US"], "followup": False, "is_price": False}}
W = 1800; t0 = 1795000000 - (1795000000 % W)
ok = 0
def check(c, m):
    global ok; assert c, m; ok += 1; print("PASS", m)

check(bot.hour_key(t0 + 60) != bot.hour_key(t0 + W + 60) and bot.hour_key(t0 + 60) == bot.hour_key(t0 + W - 60),
      "windows are 30 minutes")
heads = [f"Company {chr(65+i)}{chr(65+i)} Reports Record Quarter Number {i}" for i in range(18)]
bot.run_digest(t0 + 300, False, [item(h, t0 + 300 + i) for i, h in enumerate(heads)])
check(not calls, "nothing posts during the window (no on-the-spot posts)")
bot.run_digest(t0 + W + 120, False, [])
fb = [c for c in calls if c[0] == "Facebook" and c[1] == "feed"][0][2]
fb_slides = len([k for k in fb if k.startswith("attached_media")])
ig_children = [c for c in calls if c[0] == "Instagram" and c[2].get("is_carousel_item")]
th_children = [c for c in calls if c[0] == "Threads" and c[2].get("is_carousel_item")]
th_post = [c for c in calls if c[0] == "Threads" and c[2].get("media_type") == "CAROUSEL"][0][2]
print(f"   FB slides {fb_slides} | IG slides {len(ig_children)} | Threads slides {len(th_children)} | Threads text {len(th_post['text'])} chars")
check(fb_slides == 15, "Facebook: 15 slides per 30 min (= 30 an hour)")
check(len(ig_children) == 10, "Instagram: 10 slides (API max), all headlines in caption")
check("15." in [c for c in calls if c[0]=="Instagram" and c[2].get("media_type")=="CAROUSEL"][0][2]["caption"], "Instagram caption lists all 15")
check(len(th_children) == 15 and len(th_post["text"]) <= 500, "Threads: carousel of 15 cards, text under 500 chars")
check("last 30 min" in th_post["text"] and th_post.get("topic_tag"), "Threads text has 30-min header + topic tag")
check(all(len(v) == 1 for v in live.values()), "one post per platform")
before = len(calls)
for k in range(1, 5): bot.run_digest(t0 + W + 120 + k * 300, False, [])
check(len(calls) == before, "later runs in the window: no repeats")

# reworded repeat of an already-posted story is dropped
calls.clear()
rew = "Company AA Reports Record Quarter Number 0 Results"
bot.run_digest(t0 + W + 900, False, [item(rew, t0 + W + 900), item("Oil Prices Jump After OPEC Cut", t0 + W + 950)])
bot.run_digest(t0 + 2 * W + 120, False, [])
posted_text = live["Facebook"][0]
check("Oil Prices Jump" in posted_text and "Company AA" not in posted_text, "reworded repeat dropped, new story posted")
# two versions of the same new story in one window -> one
calls.clear()
bot.run_digest(t0 + 2*W + 600, False, [item("Barnier Warns UK Against Cherry Picking EU Rejoin", t0 + 2*W + 600),
                                        item("Barnier Warns UK On Cherry Picking If It Rejoins EU", t0 + 2*W + 650)])
bot.run_digest(t0 + 3 * W + 120, False, [])
check(live["Facebook"][0].count("Barnier") == 1, "two versions of one story in a window: posted once")
# a window with only repeats posts nothing
calls.clear()
bot.run_digest(t0 + 3*W + 600, False, [item("Barnier Warns UK Against Cherry Picking EU Rejoin", t0 + 3*W + 600)])
bot.run_digest(t0 + 4 * W + 120, False, [])
check(not calls, "window with only repeats: nothing posted anywhere")
# Threads blocked -> rests, others post
calls.clear(); bot.STATS["fails"] = [{"ts": t0 + 4*W, "platform": "Threads", "error": "HTTP 400 2207051 restricted"}]
bot.run_digest(t0 + 4*W + 600, False, [item("Fed Chair Signals December Pause", t0 + 4*W + 600)])
bot.run_digest(t0 + 5 * W + 120, False, [])
check(not [c for c in calls if c[0] == "Threads"] and [c for c in calls if c[0] == "Facebook"], "Threads blocked: it rests, FB/IG still post")
# per-story Threads posting is off (roundup only)
check(not bot.platform_wants("Threads", {"priority": 3}, [], t0), "Threads no longer posts each headline on the spot")
check(bot.platform_wants("Telegram", {"priority": 3}, [], t0), "Telegram still instant")
# single-headline window -> Threads single image
calls.clear(); bot.STATS["fails"] = []
bot.run_digest(t0 + 7*W + 600, False, [item("Gold Hits Record High Above 4000", t0 + 7*W + 600)])
bot.run_digest(t0 + 8 * W + 120, False, [])
th = [c for c in calls if c[0] == "Threads" and c[2].get("media_type")]
check(th and th[-1][2]["media_type"] == "IMAGE", "1 headline: Threads posts a single card")
print(f"\nALL {ok} ROUNDUP CHECKS PASSED")
