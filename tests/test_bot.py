import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "newsbot"))
import bot  # noqa: E402

NOW = time.time()

def feed(name, owner):
    return {"name": name, "owner": owner}

def add(items, name, owner, title, age_min=10, official=False):
    f = feed(name, owner)
    if official:
        f["official"] = True
    bot.collect(items, f, [{"title": title, "published": NOW - age_min * 60}], NOW)

def run(items, posted=None):
    return bot.find_stories(items, posted or [], NOW)

def test_three_independent_sources_posts():
    it = {}
    add(it, "CNBC", "cnbc", "Nvidia CEO Jensen Huang resigns - CNBC")
    add(it, "BBC", "bbc", "Jensen Huang resigns as Nvidia chief executive")
    add(it, "ET", "timesgroup", "Nvidia's Jensen Huang resigns as CEO")
    s = run(it)
    assert len(s) == 1, s
    assert "Huang" in s[0]["text"] and "CNBC" not in s[0]["text"]
    assert len(s[0]["sources"]) == 3

def test_two_independent_sources_enough_when_min_is_2():
    old = bot.config.MIN_SOURCES
    bot.config.MIN_SOURCES = 2
    try:
        it = {}
        add(it, "Seeking Alpha", "seekingalpha", "Palo Alto Networks to buy Applied Compute for $4.5B")
        add(it, "Investing.com", "investing", "Palo Alto to buy Applied Compute for $4.5 billion, Q1 beats")
        assert len(run(it)) == 1
        it = {}
        add(it, "BBC World", "bbc", "Palo Alto Networks to buy Applied Compute for $4.5B")
        add(it, "BBC Business", "bbc", "Palo Alto to buy Applied Compute for $4.5 billion")
        assert run(it) == [], "same company twice is not 2 sources"
    finally:
        bot.config.MIN_SOURCES = old

def test_same_owner_counts_once():
    old = bot.config.MIN_SOURCES
    bot.config.MIN_SOURCES = 3
    try:
        _same_owner_counts_once()
    finally:
        bot.config.MIN_SOURCES = old

def _same_owner_counts_once():
    it = {}
    add(it, "BBC World", "bbc", "Nvidia CEO Jensen Huang resigns")
    add(it, "BBC Biz", "bbc", "Jensen Huang resigns as Nvidia CEO")
    add(it, "ET", "timesgroup", "Nvidia's Jensen Huang resigns as CEO")
    add(it, "TOI", "timesgroup", "Jensen Huang resigns from Nvidia CEO post")
    assert run(it) == []

def test_rumour_does_not_count():
    it = {}
    add(it, "CNBC", "cnbc", "Nvidia CEO Jensen Huang resigns")
    add(it, "BBC", "bbc", "Jensen Huang reportedly resigns as Nvidia CEO")
    add(it, "ET", "timesgroup", "Jensen Huang could resign as Nvidia CEO, sources say")
    assert run(it) == []

def test_different_stories_not_merged():
    it = {}
    add(it, "CNBC", "cnbc", "Nvidia shares rise 5% on earnings beat")
    add(it, "BBC", "bbc", "Nvidia shares fall after China export ban")
    add(it, "ET", "timesgroup", "Nvidia shares slip as Fed holds rates")
    assert run(it) == []

def test_two_countries_is_geo_tier():
    it = {}
    three(it, "Japan and US sign new semiconductor pact",
              "US, Japan sign semiconductor pact in Tokyo",
              "Japan US semiconductor pact signed")
    s = run(it)
    assert len(s) == 1 and s[0]["priority"] == 2 and s[0]["flags"] == "🇯🇵🇺🇸", s
    assert "#Japan" in s[0]["tags"] and "#Geopolitics" in s[0]["tags"], s

def test_general_news_off_by_default():
    it = {}
    three(it, "Hurricane Milo makes landfall in Florida",
              "Florida hit as Hurricane Milo makes landfall in US",
              "Hurricane Milo makes landfall, US Florida coast battered")
    assert run(it) == []
    bot.config.INCLUDE_GENERAL_NEWS = True
    try:
        assert [x["priority"] for x in run(it)] == [1]
    finally:
        bot.config.INCLUDE_GENERAL_NEWS = False

def test_off_topic_skipped():
    it = {}
    add(it, "CNBC", "cnbc", "Taylor Swift announces new album tour dates")
    add(it, "BBC", "bbc", "Taylor Swift announces album tour dates for summer")
    add(it, "ET", "timesgroup", "Taylor Swift announces new album and tour dates")
    assert run(it) == []

def test_old_news_skipped():
    it = {}
    for n, o in [("A", "a"), ("B", "b"), ("C", "c")]:
        add(it, n, o, "RBI cuts repo rate by 25 basis points to 5.25%", age_min=600)
    assert run(it) == []

