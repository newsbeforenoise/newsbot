"""Run: python3 tests/check_update13_2.py - Instagram hourly while Facebook/Threads post every 30 min (Update 13.2)."""
from pathlib import Path as _P
src = open(_P(__file__).with_name("check_update13.py"), encoding="utf-8").read().split("W = 1800")[0]
src = src.replace("config.DIGEST_PLATFORM_WINDOWS = {}", "config.DIGEST_PLATFORM_WINDOWS = {'Instagram': 60}")
exec(src)
H = 3600; t0 = 1795000000 - (1795000000 % H)          # 11:00 UTC
ok = 0
def check(c, m):
    global ok; assert c, m; ok += 1; print("PASS", m)
def posts(p): return len(live[p])
# 11:00-11:30 headlines -> at 11:30 FB + Threads post, Instagram waits
bot.run_digest(t0 + 300, False, [item(h, t0 + 300 + i) for i, h in enumerate(['Fed Holds Rates Steady', 'Nvidia Beats Earnings Estimates', 'Oil Jumps On OPEC Cut', 'Yen Weakens Past 160', 'Gold Hits Record High', 'Tesla Recalls Model Y'])])
bot.run_digest(t0 + 1800 + 60, False, [])
check(posts("Facebook") == 1 and posts("Threads") == 1 and posts("Instagram") == 0, "11:30: FB + Threads post, Instagram holds")
# 11:30-12:00 headlines -> at 12:00 FB + Threads post the new ones; Instagram posts the whole hour
bot.run_digest(t0 + 1800 + 300, False, [item(h, t0 + 2100 + i) for i, h in enumerate(['ECB Signals December Hike', 'Alibaba Profit Triples', 'Bitcoin Falls Below 60000', 'Sensex Closes At Record', 'Boeing Wins Saudi Order', 'Apple Delays AI Launch'])])
bot.run_digest(t0 + H + 60, False, [])
ig = live["Instagram"][0]
check(posts("Facebook") == 2 and posts("Threads") == 2 and posts("Instagram") == 1, "12:00: FB + Threads post again, Instagram posts once")
check("this hour (11:00–12:00 UTC)" in ig, "Instagram caption covers the full hour")
check(all(h in ig for h in ['Fed Holds Rates Steady', 'Nvidia Beats Earnings Estimates', 'Oil Jumps On OPEC Cut', 'Yen Weakens Past 160', 'Gold Hits Record High', 'Tesla Recalls Model Y', 'ECB Signals December Hike', 'Alibaba Profit Triples', 'Bitcoin Falls Below 60000', 'Sensex Closes At Record', 'Boeing Wins Saudi Order', 'Apple Delays AI Launch']),
      "Instagram lists all 12 headlines from both halves")
check("ECB Signals" in live["Facebook"][0] and "Fed Holds" not in live["Facebook"][0], "Facebook's 12:00 post has only the new half hour")
ig_children = [c for c in calls if c[0] == "Instagram" and c[2].get("is_carousel_item")]
check(len(ig_children) == 10, "Instagram carousel = 10 slides (API max)")
before = dict((p, posts(p)) for p in live)
for k in range(1, 5): bot.run_digest(t0 + H + 60 + k * 300, False, [])
check(all(posts(p) == before[p] for p in live), "no repeats on later runs")
# quiet second half: Instagram still posts its held first half at the hour
bot.run_digest(t0 + H + 400, False, [item("Only Story In The First Half Hour", t0 + H + 400)])
bot.run_digest(t0 + H + 1800 + 60, False, [])          # 12:30
bot.run_digest(t0 + 2 * H + 60, False, [])             # 13:00, no new headlines in 12:30-13:00
check(posts("Instagram") == 2 and "Only Story In The First Half Hour" in live["Instagram"][0],
      "quiet half hour: Instagram still posts the held headlines at the hour")
check(posts("Facebook") == before["Facebook"] + 1, "Facebook posted only when it had something new")
# nothing at all for an hour -> Instagram posts nothing
n_ig = posts("Instagram")
bot.run_digest(t0 + 2 * H + 1800 + 60, False, []); bot.run_digest(t0 + 3 * H + 60, False, [])
check(posts("Instagram") == n_ig, "empty hour: Instagram posts nothing")
print(f"\nALL {ok} INSTAGRAM-HOURLY CHECKS PASSED")
