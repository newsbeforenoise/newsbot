"""
Keeps the Threads token alive (long-lived tokens last 60 days).
Runs weekly from GitHub Actions and messages you on Telegram with the result.
If Meta returns a DIFFERENT token string, Telegram tells you to paste it into
the THREADS_ACCESS_TOKEN secret.
"""
import json
import os
import urllib.parse
import sys
import urllib.request

token = (os.environ.get("THREADS_ACCESS_TOKEN") or "").strip()
if not token:
    print("No Threads token set - nothing to refresh.")
    sys.exit(0)
url = "https://graph.threads.net/refresh_access_token?" + urllib.parse.urlencode(
    {"grant_type": "th_refresh_token", "access_token": token})

try:
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read())
    days = int(data.get("expires_in", 0)) // 86400
    if data.get("access_token") and data["access_token"] != token:
        msg = ("Threads token refreshed, but Meta issued a NEW token. Update the GitHub secret "
               f"THREADS_ACCESS_TOKEN with:\n\n{data['access_token']}\n\nValid ~{days} days.")
    else:
        msg = f"✅ Threads token refreshed. Valid ~{days} more days."
except Exception as e:  # noqa: BLE001
    msg = f"⚠️ Threads token refresh FAILED: {e}\nGenerate a new long-lived token (see README step 2)."

print(msg if "NEW token" not in msg else "New token issued - sent to Telegram.")
bot, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
if bot and chat:
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{bot}/sendMessage",
        data=urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()), timeout=30)