def test_already_posted_not_repeated():
    it = {}
    add(it, "A", "a", "RBI cuts repo rate by 25 basis points")
    add(it, "B", "b", "RBI cuts repo rate by 25 bps to 5.25%")
    add(it, "C", "c", "Reserve Bank RBI cuts repo rate 25 basis points")
    first = run(it)
    assert len(first) == 1
    posted = [{"ts": NOW, "text": first[0]["text"], "words": first[0]["words"]}]
    add(it, "D", "d", "RBI cuts repo rate by 25 basis points, Sensex jumps")
    assert run(it, posted) == []

def three(it, a, b, c):
    add(it, "A", "a", a); add(it, "B", "b", b); add(it, "C", "c", c)

def test_flags_in_headline_order():
    it = {}
    three(it, "US imposes new sanctions on Iran oil exports",
              "U.S. imposes sanctions on Iran oil exports",
              "Washington imposes fresh sanctions on Iran oil exports")
    s = run(it)
    assert len(s) == 1 and s[0]["flags"] == "🇺🇸🇮🇷" and s[0]["priority"] == 3, s

def test_geo_story_flags():
    it = {}
    three(it, "Pakistan accuses India of ceasefire violation",
              "India rejects Pakistan ceasefire violation claim",
              "Pakistan accuses India of LoC ceasefire violation")
    s = run(it)
    assert len(s) == 1 and s[0]["flags"] == "🇵🇰🇮🇳" and s[0]["priority"] == 2, s

def test_both_flags():
    it = {}
    three(it, "Modi and Trump agree on India US trade deal",
              "Trump, Modi agree trade deal framework",
              "India, US trade deal agreed by Modi and Trump")
    s = run(it)
    assert len(s) == 1 and s[0]["flags"] == "🇺🇸🇮🇳", s

def test_max_two_flags():
    it = {}
    three(it, "China blames US for Taiwan Strait tensions",
              "Beijing blames Washington for Taiwan Strait tensions",
              "China blames America over Taiwan Strait tensions")
    s = run(it)
    assert len(s) == 1 and s[0]["flags"] == "🇨🇳🇺🇸", s

def test_word_us_is_not_usa():
    it = {}
    three(it, "Germany tells us election will be held in March",
              "Germany election will be held in March, tells us chancellor",
              "Germany election to be held in March chancellor tells us")
    s = run(it)
    assert len(s) == 1 and s[0]["flags"] == "🇩🇪", s

def test_global_story_posted_unless_focus_required():
    it = {}
    three(it, "Malaysia's ringgit falls to 4.085 against the dollar",
              "Malaysian ringgit falls to 4.085 per dollar",
              "Ringgit falls to 4.085 against greenback, Malaysia")
    s = run(it)
    assert len(s) == 1 and s[0]["flags"].startswith("🇲🇾") and s[0]["priority"] == 3, s
    bot.config.REQUIRE_FOCUS_COUNTRY = True
    try:
        assert all(x["focus"] for x in run(it))
    finally:
        bot.config.REQUIRE_FOCUS_COUNTRY = False

def test_markets_first_then_focus_countries():
    it = {}
    three(it, "Russia and Ukraine agree ceasefire talks in Istanbul",
              "Russia, Ukraine agree to ceasefire talks in Istanbul",
              "Ceasefire talks in Istanbul agreed by Russia and Ukraine")
    add(it, "D", "d", "DAX falls 2% as German factory orders slump", 20)
    add(it, "E", "e", "German factory orders slump, DAX falls 2%", 20)
    add(it, "F", "f", "DAX falls 2% after German factory orders slump", 20)
    add(it, "G", "g", "Sensex falls 2% as foreign investors sell", 20)
    add(it, "H", "h", "Sensex falls 2% on foreign investor selling", 20)
    add(it, "I", "i", "Foreign investors sell, Sensex falls 2%", 20)
    s = run(it)
    assert [x["priority"] for x in s] == [3, 3, 2], s
    assert "Sensex" in s[0]["text"] and "DAX" in s[1]["text"], s



def test_hashtags_geo():
    it = {}
    three(it, "US imposes new sanctions on Iran oil exports",
              "U.S. imposes sanctions on Iran oil exports",
              "Washington imposes fresh sanctions on Iran oil exports")
    p = bot.build_posts(run(it)[0])
    assert p["tagged"].startswith("🇺🇸🇮🇷 ") and "#Sanctions" in p["tagged"], p
    assert p["tagged"].count("#") == 3, p["tagged"]
    assert "#" not in p["plain"] and p["topic"] == "Sanctions", p

def test_hashtags_market_india():
    it = {}
    three(it, "Sensex crashes 1,200 points as RBI hikes repo rate",
              "RBI hikes repo rate; Sensex crashes 1,200 points",
              "Sensex crashes over 1,200 points after RBI repo rate hike")
    s = run(it)[0]
    p = bot.build_posts(s)
    assert p["tagged"].startswith("🇮🇳 ") and "#RBI" in p["tagged"] and "#Sensex" in s["tags"], (p, s["tags"])
    assert p["topic"] == "RBI"

def test_trending_tag_added():
    it = {}
    three(it, "Nvidia stock plunges after US chip export ban on China",
              "US chip export ban on China sends Nvidia stock down",
              "Nvidia stock falls on US China chip export ban")
    s = bot.find_stories(it, [], NOW, ["nvidia stock", "taylor swift"])[0]
    assert "#NvidiaStock" in s["tags"][:2], s["tags"]
    assert "#TaylorSwift" not in s["tags"]

