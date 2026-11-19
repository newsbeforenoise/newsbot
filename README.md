# News Before Noise — free global-markets squawk bot (First Squawk style)

- **Fast squawk-style text** → Threads, Bluesky, Telegram channel, Mastodon, Discord (and X, via a one-tap link
  in your private Telegram, because X has no free API).
- **Hourly swipeable carousel** → Instagram and Facebook: ONE post per hour, one black card per headline
  (slide 1 = the top headline, max 10 slides). Optional summary cover slide: `DIGEST_COVER = True`.
All automatic. If an image ever fails, that platform posts plain text instead. Change the split in `CARD_PLATFORMS`.

How it works (every 5 minutes, free on GitHub Actions):
1. **Reads ~45 news feeds**: Bloomberg, WSJ, FT, CNBC, BBC, Nikkei, SCMP, ET, Mint, CoinDesk, OilPrice…
2. **Confirms before posting:** a story needs **3 different owners** reporting it (BBC World + BBC Business = 1),
   **except official sources** (Fed, ECB, BoE, BoJ, RBI, US BLS, SEC): the original source is enough, so it posts at once.
   Headlines with "reportedly", "sources say", "could", "?" etc. never count, and headlines must share
   **specific** words (names, places, numbers): "Asian stocks rise as oil falls" and "European stocks fall as
   oil rises" are NOT the same story, so generic look-alikes can never fake a 3-source confirmation.
3. **Global markets first, like First Squawk:**
   - **Tier 1, markets:** stocks, central banks, macro data, FX, bonds, oil/gold, crypto, big companies, official releases
   - **Tier 2, geopolitics:** wars, sanctions, elections, summits, any country
   - Tier 3 general news is off (`INCLUDE_GENERAL_NEWS`). Within a tier, 🇺🇸/🇮🇳 stories go first (`FOCUS_COUNTRIES`).
4. **Live price alerts** (free, Yahoo Finance public data): S&P, Nasdaq, Dow, VIX, Nifty, Sensex, Nikkei, Hang Seng,
   DAX, FTSE, USD/JPY, USD/INR, EUR/USD, USD/CNY, DXY, gold, silver, WTI, Brent, Bitcoin, Ether, e.g.
   `🇯🇵 USD/JPY Rises Above 160.00, Now At 160.08` · `Bitcoin Down 6.3% On The Day At $66,500`
   (round-number levels + daily % moves, each once; edit `PRICE_SYMBOLS`).
