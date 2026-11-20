"""Run: python3 tests/check_update15.py - silent Telegram, close movers, quiet/failure alarms."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "newsbot"))
import bot, config
import prices as pr
from datetime import datetime
from zoneinfo import ZoneInfo
ok = 0
def check(got, want, msg):
    global ok; assert got == want, (msg, got, want); ok += 1; print("PASS", msg, "->", got)
# --- silent Telegram
sent = []
bot.http_post = lambda url, params, **k: sent.append(params) or {"result": {"message_id": 1}}
bot.wants_card = lambda n: False
import os; os.environ["TELEGRAM_BOT_TOKEN"] = "t"; os.environ["TELEGRAM_CHANNEL_ID"] = "c"
bot.post_telegram_channel({"tagged": "🇺🇸 Fed Holds Rates", "story": {"priority": 3}})
check(sent[-1].get("disable_notification"), "true", "regular headline is silent")
bot.post_telegram_channel({"tagged": "🔴 BREAKING: Fed Cuts", "story": {"priority": 3, "breaking": True}})
check("disable_notification" in sent[-1], False, "BREAKING makes a sound")
bot.post_telegram_channel(bot.special_post("🔔 US Stocks Close\nS&P 500 ...", [], "market"))
check("disable_notification" in sent[-1], False, "market bell makes a sound")
bot.post_telegram_channel(bot.special_post("⏰ Coming Up At 8:30 AM: CPI", [], "calendar"))
check(sent[-1].get("disable_notification"), "true", "calendar heads-up is silent")
# --- top movers
now = time.time()
Q = {"NVDA": (106.1, 100), "AMD": (92, 100), "AAPL": (101, 100), "TSLA": (103, 100), "INTC": (97, 100), "MSFT": (99.5, 100),
     "RELIANCE.NS": (105, 100), "TCS.NS": (98, 100)}
pr.fetch_quote = lambda s: (Q[s][0], Q[s][1], now - 60) if s in Q else None
us = bot.close_movers("US", now); print(us)
check(us[0], "📈 Top gainers: NVDA +6.1%, TSLA +3.0%, AAPL +1.0%", "US gainers")
check(us[1], "📉 Top losers: AMD −8.0%, INTC −3.0%, MSFT −0.5%", "US losers")
check(bot.close_movers("IN", now), ["📈 Top gainers: RELIANCE +5.0%", "📉 Top losers: TCS −2.0%"], "India movers (.NS only)")
pr.fetch_quote = lambda s: (Q[s][0], Q[s][1], now - 5 * 3600) if s in Q else None
check(bot.close_movers("US", now), [], "stale prices -> no movers line")
def boom(s): raise RuntimeError("yahoo down")
pr.fetch_quote = boom
check(bot.close_movers("US", now), [], "price source down -> post still goes, no movers")
# --- alarms
ny = ZoneInfo("America/New_York")
wed_noon = datetime(2026, 11, 18, 12, 0, tzinfo=ny).timestamp()
sat_noon = datetime(2026, 11, 21, 12, 0, tzinfo=ny).timestamp()
night = datetime(2026, 11, 18, 21, 0, tzinfo=ny).timestamp()
bot.STATS.clear()
posted = [{"ts": wed_noon - 75 * 60}]
check([k for k, _ in bot.alarms_due(wed_noon, posted)], ["quiet"], "75 min silence at noon on a weekday -> alarm")
check(bot.alarms_due(wed_noon, [{"ts": wed_noon - 20 * 60}]), [], "posted 20 min ago -> no alarm")
check(bot.alarms_due(sat_noon, [{"ts": sat_noon - 5 * 3600}]), [], "weekend -> no quiet alarm")
check(bot.alarms_due(night, [{"ts": night - 5 * 3600}]), [], "US night (India closed too) -> no quiet alarm")
india_morning = datetime(2026, 11, 18, 0, 30, tzinfo=ny).timestamp()   # 11:00 IST
check([k for k, _ in bot.alarms_due(india_morning, [{"ts": india_morning - 2 * 3600}])], ["quiet"], "India session counts too")
bot.STATS["fails"] = [{"ts": wed_noon - i * 600, "platform": "Instagram", "error": "HTTP 403 request limit"} for i in range(3)]
check([k for k, _ in bot.alarms_due(wed_noon, [{"ts": wed_noon}])], ["fail:Instagram"], "3 Instagram errors in an hour -> alarm")
msgs = []
bot.send_private = lambda m: msgs.append(m)
bot.check_alarms(wed_noon, False, [{"ts": wed_noon}]); bot.check_alarms(wed_noon + 600, False, [{"ts": wed_noon}])
check(len(msgs), 1, "same alarm not repeated within 3 hours")
bot.check_alarms(wed_noon + 4 * 3600, False, [{"ts": wed_noon + 4 * 3600}])
bot.STATS["fails"] = []
check(len(msgs), 1, "old errors (>1h) don't re-alarm")
print(f"\nALL {ok} UPDATE-15 CHECKS PASSED")