def test_x_post_fits_280():
    s = {"flags": "🇺🇸", "text": "A" * 270, "tags": ["#Tariffs", "#China", "#USA"]}
    x = bot.build_posts(s)["tagged"]
    assert len(x) <= 280, len(x)

def test_bluesky_facets_byte_offsets():
    text = "🇺🇸 US sanctions Iran\n\n#Sanctions #Iran"
    f = bot.bluesky_facets(text)
    b = text.encode()
    assert [b[x["index"]["byteStart"]:x["index"]["byteEnd"]].decode() for x in f] == ["#Sanctions", "#Iran"]
    assert f[0]["features"][0]["tag"] == "Sanctions"

def test_platforms_enabled_by_secrets():
    import os
    for k in ["THREADS_ACCESS_TOKEN","BLUESKY_HANDLE","BLUESKY_APP_PASSWORD","TELEGRAM_BOT_TOKEN",
              "TELEGRAM_CHANNEL_ID","MASTODON_INSTANCE","MASTODON_TOKEN","DISCORD_WEBHOOK_URL"]:
        os.environ.pop(k, None)
    os.environ["BLUESKY_HANDLE"] = "x.bsky.social"; os.environ["BLUESKY_APP_PASSWORD"] = "p"
    os.environ["TELEGRAM_BOT_TOKEN"] = "t"
    assert bot.enabled_platforms() == ["Bluesky"]
    os.environ["TELEGRAM_CHANNEL_ID"] = "@PeagleWire"
    assert bot.enabled_platforms() == ["Bluesky", "Telegram"]

def test_title_case():
    assert bot.title_case("bitcoin extends losses as price falls to three-month lows near $68,847") == \
        "Bitcoin Extends Losses As Price Falls To Three-Month Lows Near $68,847"
    assert bot.title_case("RBI keeps US iPhone imports 'under review'") == "RBI Keeps US iPhone Imports 'Under Review'"

def test_source_credit_in_post():
    it = {}
    add(it, "CNBC", "cnbc", "Nvidia CEO Jensen Huang resigns", 30)
    add(it, "BBC World", "bbc", "Jensen Huang resigns as Nvidia chief executive", 20)
    add(it, "Economic Times", "timesgroup", "Nvidia's Jensen Huang resigns as CEO", 10)
    p = bot.build_posts(run(it)[0])
    assert p["plain"].startswith("🇺🇸 Nvidia CEO Jensen Huang Resigns – "), p["plain"]
    assert p["plain"].endswith("– CNBC"), p["plain"]          # outlet whose headline we used
    bot.config.MAX_SOURCES_SHOWN = 3
    try:
        assert bot.build_posts(run(it)[0])["plain"].endswith("– CNBC, BBC, ET")
    finally:
        bot.config.MAX_SOURCES_SHOWN = 1
    assert len(p["tagged"]) <= 280

def _post(story, ts=None):
    return {"ts": ts or NOW, "text": story["text"], "words": story["words"],
            "item_ids": story["item_ids"], "story_id": story["story_id"]}

def test_followup_posted_with_update_label():
    it = {}
    three(it, "Microsoft outage hits Teams and Outlook users worldwide",
              "Global Microsoft outage hits Outlook and Teams users",
              "Microsoft Teams, Outlook outage hits users worldwide")
    first = run(it)
    assert len(first) == 1 and not first[0]["followup"]
    posted = [_post(first[0], NOW - 1800)]
    add(it, "D", "d", "Microsoft restores Teams and Outlook after outage")
    add(it, "E", "e", "Microsoft says Outlook, Teams restored after global outage")
    add(it, "F", "f", "Microsoft restores Outlook and Teams services after outage")
    s = run(it, posted)
    assert len(s) == 1 and s[0]["followup"] and s[0]["story_id"] == first[0]["story_id"], s
    assert "Restore" in bot.build_posts(s[0])["plain"]
    bot.config.FOLLOWUP_PREFIX = "UPDATE: "
    try:
        assert "UPDATE: " in bot.build_posts(s[0])["plain"]
    finally:
        bot.config.FOLLOWUP_PREFIX = ""

def test_late_duplicates_are_not_followups():
    it = {}
    three(it, "Microsoft outage hits Teams and Outlook users worldwide",
              "Global Microsoft outage hits Outlook and Teams users",
              "Microsoft Teams, Outlook outage hits users worldwide")
    first = run(it)
    posted = [_post(first[0], NOW - 1800)]
    add(it, "D", "d", "Microsoft Teams and Outlook outage hits users around the world")
    add(it, "E", "e", "Users worldwide hit by Microsoft Outlook, Teams outage")
    add(it, "F", "f", "Microsoft outage: Teams and Outlook users hit globally")
    assert run(it, posted) == []

