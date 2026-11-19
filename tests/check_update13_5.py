"""Run: python3 tests/check_update13_5.py - live stock move in headlines (update 13.5)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "newsbot"))
import bot, config, prices
now = time.time()
quotes = {"AMD": (230.0, 250.0, now - 60), "NVDA": (180.9, 180.0, now - 60), "RELIANCE.NS": (1300, 1250, now - 60),
          "AAPL": (200.0, 190.0, now - 3 * 3600)}
prices.fetch_quote = lambda s: quotes.get(s)
ok = 0
def check(got, want, msg):
    global ok; assert got == want, (msg, got, want); ok += 1; print("PASS", msg, "->", repr(got))
bot._QUOTE_CACHE.clear()
check(bot.stock_move_text("AMD Falls Amid Short Report From Hunterbrook"), " ($AMD −8.0%)", "AMD -8% shown")
check(bot.stock_move_text("Nvidia Edges Higher"), "", "move under 1% hidden")
check(bot.stock_move_text("Reliance Jumps On Jio Listing"), " ($RELIANCE +4.0%)", "Indian stock, .NS suffix dropped")
check(bot.stock_move_text("Apple Unveils New iPhone"), "", "stale price (market closed) never shown")
check(bot.stock_move_text("Mexican Peso Hits Low As Fed Outlook Rattles"), "", "no company, no lookup")
check(bot.stock_move_text("Metaverse Hype Fades"), "", "whole words only (Meta != Metaverse)")
check(bot.stock_move_text("AMD And Reliance Lead Movers"), " ($AMD −8.0%, $RELIANCE +4.0%)", "two tickers")
p = bot.build_posts({"text": "AMD Falls Amid Short Report From Hunterbrook", "flags": "🇺🇸", "credit": ["Seeking Alpha"],
                     "tags": ["#AMD", "#Markets"], "priority": 3})
check(p["plain"], "🇺🇸 AMD Falls Amid Short Report From Hunterbrook ($AMD −8.0%) – Seeking Alpha", "full post text")
check(p["headline"], "AMD Falls Amid Short Report From Hunterbrook", "card + duplicate key unchanged")
print(f"\nALL {ok} STOCK-MOVE CHECKS PASSED")
