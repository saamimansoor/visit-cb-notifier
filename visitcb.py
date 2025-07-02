"""
Visit Callback Notifier
Author: Sam & ChatGPT
Purpose: Automatically log in to Visit MIS (via HTTP Basic‑Auth),
         filter for “Recall” callbacks, find any due in the next N minutes,
         and post them in Discord via webhook.
"""

from playwright.sync_api import sync_playwright
import re
import datetime
import requests
import pytz

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

USERNAME        = os.getenv("MIS_USERNAME", "visit")
PASSWORD        = os.getenv("MIS_PASSWORD", "Visit@544")
WEBHOOK_URL     = os.getenv("DISCORD_WEBHOOK")   # no default for safety
FUTURE_MIN      = int(os.getenv("FUTURE_MIN", 15))    # ahead
LOOKBACK_HRS    = int(os.getenv("LOOKBACK_HOURS", 10))  # behind

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def parse_datetime(text: str) -> datetime.datetime | None:
    """
    Given a string like "Call At June 29th 2025, 1:00 pm",
    strip the prefix, remove the "th"/"st"/etc., and return
    a timezone‑aware datetime in Asia/Kolkata.
    """
    # 1) Remove any leading label
    text = text.replace("Call At ", "").strip()

    # 2) Strip ordinal suffixes: 1st, 2nd, 3rd, 4th, etc.
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.IGNORECASE)

    # 3) Parse the cleaned text
    try:
        dt = datetime.datetime.strptime(text, "%B %d %Y, %I:%M %p")
        # Localize to IST
        return pytz.timezone("Asia/Kolkata").localize(dt)
    except Exception:
        return None

def notify_discord(message: str):
    """
    Send a POST to your Discord webhook with the given message.
    """
    requests.post(WEBHOOK_URL, json={"content": message})

# ─── MAIN FLOW ─────────────────────────────────────────────────────────────────

def run():
    upcoming, missed = [], []

    with sync_playwright() as p:
        # (login + scrape exactly as before)
        # after rows = [...]

        now   = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        soon  = now + datetime.timedelta(minutes=FUTURE_MIN)
        past  = now - datetime.timedelta(hours=LOOKBACK_HRS)

        for r in rows:
            cells     = r.query_selector_all("td")
            prop_id   = cells[1].inner_text().strip()
            remarks   = cells[13].inner_text().strip()
            sched_dt  = parse_datetime(remarks)
            if not sched_dt:
                continue
            if now <= sched_dt <= soon:                # within next N min
                upcoming.append((prop_id, remarks))
            elif past <= sched_dt < now:               # within look‑back
                missed.append((prop_id, remarks))

    # ── Discord message ───────────────────────────────
    if upcoming or missed:
        lines = [f"🔔 Callback scan ({LOOKBACK_HRS} h back, {FUTURE_MIN} min ahead)"]
        if missed:
            lines.append(f"⚠️ **{len(missed)} MISSED**:")
            lines += [f"• `{p}` – {r}" for p, r in missed]
        if upcoming:
            lines.append(f"🕒 **{len(upcoming)} due soon**:")
            lines += [f"• `{p}` – {r}" for p, r in upcoming]
        notify_discord("\n".join(lines))
        print("✅  Notification sent.")
    else:
        print("ℹ️  Nothing to report.")


if __name__ == "__main__":
    run()