def test_followup_limit():
    it = {}
    three(it, "Microsoft outage hits Teams and Outlook users worldwide",
              "Global Microsoft outage hits Outlook and Teams users",
              "Microsoft Teams, Outlook outage hits users worldwide")
    first = run(it)[0]
    posted = [_post(first, NOW - 1800)] + [
        {"ts": NOW - 600, "text": "x", "words": [], "item_ids": [], "story_id": first["story_id"]}] * 3
    add(it, "D", "d", "Microsoft restores Teams and Outlook after outage")
    add(it, "E", "e", "Microsoft says Outlook, Teams restored after global outage")
    add(it, "F", "f", "Microsoft restores Outlook and Teams services after outage")
    assert run(it, posted) == []

def test_official_single_source_posts_immediately():
    it = {}
    add(it, "Federal Reserve", "fed", "Federal Reserve issues FOMC statement", official=True)
    s = run(it)
    assert len(s) == 1 and s[0]["priority"] == 3 and s[0]["credit"] == ["Federal Reserve"], s
    assert bot.build_posts(s[0])["plain"] == "🇺🇸 Federal Reserve Issues FOMC Statement"  # no "– Federal Reserve" repeat

def test_routine_official_notice_skipped():
    it = {}
    add(it, "Federal Reserve", "fed", "Federal Reserve Board announces approval of application by Example Bancorp", official=True)
    assert run(it) == []

# ---------------- price alerts ----------------
import prices  # noqa: E402
JPY = {"symbol": "JPY=X", "name": "USD/JPY", "flag": "🇯🇵", "tag": "#USDJPY", "step": 1, "pct": [1, 1.5, 2], "dp": 2}
BTC = {"symbol": "BTC-USD", "name": "Bitcoin", "flag": "", "tag": "#Bitcoin", "step": 5000, "pct": [3, 5, 8], "dp": 0, "prefix": "$"}

def test_price_first_seen_is_baseline():
    st = {}
    assert prices.check_symbol(JPY, 159.5, 159.0, int(NOW), st, NOW) is None and st["last"] == 159.5

def test_baseline_marks_moves_that_already_happened():
    st = {}
    assert prices.check_symbol(BTC, 66500.0, 71000.0, int(NOW), st, NOW) is None   # already -6.3% at setup
    st["last"] = 66600.0
    assert prices.check_symbol(BTC, 66400.0, 71000.0, int(NOW), st, NOW + 300) is None, "stale catch-up alert"
    st["last"] = 66400.0
    a = prices.check_symbol(BTC, 64000.0, 71000.0, int(NOW), st, NOW + 600)         # NEW move past -8%
    assert a and "Down 9.9%" in a["text"], a

def test_price_level_cross_up():
    st = {"last": 159.6}
    a = prices.check_symbol(JPY, 160.08, 159.9, int(NOW), st, NOW)
    assert a["text"] == "USD/JPY Rises Above 160, Now At 160.08", a
    assert a["flags"] == "🇯🇵" and "#USDJPY" in a["tags"]
    # same level again soon after (price wiggles) -> no repeat
    st["last"] = 159.95
    assert prices.check_symbol(JPY, 160.10, 159.9, int(NOW), st, NOW + 60) is None

def test_price_level_cross_down():
    st = {"last": 70500.0}
    a = prices.check_symbol(BTC, 68847.0, 69000.0, int(NOW), st, NOW)
    assert a["text"] == "Bitcoin Falls Below $70,000, Now At $68,847", a

def test_price_pct_once_per_day():
    st = {"last": 71000.0}
    a = prices.check_symbol(BTC, 66500.0, 71000.0, int(NOW), st, NOW)   # -6.3%
    assert a["text"] == "Bitcoin Down 6.3% On The Day At $66,500", a
    st["last"] = 66400.0
    assert prices.check_symbol(BTC, 66300.0, 71000.0, int(NOW), st, NOW + 300) is None
    st["last"] = 66300.0
    b = prices.check_symbol(BTC, 64000.0, 71000.0, int(NOW), st, NOW + 600)  # -9.9% -> new 8% level
    assert b and "Down 9.9%" in b["text"], b

def test_price_stale_data_no_alert():
    st = {"last": 159.6}
    assert prices.check_symbol(JPY, 160.5, 159.0, int(NOW - 3600), st, NOW) is None

def test_known_outlet_suffix_stripped_only():
    assert bot.clean_headline("Fed holds rates steady - Reuters") == "Fed holds rates steady"
    assert bot.clean_headline("Oil jumps 3% | Moneycontrol") == "Oil jumps 3%"
    assert bot.clean_headline("Japan - US Trade Talks Resume") == "Japan - US Trade Talks Resume"
    assert bot.clean_headline("Fed holds rates - Powell Says Inflation Sticky") == "Fed holds rates - Powell Says Inflation Sticky"

def test_secondhand_reports_blocked():
    assert bot.is_blocked("Anthropic weighs IPO pricing of $80-$85 a share, Bloomberg reports")
    assert bot.is_blocked("Anthropic Said to Be Weighing IPO Price as High as $85 Per Share")
    assert bot.is_blocked("Apple plans new chip, people familiar with the matter say")
    assert not bot.is_blocked("US jobs report shows 250,000 added in October")          # 'report' alone is fine
    assert not bot.is_blocked("Nvidia interim CEO Colette Kress promises salary hikes to 49,000 employees")

