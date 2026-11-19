"""Settings you can edit. No code changes needed elsewhere.
News Before Noise - free global-markets squawk (First Squawk style)."""

BRAND_NAME = "News Before Noise"
BRAND_HANDLE = "@NewsB4Noise"

# ===========================================================================
# 1. NEWS SOURCES (RSS)
# "owner" groups outlets owned by the same company (BBC World + BBC Business
# = one source). A story needs MIN_SOURCES different owners...
# ...EXCEPT feeds marked "official": True (central banks, statistics offices,
# regulators). Those are the original source, so ONE is enough - posted at once.
# Dead feeds are skipped automatically; check the run log for "feed failed".
# ===========================================================================
FEEDS = [
    # --- Global markets & business ---
    {"name": "Bloomberg Markets",  "owner": "bloomberg",  "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "Bloomberg Economics","owner": "bloomberg",  "url": "https://feeds.bloomberg.com/economics/news.rss"},
    {"name": "Bloomberg Politics", "owner": "bloomberg",  "url": "https://feeds.bloomberg.com/politics/news.rss"},
    {"name": "Bloomberg Tech",     "owner": "bloomberg",  "url": "https://feeds.bloomberg.com/technology/news.rss"},
    {"name": "WSJ Markets",        "owner": "dowjones",   "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "WSJ World",          "owner": "dowjones",   "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "WSJ Business",       "owner": "dowjones",   "url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"},
    {"name": "WSJ Tech",           "owner": "dowjones",   "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml"},
    {"name": "MarketWatch",        "owner": "dowjones",   "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
    {"name": "FT Markets",         "owner": "ft",         "url": "https://www.ft.com/markets?format=rss"},
    {"name": "FT World",           "owner": "ft",         "url": "https://www.ft.com/world?format=rss"},
    {"name": "FT Companies",       "owner": "ft",         "url": "https://www.ft.com/companies?format=rss"},
    {"name": "CNBC",               "owner": "cnbc",       "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"name": "CNBC World",         "owner": "cnbc",       "url": "https://www.cnbc.com/id/100727362/device/rss/rss.html"},
    {"name": "CNBC Markets",       "owner": "cnbc",       "url": "https://www.cnbc.com/id/15839069/device/rss/rss.html"},
    {"name": "CNBC Economy",       "owner": "cnbc",       "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "CNBC Finance",       "owner": "cnbc",       "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"},
    {"name": "CNBC Tech",          "owner": "cnbc",       "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html"},
    {"name": "Yahoo Finance",      "owner": "yahoo",      "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Fox Business",       "owner": "fox",        "url": "https://moxie.foxbusiness.com/google-publisher/latest.xml"},
    {"name": "Investing.com",      "owner": "investing",  "url": "https://www.investing.com/rss/news.rss"},
    {"name": "Seeking Alpha",      "owner": "seekingalpha","url": "https://seekingalpha.com/market_currents.xml"},
    {"name": "FXStreet",           "owner": "fxstreet",   "url": "https://www.fxstreet.com/rss/news"},
    {"name": "BBC Business",       "owner": "bbc",        "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "BBC World",          "owner": "bbc",        "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Guardian Business",  "owner": "guardian",   "url": "https://www.theguardian.com/business/rss"},
    {"name": "Guardian World",     "owner": "guardian",   "url": "https://www.theguardian.com/world/rss"},
    {"name": "Sky News Business",  "owner": "sky",        "url": "https://feeds.skynews.com/feeds/rss/business.xml"},
    {"name": "NPR",                "owner": "npr",        "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "Al Jazeera",         "owner": "aljazeera",  "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "DW Business",        "owner": "dw",         "url": "https://rss.dw.com/rdf/rss-en-bus"},
    {"name": "France 24 Business", "owner": "france24",   "url": "https://www.france24.com/en/business/rss"},
    {"name": "Euronews Business",  "owner": "euronews",   "url": "https://www.euronews.com/rss?level=vertical&name=business"},
    # --- Asia ---
    {"name": "Nikkei Asia",        "owner": "nikkei",     "url": "https://asia.nikkei.com/rss/feed/nar"},
    {"name": "SCMP Business",      "owner": "scmp",       "url": "https://www.scmp.com/rss/92/feed"},
    {"name": "Japan Times Business","owner": "japantimes","url": "https://www.japantimes.co.jp/business/feed/"},
    {"name": "Straits Times Business","owner": "sph",     "url": "https://www.straitstimes.com/news/business/rss.xml"},
    # --- India ---
    {"name": "Economic Times",     "owner": "timesgroup", "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
    {"name": "Times of India",     "owner": "timesgroup", "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"},
    {"name": "The Hindu Business", "owner": "thehindu",   "url": "https://www.thehindu.com/business/feeder/default.rss"},
    {"name": "NDTV",               "owner": "ndtv",       "url": "https://feeds.feedburner.com/ndtvnews-top-stories"},
    {"name": "Livemint",           "owner": "htmedia",    "url": "https://www.livemint.com/rss/markets"},
    {"name": "Business Standard",  "owner": "bs",         "url": "https://www.business-standard.com/rss/markets-106.rss"},
    {"name": "Moneycontrol",       "owner": "network18",  "url": "https://www.moneycontrol.com/rss/latestnews.xml"},
    # --- Crypto & commodities ---
    {"name": "CoinDesk",           "owner": "coindesk",   "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Cointelegraph",      "owner": "cointelegraph","url": "https://cointelegraph.com/rss"},
    {"name": "OilPrice",           "owner": "oilprice",   "url": "https://oilprice.com/rss/main"},
    # --- OFFICIAL (1 source is enough) ---
    {"name": "Federal Reserve", "owner": "fed", "official": True, "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
    {"name": "ECB",             "owner": "ecb", "official": True, "url": "https://www.ecb.europa.eu/rss/press.html"},
    {"name": "Bank of England", "owner": "boe", "official": True, "url": "https://www.bankofengland.co.uk/rss/news"},
    {"name": "Bank of Japan",   "owner": "boj", "official": True, "url": "https://www.boj.or.jp/en/rss/whatsnew.xml"},
    {"name": "RBI",             "owner": "rbi", "official": True, "url": "https://www.rbi.org.in/pressreleases_rss.xml"},
    {"name": "US BLS",          "owner": "bls", "official": True, "url": "https://www.bls.gov/feed/bls_latest.rss"},
    {"name": "US SEC",          "owner": "sec", "official": True, "url": "https://www.sec.gov/news/pressreleases.rss"},
]

# How many DIFFERENT owners must report the same story (non-official news).
MIN_SOURCES = 2

# TRUSTED outlets post from ONE source (First Squawk style), but only headlines
# first seen in the last TRUSTED_MAX_AGE_MINUTES, so it's genuinely breaking news.
# Empty list [] = every story needs MIN_SOURCES. Rumour/"reportedly" headlines are
# still blocked, and so is anything not about markets or geopolitics.
TRUSTED_OWNERS = ["bloomberg", "dowjones", "ft", "cnbc", "nikkei", "bbc"]
TRUSTED_MAX_AGE_MINUTES = 20

# Official feeds publish lots of routine notices. Only post official items
# whose title contains one of these words.
OFFICIAL_KEYWORDS = [
    "rate", "rates", "monetary policy", "policy decision", "statement", "minutes", "inflation",
    "cpi", "consumer price", "producer price", "employment situation", "payroll", "unemployment",
    "gdp", "jobless", "retail sales", "repo", "bank rate", "interest", "decision", "outlook",
    "financial stability", "emergency", "intervention", "swap line", "liquidity",
]

# ...and never post official items containing these (daily routine notices).
OFFICIAL_SKIP = [
    "auction", "money market operations", "penalty", "reserve money", "treasury bills",
    "variable rate repo", "variable rate reverse repo", "vrr", "vrrr", "enforcement", "termination",
    "application", "applications", "approval of", "proposed rule", "comment", "request for",
    "speech", "remarks", "testimony", "conference", "seminar", "calendar", "schedule", "consultation",
    "data release calendar", "statistical", "survey of", "working paper", "weekly", "lending",
    "compounding", "licence", "license", "cancellation", "directions", "circular",
]

# ===========================================================================
# 2. WHAT GETS POSTED (global, First Squawk style)
#   Tier 1 = markets: stocks, central banks, macro data, FX, bonds, commodities,
#            crypto, big companies, plus all official releases
#   Tier 2 = geopolitics & politics that move markets (any country)
#   Tier 3 = other news (off by default: INCLUDE_GENERAL_NEWS)
# Single words match whole words; phrases with spaces match anywhere.
# ===========================================================================
MARKET_KEYWORDS = [
    "stock", "stocks", "shares", "equities", "equity", "futures", "index", "indices", "market",
    "markets", "rally", "selloff", "sell-off", "bull", "bear", "investors", "traders", "volatility",
    "s&p", "nasdaq", "dow", "wall street", "ftse", "dax", "cac", "stoxx", "nikkei", "topix",
    "hang seng", "shanghai composite", "csi 300", "kospi", "asx", "sensex", "nifty", "dalal street",
    "fed", "federal reserve", "powell", "ecb", "lagarde", "boj", "bank of japan", "ueda", "boe",
    "bank of england", "pboc", "rbi", "snb", "central bank", "rate cut", "rate hike", "interest rate",
    "rates", "inflation", "cpi", "ppi", "gdp", "recession", "jobs", "payrolls", "unemployment",
    "pmi", "retail sales", "treasury", "treasuries", "bond", "bonds", "yield", "yields", "debt",
    "budget", "deficit", "stimulus", "tariff", "tariffs", "trade", "exports", "imports", "export",
    "import", "export curbs", "export controls", "rare earths", "chips", "chipmakers", "semiconductors",
    "dollar", "greenback", "yen", "euro", "yuan", "renminbi", "rupee", "sterling", "pound", "ringgit",
    "currency", "forex", "foreign exchange", "exchange rate", "intervention", "fx", "usd", "jpy", "eur", "gbp", "cny", "inr",
    "oil", "crude", "brent", "wti", "opec", "gas", "lng", "gold", "silver", "copper", "commodities",
    "bitcoin", "ether", "ethereum", "crypto", "stablecoin", "etf", "etfs",
    "earnings", "revenue", "profit", "guidance", "ipo", "merger", "acquisition", "acquire", "buyback",
    "dividend", "bankruptcy", "downgrade", "upgrade", "rating", "moody's", "fitch", "ceo", "layoffs",
    "outage", "billion", "trillion", "valuation", "sec", "sebi", "antitrust",
    "nvidia", "apple", "microsoft", "google", "alphabet", "amazon", "meta", "tesla", "openai",
    "intel", "amd", "tsmc", "samsung", "softbank", "toyota", "alibaba", "tencent", "byd", "boeing",
    "berkshire", "jpmorgan", "goldman", "blackrock", "reliance", "tata", "infosys", "adani", "hdfc",
    "aramco", "shell", "exxon", "chevron", "nestle", "lvmh", "asml", "sap",
]
GEO_KEYWORDS = [
    "president", "prime minister", "minister", "government", "parliament", "congress", "senate",
    "white house", "kremlin", "election", "elections", "vote", "coalition", "sanction", "sanctions",
    "war", "ceasefire", "truce", "missile", "missiles", "strike", "strikes", "attack", "military",
    "troops", "drone", "drones", "nuclear", "summit", "talks", "treaty", "nato", "g7", "g20", "brics",
    "united nations", "embargo", "blockade", "border", "invasion", "coup", "protest", "protests",
    "trump", "xi", "putin", "modi", "zelensky", "netanyahu", "takaichi", "starmer", "macron",
    "merz", "erdogan", "khamenei", "kim jong",
]
INCLUDE_GENERAL_NEWS = False   # True = also post tier 3 (sports, celebrities... not squawk-like)

# Optional: US & India stories go first within the same tier.
# Set REQUIRE_FOCUS_COUNTRY = True to post ONLY stories involving them.
FOCUS_COUNTRIES = ["US", "IN"]
REQUIRE_FOCUS_COUNTRY = False

# A headline containing any of these does NOT count as a confirming source.
BLOCKED_PHRASES = [
    "reportedly", "sources say", "sources said", "source says", "rumor", "rumour",
    "allegedly", "alleged", "unconfirmed", "speculation", "could ", "may ", "might ",
    "opinion", "analysis", "explainer", "explained", "live:", "live updates",
    "live blog", "watch:", "video", "podcast", "quiz", "photos", "in pics",
    "what to know", "what we know", "here's why", "here is why", "how to", "denies",
    "fake", "satire", "?", "best stocks", "stocks to buy", "top picks", "should you",
    "sponsored", "newsletter", "morning bid", "week ahead",
    # second-hand reports: many outlets repeating ONE source are not independent confirmation
    "said to be", "said to have", "said to plan", "said to weigh", "people familiar", "familiar with the matter",
    "according to a report", "according to reports", "report says", "reports say", "media report",
    "bloomberg reports", "reuters reports", "bloomberg news reports", "wsj reports", "ft reports",
    "cnbc reports", "axios reports", "the information reports", "nikkei reports", "report: ",
    ", bloomberg", ", reuters", ", wsj", "- bloomberg", "– bloomberg", "per bloomberg", "per reuters",
    # features & opinion that trusted outlets mix into their feeds
    "the big take", "big take:", "column:", "commentary", "op-ed", "interview:", "q&a", "review:",
    "the week in", "what's next", "five things", "5 things", "chart of the day", "charts:", "cartoon",
    "obituary", "letter:", "letters:", "lex:", "in pictures", "the morning", "evening briefing",
    "markets wrap", "stock market today", "live news", "playbook", "how i ", "my ", "why i ",
    # video / podcast shows (titles like "S&P Falls | Closing Bell")
    "| closing bell", "| bloomberg", "| the close", "| daybreak", "| surveillance", "| odd lots",
    "| balance of power", "| wall street week", "| the big take", "| squawk", "| power lunch",
    "| fast money", "| mad money", "| the exchange", "| money movers", "| podcast", "| video",
    ": how ", ": why ", ": what ", ": inside ",
]

# Headlines STARTING with these are features/explainers, not breaking news.
BLOCKED_STARTS = ["How ", "Why ", "What ", "What's ", "Inside ", "Opinion", "Analysis", "Explainer", "Here's ",
                  "These ", "This Is ", "Meet ", "The Case For", "The Case Against", "Patching "]

# ===========================================================================
# 3. COUNTRIES -> flag + hashtag. Up to MAX_FLAGS flags lead each post, in
# the order the countries appear in the headline. "US"/"U.S." is matched
# case-sensitively so the word "us" doesn't count.
# ===========================================================================
MAX_FLAGS = 2
DEFAULT_FLAG = ""          # e.g. "🌐" for stories with no country (Bitcoin...)
COUNTRIES = {
    "US": {"flag": "🇺🇸", "tag": "#USA", "words": ["united states", "america", "american", "washington",
           "white house", "pentagon", "trump", "vance", "rubio", "bessent", "us senate", "us congress",
           "fed", "federal reserve", "powell", "wall street", "nasdaq", "dow", "s&p", "us treasury",
           "treasuries", "greenback", "us-china", "us-india", "us-iran", "new york",
           "nvidia", "apple", "microsoft", "google", "alphabet", "amazon", "meta", "tesla", "openai",
           "intel", "amd", "boeing", "jpmorgan", "goldman", "blackrock", "berkshire", "exxon", "chevron",
           "anthropic", "palo alto", "netflix", "oracle", "salesforce", "broadcom", "qualcomm", "micron",
           "adobe", "ibm", "walmart", "costco", "citigroup", "citi", "bank of america", "wells fargo",
           "morgan stanley", "visa", "mastercard", "paypal", "coinbase", "uber", "airbnb", "pfizer",
           "eli lilly", "moderna", "johnson & johnson", "ford", "general motors", "spacex", "xai",
           "coca-cola", "pepsico", "mcdonald's", "starbucks", "disney", "nike", "caterpillar", "dell"]},
    "IN": {"flag": "🇮🇳", "tag": "#India", "words": ["india", "indian", "new delhi", "delhi", "modi",
           "jaishankar", "sitharaman", "rbi", "sebi", "sensex", "nifty", "dalal street", "rupee",
           "mumbai", "lok sabha", "india-us", "indo-us", "reliance", "adani", "tata", "infosys", "hdfc",
           "icici", "indigo", "wipro", "tcs", "bajaj", "maruti", "larsen", "ongc", "zomato", "eternal",
           "paytm", "hcl", "kotak", "axis bank", "vedanta", "sun pharma", "hindustan unilever", "itc"]},
    "CN": {"flag": "🇨🇳", "tag": "#China", "words": ["china", "chinese", "beijing", "xi jinping", "xi",
           "pboc", "yuan", "renminbi", "shanghai", "shenzhen", "csi 300", "alibaba", "tencent", "byd", "huawei"]},
    "JP": {"flag": "🇯🇵", "tag": "#Japan", "words": ["japan", "japanese", "tokyo", "boj", "bank of japan",
           "ueda", "takaichi", "yen", "nikkei", "topix", "softbank", "toyota", "sony", "smfg", "mufg"]},
    "GB": {"flag": "🇬🇧", "tag": "#UK", "words": ["britain", "british", "uk", "london", "starmer", "reeves",
           "boe", "bank of england", "sterling", "pound", "ftse"]},
    "EU": {"flag": "🇪🇺", "tag": "#EU", "words": ["eu", "european union", "eurozone", "euro zone", "brussels",
           "ecb", "lagarde", "euro", "stoxx", "von der leyen"]},
    "DE": {"flag": "🇩🇪", "tag": "#Germany", "words": ["germany", "german", "berlin", "merz", "bundesbank", "dax", "bund", "bunds"]},
    "FR": {"flag": "🇫🇷", "tag": "#France", "words": ["france", "french", "paris", "macron", "cac"]},
    "IT": {"flag": "🇮🇹", "tag": "#Italy", "words": ["italy", "italian", "meloni", "rome"]},
    "CH": {"flag": "🇨🇭", "tag": "#Switzerland", "words": ["switzerland", "swiss", "snb"]},
    "RU": {"flag": "🇷🇺", "tag": "#Russia", "words": ["russia", "russian", "moscow", "kremlin", "putin", "volgograd"]},
    "UA": {"flag": "🇺🇦", "tag": "#Ukraine", "words": ["ukraine", "ukrainian", "kyiv", "zelensky"]},
    "IR": {"flag": "🇮🇷", "tag": "#Iran", "words": ["iran", "iranian", "tehran", "khamenei"]},
    "IL": {"flag": "🇮🇱", "tag": "#Israel", "words": ["israel", "israeli", "netanyahu", "gaza", "hamas"]},
    "SA": {"flag": "🇸🇦", "tag": "#SaudiArabia", "words": ["saudi", "riyadh", "aramco"]},
    "AE": {"flag": "🇦🇪", "tag": "#UAE", "words": ["uae", "dubai", "abu dhabi", "emirates"]},
    "QA": {"flag": "🇶🇦", "tag": "#Qatar", "words": ["qatar", "doha"]},
    "TR": {"flag": "🇹🇷", "tag": "#Turkey", "words": ["turkey", "turkish", "turkiye", "erdogan", "lira"]},
    "PK": {"flag": "🇵🇰", "tag": "#Pakistan", "words": ["pakistan", "pakistani", "islamabad"]},
    "KR": {"flag": "🇰🇷", "tag": "#SouthKorea", "words": ["south korea", "south korean", "seoul", "kospi", "samsung"]},
    "KP": {"flag": "🇰🇵", "tag": "#NorthKorea", "words": ["north korea", "pyongyang", "kim jong"]},
    "TW": {"flag": "🇹🇼", "tag": "#Taiwan", "words": ["taiwan", "taiwanese", "taipei", "tsmc"]},
    "HK": {"flag": "🇭🇰", "tag": "#HongKong", "words": ["hong kong", "hang seng"]},
    "SG": {"flag": "🇸🇬", "tag": "#Singapore", "words": ["singapore"]},
    "MY": {"flag": "🇲🇾", "tag": "#Malaysia", "words": ["malaysia", "malaysian", "ringgit", "kuala lumpur"]},
    "ID": {"flag": "🇮🇩", "tag": "#Indonesia", "words": ["indonesia", "indonesian", "jakarta"]},
    "VN": {"flag": "🇻🇳", "tag": "#Vietnam", "words": ["vietnam", "vietnamese"]},
    "PH": {"flag": "🇵🇭", "tag": "#Philippines", "words": ["philippines", "philippine", "manila"]},
    "TH": {"flag": "🇹🇭", "tag": "#Thailand", "words": ["thailand", "thai", "bangkok"]},
    "AU": {"flag": "🇦🇺", "tag": "#Australia", "words": ["australia", "australian", "asx", "rba"]},
    "NZ": {"flag": "🇳🇿", "tag": "#NewZealand", "words": ["new zealand", "rbnz"]},
    "CA": {"flag": "🇨🇦", "tag": "#Canada", "words": ["canada", "canadian", "ottawa", "carney", "loonie"]},
    "MX": {"flag": "🇲🇽", "tag": "#Mexico", "words": ["mexico", "mexican", "mexican peso"]},
    "BR": {"flag": "🇧🇷", "tag": "#Brazil", "words": ["brazil", "brazilian", "lula"]},
    "AR": {"flag": "🇦🇷", "tag": "#Argentina", "words": ["argentina", "argentine", "milei"]},
    "VE": {"flag": "🇻🇪", "tag": "#Venezuela", "words": ["venezuela", "venezuelan", "maduro", "caracas"]},
    "ZA": {"flag": "🇿🇦", "tag": "#SouthAfrica", "words": ["south africa", "south african"]},
    "EG": {"flag": "🇪🇬", "tag": "#Egypt", "words": ["egypt", "egyptian", "cairo"]},
    "NG": {"flag": "🇳🇬", "tag": "#Nigeria", "words": ["nigeria", "nigerian"]},
    "BD": {"flag": "🇧🇩", "tag": "#Bangladesh", "words": ["bangladesh", "dhaka"]},
    "LK": {"flag": "🇱🇰", "tag": "#SriLanka", "words": ["sri lanka"]},
    "NO": {"flag": "🇳🇴", "tag": "#Norway", "words": ["norway", "norwegian"]},
    "NL": {"flag": "🇳🇱", "tag": "#Netherlands", "words": ["netherlands", "dutch", "asml"]},
    "ES": {"flag": "🇪🇸", "tag": "#Spain", "words": ["spain", "spanish", "madrid"]},
    "PL": {"flag": "🇵🇱", "tag": "#Poland", "words": ["poland", "polish", "warsaw"]},
    "GR": {"flag": "🇬🇷", "tag": "#Greece", "words": ["greece", "greek", "athens"]},
}

# ===========================================================================
# 4. HASHTAGS. X/Bluesky/Telegram get up to MAX_HASHTAGS_X; Threads gets the
# single best one (Threads allows one topic tag per post).
# ===========================================================================
MAX_HASHTAGS_X = 3
HASHTAG_RULES = [
    ("#Tariffs",      ["tariff", "tariffs", "trade war", "import duty", "import duties"]),
    ("#TradeDeal",    ["trade deal", "trade pact", "trade agreement", "trade talks"]),
    ("#Sanctions",    ["sanction", "sanctions"]),
    ("#Fed",          ["fed", "federal reserve", "powell", "fomc"]),
    ("#ECB",          ["ecb", "lagarde"]),
    ("#BOJ",          ["boj", "bank of japan", "ueda"]),
    ("#BOE",          ["boe", "bank of england"]),
    ("#PBOC",         ["pboc"]),
    ("#RBI",          ["rbi", "reserve bank of india"]),
    ("#InterestRates",["rate cut", "rate hike", "interest rate", "interest rates", "repo rate"]),
    ("#Inflation",    ["inflation", "cpi", "ppi"]),
    ("#Jobs",         ["payrolls", "jobs report", "unemployment", "jobless"]),
    ("#GDP",          ["gdp"]),
    ("#Bonds",        ["treasury", "treasuries", "bond", "bonds", "yield", "yields", "gilts", "bunds"]),
    ("#USDJPY",       ["usd/jpy", "dollar/yen", "usdjpy"]),
    ("#Forex",        ["yen", "yuan", "eur/usd", "sterling", "rupee", "ringgit", "peso", "lira",
                       "forex", "currency", "greenback", "dollar", "foreign exchange", "exchange rate"]),
    ("#CrudeOil",     ["crude", "oil", "brent", "wti", "opec"]),
    ("#Gold",         ["gold"]),
    ("#Bitcoin",      ["bitcoin", "btc"]),
    ("#Ethereum",     ["ether", "ethereum"]),
    ("#Crypto",       ["crypto", "stablecoin"]),
    ("#Earnings",     ["earnings", "quarterly results", "q1", "q2", "q3", "q4", "guidance"]),
    ("#IPO",          ["ipo"]),
    ("#MergersAndAcquisitions", ["merger", "acquisition", "acquire", "takeover"]),
    ("#Layoffs",      ["layoffs", "layoff", "job cuts"]),
    ("#Sensex",       ["sensex"]), ("#Nifty", ["nifty"]),
    ("#Nikkei",       ["nikkei"]), ("#HangSeng", ["hang seng"]), ("#DAX", ["dax"]), ("#FTSE", ["ftse"]),
    ("#WallStreet",   ["wall street", "dow", "nasdaq", "s&p"]),
    ("#AI",           ["ai", "artificial intelligence", "data centre", "data center", "hyperscalers"]),
    ("#Nvidia", ["nvidia"]), ("#Apple", ["apple"]), ("#Tesla", ["tesla"]),
    ("#Microsoft", ["microsoft"]), ("#Google", ["google", "alphabet"]), ("#Amazon", ["amazon"]),
    ("#Meta", ["meta"]), ("#OpenAI", ["openai"]), ("#SoftBank", ["softbank"]), ("#TSMC", ["tsmc"]),
    ("#Reliance", ["reliance"]), ("#Adani", ["adani"]),
    ("#Ceasefire",    ["ceasefire", "truce"]),
    ("#Elections",    ["election", "elections"]),
    ("#Trump", ["trump"]), ("#Putin", ["putin"]), ("#XiJinping", ["xi jinping"]), ("#Modi", ["modi"]),
]
MARKET_TAG = "#Markets"          # added to tier-1 stories
GEO_TAG = "#Geopolitics"         # added to tier-2 stories

# Google Trends' free "trending now" feeds: a trending search that appears
# in the headline is added as a tag (e.g. #NvidiaStock).
USE_TRENDING = True
TRENDS_FEEDS = [
    "https://trends.google.com/trending/rss?geo=US",
    "https://trends.google.com/trending/rss?geo=IN",
    "https://trends.google.com/trending/rss?geo=GB",
]

# ===========================================================================
# 5. SQUAWK STYLE
# ===========================================================================
POST_PREFIX = ""
SHOW_FLAGS = True            # False = no flags at all (pure First Squawk look)
TITLE_CASE = True            # "Bitcoin Extends Losses As Price Falls..."
SHOW_SOURCES = True          # "... – FT" (text only, no links), like First Squawk
MAX_SOURCES_SHOWN = 1        # First Squawk credits one source; 3 = "– CNBC, BBC, ET"
MAX_HEADLINE_CHARS = 200     # prefer headlines shorter than this
POST_SPACING_SECONDS = 15    # gap between posts in one run (natural squawk rhythm)
# For a pure First Squawk look: SHOW_FLAGS = False and MAX_HASHTAGS_X = 0
OWNER_LABELS = {
    "bloomberg": "Bloomberg", "dowjones": "WSJ", "ft": "FT", "cnbc": "CNBC", "yahoo": "Yahoo Finance",
    "fox": "Fox Business", "investing": "Investing.com", "seekingalpha": "Seeking Alpha",
    "fxstreet": "FXStreet", "bbc": "BBC", "guardian": "Guardian", "sky": "Sky News", "npr": "NPR",
    "aljazeera": "Al Jazeera", "dw": "DW", "france24": "France 24", "euronews": "Euronews",
    "nikkei": "Nikkei", "scmp": "SCMP", "japantimes": "Japan Times", "sph": "Straits Times",
    "timesgroup": "ET", "thehindu": "The Hindu", "ndtv": "NDTV", "htmedia": "Mint",
    "bs": "Business Standard", "network18": "Moneycontrol", "coindesk": "CoinDesk",
    "cointelegraph": "Cointelegraph", "oilprice": "OilPrice", "fed": "Federal Reserve", "ecb": "ECB",
    "boe": "BoE", "boj": "BoJ", "rbi": "RBI", "bls": "BLS", "sec": "SEC", "prices": "Market Data",
}

# Follow-ups: post real updates on a story already posted
# (outage -> cause found -> services restored). Repeats are skipped.
FOLLOWUPS = True
FOLLOWUP_PREFIX = ""         # First Squawk posts updates without a label; e.g. "UPDATE: "
FOLLOWUP_HOURS = 12
MAX_FOLLOWUPS = 3
FOLLOWUP_MIN_NEW_WORDS = 1
FOLLOWUP_SIGNALS = [
    "confirm", "den", "restor", "resum", "resign", "arrest", "kill", "dead", "death", "toll",
    "injur", "rise", "rose", "fall", "fell", "jump", "surg", "plung", "slump", "cut", "hike",
    "approv", "reject", "sign", "ban", "lift", "retaliat", "respond", "end", "extend", "charg",
    "sue", "win", "won", "lose", "lost", "agre", "halt", "suspend", "launch", "strik", "attack",
    "evacuat", "impos", "delay", "cancel", "fire", "elect", "pass", "veto", "block", "freez",
]

# ===========================================================================
# 6. LIVE PRICE ALERTS (free, from Yahoo Finance's public chart data)
# Posts like "USD/JPY Rises Above 160.00, Now At 160.08" or
# "Bitcoin Down 5.2% On The Day At $68,847".
#   step = round-number levels to alert on (crossing 160.00, 161.00...)
#   pct  = daily % moves to alert on (each level once per day per direction)
#   fmt  = number format, prefix = "$" etc.
# ===========================================================================
PRICE_ALERTS = True
PRICE_SYMBOLS = [
    {"symbol": "^GSPC",   "name": "S&P 500",      "flag": "🇺🇸", "tag": "#SPX",     "step": 100,  "pct": [1, 2, 3, 4], "dp": 0},
    {"symbol": "^IXIC",   "name": "Nasdaq Composite","flag": "🇺🇸","tag": "#Nasdaq", "step": 500,  "pct": [1, 2, 3, 4], "dp": 0},
    {"symbol": "^DJI",    "name": "Dow Jones",    "flag": "🇺🇸", "tag": "#DowJones", "step": 1000, "pct": [1, 2, 3, 4], "dp": 0},
    {"symbol": "^VIX",    "name": "VIX",          "flag": "🇺🇸", "tag": "#VIX",     "step": 5,    "pct": [15, 25, 40], "dp": 2},
    {"symbol": "^NSEI",   "name": "Nifty 50",     "flag": "🇮🇳", "tag": "#Nifty",   "step": 500,  "pct": [1, 2, 3],    "dp": 0},
    {"symbol": "^BSESN",  "name": "Sensex",       "flag": "🇮🇳", "tag": "#Sensex",  "step": 1000, "pct": [1, 2, 3],    "dp": 0},
    {"symbol": "^N225",   "name": "Nikkei 225",   "flag": "🇯🇵", "tag": "#Nikkei",  "step": 1000, "pct": [1.5, 3, 5],  "dp": 0},
    {"symbol": "^HSI",    "name": "Hang Seng",    "flag": "🇭🇰", "tag": "#HangSeng","step": 1000, "pct": [1.5, 3, 5],  "dp": 0},
    {"symbol": "^GDAXI",  "name": "DAX",          "flag": "🇩🇪", "tag": "#DAX",     "step": 500,  "pct": [1, 2, 3],    "dp": 0},
    {"symbol": "^FTSE",   "name": "FTSE 100",     "flag": "🇬🇧", "tag": "#FTSE",    "step": 250,  "pct": [1, 2, 3],    "dp": 0},
    {"symbol": "JPY=X",   "name": "USD/JPY",      "flag": "🇯🇵", "tag": "#USDJPY",  "step": 1,    "pct": [1, 1.5, 2],  "dp": 2},
    {"symbol": "INR=X",   "name": "USD/INR",      "flag": "🇮🇳", "tag": "#Rupee",   "step": 0.5,  "pct": [0.5, 1],     "dp": 2},
    {"symbol": "EURUSD=X","name": "EUR/USD",      "flag": "🇪🇺", "tag": "#EURUSD",  "step": 0.01, "pct": [1, 1.5],     "dp": 4},
    {"symbol": "CNY=X",   "name": "USD/CNY",      "flag": "🇨🇳", "tag": "#Yuan",    "step": 0.1,  "pct": [0.5, 1],     "dp": 4},
    {"symbol": "DX-Y.NYB","name": "Dollar Index", "flag": "🇺🇸", "tag": "#DXY",     "step": 1,    "pct": [1, 1.5],     "dp": 2},
    {"symbol": "GC=F",    "name": "Gold",         "flag": "",   "tag": "#Gold",     "step": 50,   "pct": [2, 3, 5],    "dp": 1, "prefix": "$"},
    {"symbol": "SI=F",    "name": "Silver",       "flag": "",   "tag": "#Silver",   "step": 2,    "pct": [3, 5, 8],    "dp": 2, "prefix": "$"},
    {"symbol": "CL=F",    "name": "WTI Crude",    "flag": "",   "tag": "#CrudeOil", "step": 5,    "pct": [3, 5, 8],    "dp": 2, "prefix": "$"},
    {"symbol": "BZ=F",    "name": "Brent Crude",  "flag": "",   "tag": "#CrudeOil", "step": 5,    "pct": [3, 5, 8],    "dp": 2, "prefix": "$"},
    {"symbol": "BTC-USD", "name": "Bitcoin",      "flag": "",   "tag": "#Bitcoin",  "step": 5000, "pct": [3, 5, 8, 12],"dp": 0, "prefix": "$"},
    {"symbol": "ETH-USD", "name": "Ether",        "flag": "",   "tag": "#Ethereum", "step": 250,  "pct": [4, 7, 10],   "dp": 0, "prefix": "$"},
]
PRICE_LEVEL_COOLDOWN_HOURS = 6   # don't repeat the same level within this time

# ===========================================================================
# 7. INSTAGRAM & FACEBOOK IMAGE CARDS (black background, white headline)
# Instagram allows 100 API posts/day and a flooded feed loses reach, so image
# platforms get their own (lower) daily caps and only the important stories.
# ===========================================================================
# Platforms that get the image card (text is still in the caption); the rest post
# fast squawk-style text. Cards on Instagram & Facebook (visual feeds); squawk text
# everywhere else. Add/remove names to change it. Possible names:
# "Facebook", "Instagram", "Threads", "Bluesky", "Telegram", "Mastodon", "Discord",
# "X" (= the card is also sent with your private one-tap X link).
CARD_PLATFORMS = ["Facebook", "Instagram"]
IMAGE_DAILY_LIMITS = {"Facebook": 40, "Instagram": 25}   # only used if a platform is NOT in DIGEST_PLATFORMS

# HOURLY DIGEST: instead of one post per headline, these platforms get ONE post per
# hour: a swipeable carousel (cover slide summarising the hour + one card per
# headline, max 10 slides). Every other platform keeps posting each headline live.
# Set DIGEST_PLATFORMS = [] to go back to one Facebook/Instagram post per headline.
DIGEST_PLATFORMS = ["Facebook", "Instagram"]
DIGEST_MIN_PRIORITY = 2          # 2 = markets + geopolitics; 3 = markets & price alerts only
DIGEST_MAX_SLIDES = 10           # Instagram carousels allow up to 10 via the API
DIGEST_COVER = False             # False = slide 1 is the top headline itself (no summary cover slide)
DIGEST_TIMEZONE = "America/New_York"   # hours & labels in Eastern time ("16:00–17:00 EST"); or "UTC", "Asia/Kolkata"
DIGEST_MAX_ATTEMPTS = 3          # retries per platform if Facebook/Instagram is down
DIGEST_MAX_AGE_HOURS = 2         # never put headlines older than this in a carousel
IMAGE_MIN_PRIORITY = 3          # 3 = markets + price alerts only; 2 = also geopolitics
MAX_HASHTAGS_INSTAGRAM = 5
FACEBOOK_PUBLISH = True          # False = upload to the Page unpublished, only to host the Instagram image
GRAPH_API_VERSION = "v24.0"      # Meta Graph API version (update every ~2 years)
CARD_BACKGROUND = (0, 0, 0)
CARD_TEXT = (255, 255, 255)
CARD_ACCENT_MARKETS = (255, 196, 0)    # yellow pill
CARD_ACCENT_GEO = (255, 90, 90)        # red pill
CARD_ACCENT_PRICE = (0, 200, 140)      # green pill
CARD_ACCENT_UPDATE = (90, 160, 255)    # blue pill

# ===========================================================================
# 8. LIMITS & MATCHING
# ===========================================================================
MAX_POSTS_PER_DAY = 200   # rolling 24h (Threads allows 250)
MAX_POSTS_PER_RUN = 5     # per 5-minute run
FRESH_HOURS = 3           # ignore news older than this
MIN_SHARED_WORDS = 3      # headlines must share this many key words...
MIN_OVERLAP = 0.5         # ...and this fraction of the shorter one's key words...
MIN_SPECIFIC_WORDS = 2    # ...and at least this many SPECIFIC shared words (not in GENERIC_WORDS)
GENERIC_WORDS = """
stock stocks share shares market markets price prices rise rises rose fall falls fell gain gains drop drops
jump jumps slip slips climb climbs surge surges slump slumps plunge plunges rally rallies tumble tumbles
higher lower high low record investor investors trader traders trading trade trades rate rates oil gold
dollar dollars global world asian asia european europe economy economic growth percent pct points point
index indices futures bond bonds yield yields deal deals plan plans cut cuts hike hikes amid ahead
government official officials minister company companies firm firms bank banks billion million trillion
week month quarter year annual data report reports news sector sectors demand supply cost costs
""".split()

# ===========================================================================
# 9. EXTRAS (update 7)
# ===========================================================================
# --- 🔴 BREAKING label for the biggest stories --------------------------------
BREAKING_ENABLED = True
BREAKING_LABEL = "🔴 BREAKING: "
BREAKING_MAX_PER_DAY = 10        # keep it rare so it still means something
BREAKING_OFFICIAL = True         # official central-bank / statistics releases count as breaking
BREAKING_PRICE_PCT = 2           # index moves of this % or more on the day
BREAKING_PRICE_SYMBOLS = ["^GSPC", "^IXIC", "^DJI", "^NSEI", "^BSESN", "^N225", "^HSI", "^GDAXI", "^FTSE"]
BREAKING_KEYWORDS = [
    "cuts rates", "cuts interest rate", "raises rates", "raises interest rate", "hikes rates",
    "hikes interest rate", "holds rates", "keeps rates", "leaves rates", "rate decision", "emergency rate",
    "emergency meeting", "declares war", "invades", "invasion", "missile strike", "missile attack",
    "airstrike", "air strike", "ceasefire", "coup", "assassinat", "martial law", "state of emergency",
    "nuclear test", "resigns", "impeach", "defaults on", "circuit breaker", "trading halted",
]

# --- 🔔 Market open / close summaries ------------------------------------------
# Posted once per trading day, a few minutes after the bell, using the live prices
# the bot already reads. Skipped automatically on holidays (no fresh prices).
#   at    = local time to post (posts any time in the next 60 minutes if a run is late)
#   fresh = prices must be newer than this local time (proves the market traded today)
MARKET_BELLS = [
    {"id": "us_open",  "title": "🔔 US Stocks Open",  "tz": "America/New_York", "at": "09:35", "fresh": "09:30",
     "symbols": ["^GSPC", "^IXIC", "^DJI", "^VIX"], "tags": ["#StockMarket", "#SPX"]},
    {"id": "us_close", "title": "🔔 US Stocks Close", "tz": "America/New_York", "at": "16:05", "fresh": "15:55",
     "symbols": ["^GSPC", "^IXIC", "^DJI", "^VIX", "DX-Y.NYB", "GC=F", "CL=F", "BTC-USD"],
     "tags": ["#StockMarket", "#SPX"]},
    {"id": "in_open",  "title": "🔔 India Stocks Open",  "tz": "Asia/Kolkata", "at": "09:20", "fresh": "09:15",
     "symbols": ["^NSEI", "^BSESN", "INR=X"], "tags": ["#Nifty", "#Sensex"]},
    {"id": "in_close", "title": "🔔 India Stocks Close", "tz": "Asia/Kolkata", "at": "15:35", "fresh": "15:25",
     "symbols": ["^NSEI", "^BSESN", "INR=X"], "tags": ["#Nifty", "#Sensex"]},
]
BELL_WINDOW_MINUTES = 60

# --- 🗓 Economic calendar ---------------------------------------------------------
# Free weekly calendar (Forex Factory's public JSON). The bot posts:
#   * a "Today's key data" list each weekday morning, and
#   * a "Coming up" heads-up shortly before each high-impact release.
# The actual numbers then arrive through the normal news feeds (BLS, Fed, etc.).
CALENDAR_ENABLED = True
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CALENDAR_REFRESH_HOURS = 4       # the file updates hourly; don't hammer it
CALENDAR_IMPACT = ["High"]       # add "Medium" for more events
CALENDAR_COUNTRIES = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "CNY": "🇨🇳"}
CALENDAR_HEADS_UP_MINUTES = 15   # "Coming up" about this many minutes before (posted 5-17 min ahead)
CALENDAR_TIMEZONE = "America/New_York"
CALENDAR_DAILY_AT = "07:00"      # "Today's key data" post (weekdays, local time above)
CALENDAR_MAX_LINES = 8

# --- 📊 Daily health report (private Telegram chat) ------------------------------
DAILY_REPORT = True
DAILY_REPORT_TIMEZONE = "America/New_York"
DAILY_REPORT_AT = "21:00"

# ===========================================================================
# 10. RECAPS & GROWTH (update 8)
# ===========================================================================
# --- 🎬 Daily reel: top stories of the day as a short video with music -------------
REEL_ENABLED = True
REEL_PLATFORMS = ["Instagram", "Facebook", "Telegram"]   # Instagram Reels, Facebook Reels, Telegram channel video
REEL_AT = "18:30"                 # local time (DIGEST_TIMEZONE), after the US close
REEL_STORIES = 5
REEL_INTRO_SECONDS = 2.8
REEL_STORY_SECONDS = 3.8
REEL_OUTRO_SECONDS = 3.2
REEL_FADE_SECONDS = 0.5
REEL_MUSIC_VOLUME = 0.9           # original tracks in newsbot/assets/music (rotate daily). Add your own .mp3/.m4a there.
REEL_MAX_ATTEMPTS = 3
REEL_HASHTAGS = ["#Markets", "#StockMarket", "#News", "#Finance", "#Economy"]

# --- 📅 Weekly recap: "The Week In Markets" carousel every Sunday -----------------
WEEKLY_ENABLED = True
WEEKLY_AT = "11:00"               # Sunday, local time (DIGEST_TIMEZONE)
WEEKLY_STORIES = 10
WEEKLY_HASHTAGS = ["#Markets", "#WeekInReview", "#StockMarket", "#Geopolitics", "#Economy"]

# --- 👋 One-time welcome post (pinned on Telegram; pin it yourself on Threads) ----
WELCOME_ENABLED = True
WELCOME_TEXT = (
    "👋 Welcome to News Before Noise\n\n"
    "Global markets & geopolitics headlines, as they break. Every story is confirmed by "
    "multiple sources or comes from an official source. No noise.\n\n"
    "🔴 Breaking news\n🔔 Market open & close\n🗓 Economic calendar & data releases\n"
    "📈 Live price alerts\n🎬 Daily top-5 reel · 📅 Weekly recap\n\n"
    "All our channels: https://newsbeforenoise.github.io/newsbot/\n\n"
    "Automated headline alerts. Not financial advice."
)

# --- 👥 Follower counts in the daily report ----------------------------------------
REPORT_FOLLOWERS = True