5. **Squawk style:** country flags in headline order (up to 2), Title Case, prefers headlines with numbers,
   credits the outlet whose headline is used (like First Squawk's "– FT"), no links:
   `🇯🇵 SoftBank Books $3.7bn Charge Over Failed Gas Turbine Bet For AI – Nikkei`
   `🇺🇸 Federal Reserve Issues FOMC Statement`
   **Follow-ups:** real updates on a posted story (`Microsoft Restores Teams And Outlook After Outage`), max 3 per story
   within 12h; repeats with nothing new are skipped.
   Want the *pure* First Squawk look? `SHOW_FLAGS = False` and `MAX_HASHTAGS_X = 0`.
6. **Hashtags:** up to 3 on X/Bluesky/Telegram/Mastodon/Discord (+ a matching Google Trends search); Threads gets its one topic tag.
7. **Auto-posts** to Threads, Bluesky, Telegram channel, Mastodon, Discord (whichever you set up). If one fails, the others still post.
   **Hourly carousel** on Instagram and Facebook (`DIGEST_PLATFORMS`): every headline of the hour is collected,
   and at the top of the next hour (≈5–15 min past, GitHub timing) ONE post goes out: one card per headline,
   slide 1 = the most important (optional summary cover slide: `DIGEST_COVER = True`) (black background, white headline, MARKETS / GEOPOLITICS /
   PRICE ALERT / UPDATE pill, country tags, source, @NewsB4Noise). Most important first; if more than 10,
   the top 10 are shown and the caption says how many more. 1 headline = a single image; 0 = no post.
   Max 24 posts/day, far under Instagram's limit. If Instagram is down, it's retried (Facebook isn't re-posted).
   Hour labels use `DIGEST_TIMEZONE` (UTC by default; e.g. "America/New_York", "Asia/Kolkata").
   Set `DIGEST_PLATFORMS = []` to go back to one Facebook/Instagram post per headline.
   Threads, Bluesky, Telegram, Mastodon, Discord and X stay text; add any of them to `CARD_PLATFORMS` to switch
   it to cards (Bluesky/Mastodon cards include alt text).
   The carousel includes markets, price alerts and geopolitics (`DIGEST_MIN_PRIORITY`).
   (If you ever add Threads to `CARD_PLATFORMS`, it needs the Facebook Page secrets: Threads only accepts images
   from a public link, so the card is hosted on your Page.)
   In `DRY_RUN`, run pages have a **card-previews** download (after the first full hour it includes the
   carousel slides `digest_01.jpg…`) so you can see everything before going live.
8. **X:** a one-tap link arrives in your private Telegram: tap it, X opens with the post filled in, tap Post.

Limits: up to 5 posts per run (15 s apart), 150 per day (Threads allows 250). Everything is in `newsbot/config.py`.

**Cost: $0.** Public GitHub repo (unlimited Actions minutes) + free APIs. Nothing to pay for months.

---

## Setup (about 30–40 min, once)

### Step 1 — GitHub repo
1. Create a free account at github.com.
2. New repository → name it `newsbot` → **Public** (public = unlimited free Actions minutes; your keys stay hidden in Secrets).
3. Upload all files from this zip, keeping the folders (`.github/workflows/…`, `newsbot/…`, `tests/…`, `state/`).
   - On a laptop: "Add file → Upload files" and drag the unzipped folder's contents.
   - ⚠️ `.github` is a hidden folder, and Mac/Windows often skip it when dragging. After uploading, check that
     `.github/workflows/newsbot.yml` and `.github/workflows/refresh-token.yml` exist in the repo. If not:
     "Add file → Create new file", type the name `.github/workflows/newsbot.yml`, paste the file's contents, commit.
     Do the same for `refresh-token.yml`.

### Step 2 — Threads API token (free)
1. Your Threads account must be linked to an Instagram account (it already is if you signed up via Instagram).
2. Go to **developers.facebook.com** → My Apps → **Create App** → choose the **"Access the Threads API"** use case.
3. In the app: Use cases → Threads API → **Customize** → add permissions `threads_basic` and `threads_content_publish`.
4. App roles → Roles → **Add Threads Tester** → enter your Threads username.
   Then on threads.net/instagram: Settings → Account → Website permissions → **Invites** → accept.
   (As a tester posting to your own account you don't need App Review.)
5. Use **Graph API Explorer** (or the "Generate token" button in the Threads use-case settings) to get a **user access token**
   for your Threads account.
6. Convert it to a **long-lived (60-day)** token — open this URL in a browser (replace the two values):
   ```
   https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=APP_SECRET&access_token=SHORT_TOKEN
   ```
   Copy the `access_token` from the result.
7. Get your user id:
   ```
   https://graph.threads.net/v1.0/me?fields=id,username&access_token=LONG_TOKEN
   ```

### Step 3 — Telegram bot (free)
1. In Telegram, message **@BotFather** → `/newbot` → follow prompts → copy the **bot token**.
2. Send any message (e.g. "hi") to your new bot.
3. Open `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` → find `"chat":{"id": 123456789` → that's your **chat id**.

### Step 3b — Telegram public channel (free, auto)
1. Telegram → New Channel → name **News Before Noise** → Public → link e.g. `t.me/NewsB4Noise`.
2. Channel → Administrators → Add admin → search your bot → allow **Post messages**.
3. Your channel id is `@NewsB4Noise` (the public link name with `@`).

### Step 3c — Bluesky (free, auto)
1. Sign up at bsky.app with your handle (e.g. `newsb4noise.bsky.social`).
2. Settings → Moderation → turn on the **bot** label for the account (Bluesky asks bots to label themselves).
3. Settings → Privacy and security → **App passwords** → Add → copy it (looks like `abcd-efgh-ijkl-mnop`). Never use your real password.

### Step 3d — Mastodon (free, auto, optional)
1. Pick a server that allows news bots (read its rules), sign up, and tick
   Preferences → Profile → **"This is an automated account"**.
2. Preferences → Development → New application → scope `write:statuses` → Submit → copy **Your access token**.

### Step 3e — Discord (free, auto, optional)
1. Create your own server → a `#breaking-news` channel → Edit channel → Integrations → Webhooks → New → **Copy Webhook URL**.

### Step 3f — Facebook Page + Instagram (free, auto, image cards)
Instagram's API only works for **Professional** accounts linked to a **Facebook Page**. Both are free.
1. Instagram app → Settings → Account type and tools → **Switch to professional account** (Creator or Business).
2. Create a Facebook Page **News Before Noise** (facebook.com/pages/create).
   Page settings → **Linked accounts** → Instagram → Connect your Instagram.
3. developers.facebook.com → your app (the Threads one is fine, or create a new **Business** app) → add the use
   cases **"Manage everything on your Page"** and **"Instagram API with Facebook Login"**.
4. Tools → **Graph API Explorer** → choose your app → "Get User Access Token" with these permissions:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`,
   `instagram_content_publish`, `business_management` → Generate → copy it.
5. Make it long-lived (open in a browser, replace the 3 values; App ID/secret are in App settings → Basic):
   ```
   https://graph.facebook.com/v24.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN
   ```
6. Get your **Page token** (this one never expires) and **Page id**:
   ```
   https://graph.facebook.com/v24.0/me/accounts?access_token=LONG_USER_TOKEN
   ```
   Copy your page's `access_token` → `FB_PAGE_TOKEN`, and its `id` → `FB_PAGE_ID`.
7. Get your **Instagram id**:
   ```
   https://graph.facebook.com/v24.0/FB_PAGE_ID?fields=instagram_business_account&access_token=FB_PAGE_TOKEN
   ```
   Copy `instagram_business_account.id` → `IG_USER_ID`.
8. Optional check: paste the Page token into the **Access Token Debugger**; it should say *Expires: Never*.
   (The app can stay in Development mode: you're its admin and the Page's admin.)
- Only want Instagram, not Facebook posts? Set `FACEBOOK_PUBLISH = False` in `config.py`; the card is then
  uploaded to the Page *unpublished*, only so Instagram can fetch it.

### Step 4 — Add secrets to GitHub
Repo → **Settings → Secrets and variables → Actions**.

**Secrets** tab → "New repository secret":
| Name | Value |
|---|---|
| `THREADS_ACCESS_TOKEN` | long-lived token from step 2.6 |
| `THREADS_USER_ID` | id from step 2.7 |
| `TELEGRAM_BOT_TOKEN` | from step 3.1 |
| `TELEGRAM_CHAT_ID` | from step 3.3 (private: your X one-tap links) |
| `TELEGRAM_CHANNEL_ID` | `@NewsB4Noise` (step 3b) |
| `BLUESKY_HANDLE` | e.g. `newsb4noise.bsky.social` |
| `BLUESKY_APP_PASSWORD` | app password from step 3c |
| `MASTODON_INSTANCE` | e.g. `https://yourserver.social` (optional) |
| `MASTODON_TOKEN` | from step 3d (optional) |
| `DISCORD_WEBHOOK_URL` | from step 3e (optional) |
| `FB_PAGE_ID` | from step 3f.6 (Facebook + Instagram) |
| `FB_PAGE_TOKEN` | from step 3f.6 (Facebook + Instagram) |
| `IG_USER_ID` | from step 3f.7 (Instagram) |

Skip any platform by simply not adding its secrets. The run log shows `Auto-posting to: ...`.

**Variables** tab → "New repository variable":
| Name | Value |
|---|---|
| `DRY_RUN` | `true`  ← start here: it logs what it *would* post |
| `BOT_ENABLED` | `true` |

### Step 5 — Turn it on
1. Repo → **Actions** tab → enable workflows if asked.
2. Click **newsbot → Run workflow**. The first run only saves a baseline (posts nothing).
   A branch called `state` appears: that's the bot's memory (one commit, overwritten each run). Don't delete it.
3. Let it run for a few hours with `DRY_RUN=true`. Open a run's log to see `>>> headline` lines and their sources,
   plus which feeds failed (`! feed failed`) and which platforms are on (`Auto-posting to: …`).
4. Happy with the quality? Change variable `DRY_RUN` to `false`. It's live.
5. If the "Save state" step fails with a permission error: Settings → Actions → General →
   Workflow permissions → **Read and write permissions** → Save.

---

## Daily use
- **Kill switch:** set variable `BOT_ENABLED` to `false` (works from the GitHub mobile app).
- **Weekly maintenance job:** refreshes the Threads token (messages you on Telegram; if it ever says
  "NEW token" or "FAILED", update the `THREADS_ACCESS_TOKEN` secret) and makes a tiny keep-alive commit,
  because GitHub switches off schedules in repos with no activity for 60 days.
- **Too many / too few posts?** In `config.py`: raise `MIN_SOURCES` to 4 for stricter, lower `MAX_POSTS_PER_DAY`,
  edit `MARKET_KEYWORDS` / `GEO_KEYWORDS`, or set `INCLUDE_GENERAL_NEWS = True`.
- **Only US/India?** `REQUIRE_FOCUS_COUNTRY = True`.
- **Dead feed?** The log shows `! feed failed` and `Feeds working: N/47`. Replace or delete that line in `FEEDS`.
  If fewer than a quarter of feeds work, you get a private Telegram warning (max once every 6 hours).
- **A platform failing?** The log shows the platform's own reason, e.g. `! Telegram failed: HTTP 400: chat not found`.

## Good to know
- GitHub's 5-min schedule can run a few minutes late at busy times. Official releases and price alerts are fast;
  3-source news is typically 10–30 min behind the first report. That's the price of free + accurate.
- Price data comes from Yahoo Finance's public (unofficial) endpoint; some exchanges are delayed ~15 min.
  If Yahoo changes it, price alerts stop but news keeps posting.
- Matching is keyword-based (no AI), so very differently-worded headlines about the same event may not match,
  and occasionally two related stories may. Watch the dry-run logs for a day and tune `MIN_SHARED_WORDS` / `MIN_OVERLAP`.
- Bio text is in the chat where this bot was made; every bio says posts are automated alerts. WhatsApp Channels have no API, so they can't be automated. Avoid buy/sell calls.
- **Tests run automatically** on every change you push (Actions → *tests*). A red ❌ means your last edit
  (usually `config.py`) broke something; undo it. Locally: `python3 tests/test_bot.py` and
  `python3 tests/test_scenarios.py` (19 end-to-end scenarios: full news cycle, hourly carousel, follow-ups,
  platform outages and retries, caps, dry run, kill switch…).

## Update 7 extras (all automatic, all free)

| Feature | What it posts | Where | Turn off in `config.py` |
|---|---|---|---|
| 🔴 BREAKING label | Prefix on the biggest stories (central-bank decisions, wars, ceasefires, ±2% index moves), max 10/day | All text platforms | `BREAKING_ENABLED = False` |
| 🔔 Market open/close | US open 9:35 AM ET, US close 4:05 PM ET, India open 9:20 AM IST, India close 3:35 PM IST. Skipped on holidays | All text platforms + X link | `MARKET_BELLS = []` |
| 🗓 Economic calendar | "Today's key data" at 7 AM ET on weekdays + "⏰ Coming up" ~15 min before each high-impact release (US, EU, UK, Japan, China) | All text platforms + X link | `CALENDAR_ENABLED = False` |
| 📊 Daily report | Posts per platform, errors, carousels, feeds working, at 9 PM ET | Your private Telegram chat only | `DAILY_REPORT = False` |
| 🔗 Links page | One page with all your channels for every bio: https://newsbeforenoise.github.io/newsbot/ | GitHub Pages (`docs/`) | — |

Facebook and Instagram keep only the hourly carousel; the market and calendar posts go to the live text platforms.