def test_may_month_not_blocked():
    assert not bot.is_blocked("US inflation falls to lowest since May 2024")
    assert not bot.is_blocked("May retail sales jump 1.2%")
    assert bot.is_blocked("Fed may cut rates in December")

def test_rdf_and_broken_xml_feeds():
    rdf = b"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"
      xmlns:dc="http://purl.org/dc/elements/1.1/"><item rdf:about="x"><title>ECB holds rates</title>
      <link>http://x</link><dc:date>2026-11-12T10:00:00Z</dc:date></item></rdf:RDF>"""
    e = bot.parse_feed(rdf)
    assert e[0]["title"] == "ECB holds rates" and e[0]["published"], e
    broken = b"<rss><channel><item><title><![CDATA[Gold hits record &nbsp; high]]></title><pubDate>Thu, 12 Nov 2026 20:00:00 GMT</pubDate></item><item><title>Oil &nbsp; falls</title></item></channel></rss>"
    titles = [x["title"] for x in bot.parse_feed(broken)]
    assert titles == ["Gold hits record &nbsp; high", "Oil &nbsp; falls"], titles
    assert bot.clean_headline(titles[1]) == "Oil falls"

def test_baseline_items_never_post():
    it = {}
    three(it, "Nvidia CEO Jensen Huang resigns", "Jensen Huang resigns as Nvidia chief", "Nvidia's Jensen Huang resigns as CEO")
    for v in it.values():
        v["baseline"] = True
    assert run(it) == []

def test_routine_rbi_notice_skipped():
    it = {}
    add(it, "RBI", "rbi", "Result of the 14-day Variable Rate Repo (VRR) auction held on November 12, 2026", official=True)
    add(it, "RBI2", "rbi", "RBI imposes monetary penalty on Example Bank for interest rate violations", official=True)
    assert run(it) == []
    add(it, "RBI3", "rbi", "RBI Monetary Policy Statement: repo rate cut by 25 basis points", official=True)
    assert len(run(it)) == 1

def test_congress_and_treasury_not_us():
    assert bot.detect_countries("Congress leader Rahul Gandhi slams Modi government") == ["IN"]
    assert bot.detect_countries("UK Treasury unveils budget, Reeves says") == ["GB"]
    assert bot.detect_countries("Rand Paul blocks bill") == []

def test_prefers_headline_with_numbers():
    it = {}
    add(it, "A", "a", "Malaysia ringgit weakens against the dollar")
    add(it, "B", "b", "Malaysia's ringgit weakens to 4.085 against the dollar")
    add(it, "C", "c", "Ringgit weakens against dollar, Malaysia data shows")
    s = run(it)
    assert "4.085" in s[0]["text"], s
    assert bot.build_posts(s[0])["plain"].endswith("– B"), bot.build_posts(s[0])

def test_same_story_twice_in_one_run_posts_once():
    import os
    for k in list(os.environ):
        if k.startswith(("THREADS", "BLUESKY", "TELEGRAM", "MASTODON", "DISCORD")):
            os.environ.pop(k)
    os.environ["DRY_RUN"] = "true"
    st1 = {"text": "Tesla's Musk resigns as CEO", "flags": "", "tags": [], "priority": 3, "focus": False,
           "words": ["tesla", "musk", "resign", "ceo"], "sources": ["A"], "credit": [], "item_ids": ["1"],
           "story_id": "1", "followup": False}
    st2 = dict(st1, text="Musk resigns as Tesla CEO", item_ids=["2"], story_id="2")
    import tempfile, pathlib, json
    d = pathlib.Path(tempfile.mkdtemp())
    bot.STATE_DIR, bot.ITEMS_FILE, bot.POSTED_FILE, bot.PRICES_FILE = d, d/"i.json", d/"p.json", d/"pr.json"
    bot.ITEMS_FILE.write_text("{}")
    real = (bot.find_stories, bot.prices.price_alerts, bot.fetch)
    bot.find_stories = lambda *a, **k: [st1, st2]
    bot.prices.price_alerts = lambda *a, **k: []
    bot.fetch = lambda *a, **k: None
    try:
        bot.main()
        assert len(json.loads(bot.POSTED_FILE.read_text())) == 1
    finally:
        bot.find_stories, bot.prices.price_alerts, bot.fetch = real
        os.environ.pop("DRY_RUN")

def test_generic_words_cannot_confirm_a_story():
    it = {}
    add(it, "A", "a", "Asian stocks rise as oil prices fall")
    add(it, "B", "b", "European stocks fall as oil prices rise")
    add(it, "C", "c", "US stocks rise while oil prices fall")
    assert run(it) == []

