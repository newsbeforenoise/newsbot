"""Run: python3 tests/check_update14.py - flags, deal tags, reworded repeats, promo line, weekly report."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "newsbot"))
import bot, config
bot.images.render = lambda *a, **k: b"J"
bot.prices.fetch_quote = lambda s: None
ok = 0
def check(got, want, msg):
    global ok; assert got == want, (msg, got, want); ok += 1; print("PASS", msg, "->", got)
D = bot.detect_countries
check(D("Citi Sees Romanian Carry Appeal With Budget Key For Bond Rally"), ["RO"], "Citi view on Romania -> 🇷🇴 only")
check(D("Goldman Says Fed Will Cut In December"), ["US"], "Goldman view on the Fed -> still US (via Fed)")
check(D("JPMorgan, Visa, Mastercard Say Third-Party Vendors Targeted In Cyberattack"), ["US"], "company news (not a view) keeps 🇺🇸")
check(D("Citi Sees Gold At $4,000"), ["US"], "no other country named -> firm's flag kept")
check(D("Nvidia Shares Fall As China Curbs Imports"), ["US", "CN"], "Nvidia + China unchanged")
check(D("Denmark Buckles Under Trump, Approves US Military Expansion Deal In Greenland")[:3], ["DK", "US", "GL"], "Greenland gets 🇬🇱")
check(bot.flags_for(D("Senegal Parliament Rejects 2027 Budget In Setback For IMF Deal")), "🇸🇳", "Senegal now flagged")
M = lambda t: bot.on_topic(t, config.MARKET_KEYWORDS)
check(M("Advent Is Said In Talks To Buy Business Services Firm Boardroom"), True, "buyout story = markets (not #Geopolitics)")
check(M("Tod's Nears €400 Million Debt Refinance Backed By Group's Owners"), True, "refinance = markets")
check(M("Xi Tells Trump To 'Do Right Thing' On Taiwan"), False, "politics stays politics")
K, S = bot.key_words, bot.same_topic
check(S(K("Trump's Greenland Deal To Take Effect After Bitter Standoff"),
        K("Denmark Buckles Under Trump, Approves US Military Expansion Deal In Greenland")), True, "Greenland pair = same story")
check(S(K("Nvidia Beats Earnings Estimates"), K("Nvidia CEO Says AI Demand Is Insane")), False, "different Nvidia stories stay separate")
check(S(K("Bitcoin Bounces Back Into Green Ahead Of Anthropic IPO"), K("Anthropic Investor Says IPO Sets New Benchmark For AI")), False, "two different Anthropic IPO stories stay separate")
check(S(K("Trump Cites Military Aid, Nuclear Power In Manila Meeting With Marcos"), K("3 Nuclear Powers At One Table: Historic Xi-Trump-Putin Meeting In China")), False, "two different Trump meetings stay separate")
check(S(K("Trump Meets Xi At APEC"), K("Trump Signs Tax Bill")), False, "sharing only a leader's name isn't enough")
check(S(K("Fed Holds Rates Steady"), K("Oil Jumps On OPEC Cut")), False, "unrelated")
# promo line
dg = bot.build_digest([{"ts": 1795000000, "headline": h, "credit": "B", "plain": "🇺🇸 " + h, "tags": ["#USA"], "priority": 3,
                        "focus": True, "story": {}} for h in ("Fed Holds Rates", "Oil Jumps On OPEC Cut")])
check(dg["caption"].split("\n")[1], "⚡ Live alerts first on Telegram: t.me/NewsB4Noise", "promo is line 2 of FB/IG caption")
check(bot._first_line(dg["caption"]), bot._first_line(dg["head"]), "duplicate check still keys on line 1")
check("t.me" in bot.threads_caption(dg), False, "no link on Threads")
check(config.DIGEST_MAX_SLIDES, 10, "Facebook roundups 10 slides")
# weekly report
bot.STATS.clear()
bot.STATS["history"] = {f"2026-11-{d:02d}": {"followers": {"Telegram": 3 + (d - 13), "Facebook": 2, "Instagram": 7},
                                             "posts": {"Telegram": 200, "Facebook": 40}, "fails": ({"Instagram": 2} if d == 19 else {})}
                        for d in range(13, 20)}
w = bot.weekly_report("2026-11-19"); print(w)
check("Telegram 9 (+6)" in w and "Telegram 1,400" in w and "Instagram 2" in w and "Growing: Telegram" in w, True, "weekly numbers")
print(f"\nALL {ok} UPDATE-14 CHECKS PASSED")