def test_level_formatting():
    assert prices.level_dp(50) == 0 and prices.level_dp(0.25) == 2 and prices.level_dp(0.01) == 2
    gold = {"symbol": "GC=F", "name": "Gold", "flag": "", "tag": "#Gold", "step": 50, "pct": [], "dp": 1, "prefix": "$"}
    a = prices.check_symbol(gold, 4061.3, 4060.0, int(NOW), {"last": 4040.0}, NOW)
    assert a["text"] == "Gold Rises Above $4,050, Now At $4,061.3", a

def test_bluesky_numeric_hash_not_a_tag():
    assert [f["features"][0]["tag"] for f in bot.bluesky_facets("Toyota keeps #1 spot\n\n#Japan")] == ["Japan"]

def test_http_error_shows_reason_not_url():
    import urllib.request, urllib.error, io
    real = urllib.request.urlopen
    def boom(*a, **k):
        raise urllib.error.HTTPError("https://api.telegram.org/botSECRET/sendMessage", 400, "Bad", {}, io.BytesIO(b'{"description":"chat not found"}'))
    urllib.request.urlopen = boom
    try:
        bot.http_post("https://api.telegram.org/botSECRET/sendMessage", {"a": 1})
        assert False
    except RuntimeError as e:
        assert "chat not found" in str(e) and "SECRET" not in str(e), e
    finally:
        urllib.request.urlopen = real

import images  # noqa: E402

def test_card_renders_jpeg_4x5():
    from PIL import Image
    import io
    jpg = images.render({"priority": 3, "countries": ["JP", "US"]}, "Japan's Nikkei Jumps 2.4% As Yen Weakens " * 4, "Nikkei")
    im = Image.open(io.BytesIO(jpg))
    assert im.format == "JPEG" and im.size == (1080, 1350)

def test_card_labels():
    assert images.label_for({"is_price": True})[0] == "PRICE ALERT"
    assert images.label_for({"followup": True, "priority": 3})[0] == "UPDATE"
    assert images.label_for({"priority": 2})[0] == "GEOPOLITICS"
    assert images.country_name("KR") == "SOUTH KOREA" and images.country_name("US") == "USA"

def test_image_platform_caps_and_priority():
    st3, st2 = {"priority": 3}, {"priority": 2}
    assert not bot.platform_wants("Instagram", st3, [], NOW)          # hourly digest mode: never per story
    assert not bot.platform_wants("Facebook", st3, [], NOW)
    old = bot.config.DIGEST_PLATFORMS
    bot.config.DIGEST_PLATFORMS = []                                   # per-story mode (digest off)
    try:
        _per_story_caps(st3, st2)
    finally:
        bot.config.DIGEST_PLATFORMS = old

def _per_story_caps(st3, st2):
    assert bot.platform_wants("Instagram", st3, [], NOW)
    assert not bot.platform_wants("Instagram", st2, [], NOW)          # geopolitics not on IG by default
    assert bot.platform_wants("Threads", st2, [], NOW)
    full = [{"ts": NOW - 60, "platforms": ["Instagram"]}] * bot.config.IMAGE_DAILY_LIMITS["Instagram"]
    assert not bot.platform_wants("Instagram", st3, full, NOW)
    assert bot.platform_wants("Facebook", st3, full, NOW)

def test_facebook_then_instagram_flow():
    import os
    os.environ.update({"FB_PAGE_ID": "PAGE", "FB_PAGE_TOKEN": "TOK", "IG_USER_ID": "IG"})
    calls = []
    def fake_file(url, fields, ff, fn, data):
        calls.append(("upload", url.split("/")[-2] + "/" + url.split("/")[-1], fields["published"]))
        assert data[:2] == b"\xff\xd8"                       # a real JPEG
        return {"id": "PHOTO1", "post_id": "PAGE_POST1"}
    def fake_get(url, params):
        calls.append(("get", url.split("/")[-1], params["fields"]))
        if params["fields"] == "images":
            return {"images": [{"width": 720, "source": "https://cdn/small.jpg"}, {"width": 1080, "source": "https://cdn/big.jpg"}]}
        return {"status_code": "FINISHED"}
    def fake_post(url, params=None, json_body=None, headers=None):
        calls.append(("post", url.split("/")[-1], params.get("image_url") or params.get("creation_id")))
        return {"id": "CONT1"} if url.endswith("/media") else {"id": "IGPOST1"}
    real = (bot.http_post_file, bot.http_get_json, bot.http_post)
    bot.http_post_file, bot.http_get_json, bot.http_post = fake_file, fake_get, fake_post
    try:
        story = {"text": "Bitcoin Down 6.3% On The Day At $66,500", "flags": "", "tags": ["#Bitcoin", "#Markets"],
                 "priority": 3, "is_price": True, "countries": [], "credit": []}
        p = bot.build_posts(story)
        assert bot.post_facebook(p) == "PAGE_POST1"
        assert bot.post_instagram(p) == "IGPOST1"
        assert ("post", "media", "https://cdn/big.jpg") in calls             # IG got the FB-hosted image
        assert ("post", "media_publish", "CONT1") in calls
        assert "#Bitcoin" in p["ig_caption"] and "Not financial advice" in p["ig_caption"]
        # Instagram alone (Facebook publishing off): image hosted unpublished
        calls.clear()
        p2 = bot.build_posts(story)
        bot.post_instagram(p2)
        assert ("upload", "PAGE/photos", "false") in calls, calls
    finally:
        bot.http_post_file, bot.http_get_json, bot.http_post = real
        for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN", "IG_USER_ID"):
            os.environ.pop(k)

def test_multipart_body_shape():
    import urllib.request
    seen = {}
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"id":"1"}'
    real = urllib.request.urlopen
    def fake(req, timeout=0):
        seen["ct"] = req.headers.get("Content-type"); seen["body"] = req.data
        return R()
    urllib.request.urlopen = fake
    try:
        assert bot.http_post_file("https://x/photos", {"message": "hi"}, "source", "card.jpg", b"\xff\xd8DATA") == {"id": "1"}
    finally:
        urllib.request.urlopen = real
    assert seen["ct"].startswith("multipart/form-data; boundary=")
    assert b'name="message"\r\n\r\nhi' in seen["body"] and b'filename="card.jpg"' in seen["body"] and b"\xff\xd8DATA" in seen["body"]

def _mock_all(calls, fail_images=False):
    """Fake every HTTP helper; records (kind, endpoint, detail)."""
    def post(url, params=None, json_body=None, headers=None):
        body = params or json_body or {}
        calls.append(("post", url.rsplit("/", 1)[-1], body.get("media_type") or body.get("media_ids[]")
                      or ("embed" if "embed" in (body.get("record") or {}) else body.get("text", "")[:10] if isinstance(body.get("text"), str) else "")))
        if "createSession" in url:
            return {"did": "did:x", "accessJwt": "jwt"}
        return {"id": "ID1", "uri": "at://1", "result": {"message_id": 7}}
    def post_file(url, fields, ff, fn, data, headers=None):
        if fail_images:
            raise RuntimeError("upload refused")
        calls.append(("file", url.rsplit("/", 1)[-1], ff))
        assert data[:2] == b"\xff\xd8"
        return {"id": "M1", "post_id": "P1", "result": {"message_id": 8}}
    def get_json(url, params):
        calls.append(("get", url.rsplit("/", 1)[-1], params.get("fields")))
        if params.get("fields") == "images":
            return {"images": [{"width": 1080, "source": "https://fbcdn/card.jpg"}]}
        return {"status": "FINISHED", "status_code": "FINISHED"}
    def post_bytes(url, data, headers):
        if fail_images:
            raise RuntimeError("blob refused")
        calls.append(("bytes", url.rsplit("/", 1)[-1], headers.get("Content-Type")))
        return {"blob": {"$type": "blob", "ref": {"$link": "x"}, "mimeType": "image/jpeg", "size": len(data)}}
    return post, post_file, get_json, post_bytes

def _with_mocks(fn, fail_images=False):
    import os
    calls = []
    real = (bot.http_post, bot.http_post_file, bot.http_get_json, bot.http_post_bytes, bot.time.sleep)
    bot.http_post, bot.http_post_file, bot.http_get_json, bot.http_post_bytes = _mock_all(calls, fail_images)
    bot.time.sleep = lambda s: None
    bot._bsky_session.clear()
    env = {"FB_PAGE_ID": "PAGE", "FB_PAGE_TOKEN": "T", "THREADS_ACCESS_TOKEN": "T", "BLUESKY_HANDLE": "h",
           "BLUESKY_APP_PASSWORD": "p", "TELEGRAM_BOT_TOKEN": "b", "TELEGRAM_CHANNEL_ID": "@c", "TELEGRAM_CHAT_ID": "1",
           "MASTODON_INSTANCE": "https://m.x", "MASTODON_TOKEN": "t", "DISCORD_WEBHOOK_URL": "https://d/wh"}
    os.environ.update(env)
    try:
        story = {"text": "Japan's Nikkei jumps 2.4% as yen weakens past 160", "flags": "🇯🇵", "tags": ["#Nikkei", "#Japan"],
                 "priority": 2, "countries": ["JP"], "credit": ["Nikkei"]}
        fn(bot.build_posts(story), calls)
    finally:
        bot.http_post, bot.http_post_file, bot.http_get_json, bot.http_post_bytes, bot.time.sleep = real
        for k in env:
            os.environ.pop(k)

def test_default_split_text_vs_cards():
    def check(p, calls):
        bot.post_threads(p); bot.post_bluesky(p); bot.post_mastodon(p); bot.notify_x_link(p, ["Nikkei"])
        assert ("post", "threads", "TEXT") in calls and not any(c[0] in ("file", "bytes") for c in calls), calls
        bot.post_telegram_channel(p); bot.post_discord(p)
        assert not any(c[0] in ("file", "bytes") for c in calls), calls      # Telegram & Discord: text too
    _with_mocks(check)

def test_card_on_every_platform():
    old = list(bot.config.CARD_PLATFORMS)
    bot.config.CARD_PLATFORMS = ["Facebook", "Instagram", "Threads", "Bluesky", "Telegram", "Mastodon", "Discord", "X"]
    try:
        _with_mocks(_check_all_cards)
    finally:
        bot.config.CARD_PLATFORMS = old

def _check_all_cards(p, calls):
    if True:
        bot.post_threads(p); bot.post_bluesky(p); bot.post_telegram_channel(p); bot.post_mastodon(p); bot.post_discord(p)
        bot.notify_x_link(p, ["Nikkei"])
        assert ("file", "photos", "source") in calls                      # hosted on FB (unpublished) for Threads
        assert ("post", "threads", "IMAGE") in calls
        assert ("bytes", "com.atproto.repo.uploadBlob", "image/jpeg") in calls and ("post", "com.atproto.repo.createRecord", "embed") in calls
        assert calls.count(("file", "sendPhoto", "photo")) == 2           # channel + private X alert
        assert ("file", "media", "file") in calls and ("post", "statuses", "M1") in calls
        assert ("file", "wh", "files[0]") in calls
        assert p["alt"].startswith("News Before Noise headline card: Japan's Nikkei")

def test_image_failure_falls_back_to_text():
    old = list(bot.config.CARD_PLATFORMS)
    bot.config.CARD_PLATFORMS = ["Threads", "Bluesky", "Telegram", "Mastodon", "Discord"]
    def check(p, calls):
        bot.post_threads(p); bot.post_bluesky(p); bot.post_telegram_channel(p); bot.post_mastodon(p); bot.post_discord(p)
        assert ("post", "threads", "TEXT") in calls
        assert ("post", "com.atproto.repo.createRecord", "embed") not in calls
        assert any(c[1] == "sendMessage" for c in calls) and any(c[1] == "statuses" for c in calls) and any(c[1] == "wh" for c in calls)
    try:
        _with_mocks(check, fail_images=True)
    finally:
        bot.config.CARD_PLATFORMS = old

def test_card_platform_list_respected():
    old = list(bot.config.CARD_PLATFORMS)
    bot.config.CARD_PLATFORMS = ["Facebook"]
    try:
        def check(p, calls):
            bot.post_telegram_channel(p)
            assert [c[1] for c in calls] == ["sendMessage"], calls
        _with_mocks(check)
    finally:
        bot.config.CARD_PLATFORMS = old

def _qitem(i, prio=3, ts=None):
    return {"ts": ts or NOW - 600 + i, "headline": f"Headline Number {i} Moves Markets", "credit": "CNBC",
            "plain": f"🇺🇸 Headline Number {i} Moves Markets – CNBC", "tags": ["#Fed", "#USA", "#Markets"],
            "priority": prio, "focus": True, "story": {"priority": prio, "countries": ["US"]}}

def test_digest_caps_at_10_slides_no_cover():
    items = [_qitem(i) for i in range(14)]
    dg = bot.build_digest(items)
    assert len(dg["slides"]) == 10 and dg["count"] == 14
    assert "+4 more headlines" in dg["caption"] and dg["caption"].count("\n10. ") == 1
    bot.config.DIGEST_COVER = True
    try:
        dg2 = bot.build_digest(items)
        assert len(dg2["slides"]) == 10 and "+5 more headlines" in dg2["caption"]
    finally:
        bot.config.DIGEST_COVER = False
    assert "#Fed" in dg["caption"] and "#Markets" in dg["caption"] and len(dg["caption"]) <= 2150
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(dg["slides"][0])).size == (1080, 1350)

def test_digest_most_important_first():
    items = [_qitem(1, prio=2), _qitem(2, prio=3)]
    dg = bot.build_digest(items)
    assert dg["caption"].index("Number 2") < dg["caption"].index("Number 1")

def test_digest_single_item_no_cover():
    dg = bot.build_digest([_qitem(1)])
    assert len(dg["slides"]) == 1 and not dg["caption"].startswith("🕐")

def test_hour_window_label():
    import datetime as dt
    t = dt.datetime(2026, 11, 18, 14, 25, tzinfo=dt.timezone.utc).timestamp()
    assert bot.hour_window(t, t) == "14:00–15:00 UTC"
    assert bot.hour_window(t, t + 2 * 3600) == "14:00–17:00 UTC"
    bot.config.DIGEST_TIMEZONE = "Asia/Kolkata"
    try:
        assert bot.hour_window(t, t) == "19:00–20:00 IST", bot.hour_window(t, t)
    finally:
        bot.config.DIGEST_TIMEZONE = "UTC"

def test_feed_parsing_rss_and_atom():
    rss = b"""<rss><channel><item><title>Fed holds rates steady</title><link>http://x</link>
      <pubDate>Thu, 12 Nov 2026 20:00:00 GMT</pubDate></item></channel></rss>"""
    atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Modi meets Trump</title>
      <link href="http://y"/><updated>2026-11-12T20:00:00Z</updated></entry></feed>"""
    assert bot.parse_feed(rss)[0]["title"] == "Fed holds rates steady"
    assert bot.parse_feed(atom)[0]["link"] == "http://y"
    assert bot.parse_feed(atom)[0]["published"] is not None

if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)
