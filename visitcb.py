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

USERNAME        = "visit"   # ← your MIS username
PASSWORD        = "Visit@544"  # ← your MIS password
WEBHOOK_URL     = "https://discord.com/api/webhooks/1388781763010236496/4kOKN_MpiFSj2Y8YtfD3rYbIlYe6LHOpP68insbRvgWFVms5gigJ_Jot5X9zk2XqGvEn"
TIME_WINDOW_MIN = 15        # how many minutes ahead you want to be warned

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
    due_list = []

    with sync_playwright() as p:	
        print("▶️  Launching browser and logging in...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            http_credentials={"username": USERNAME, "password": PASSWORD}
        )
        page = context.new_page()
        page.goto("https://mer.getvisitapp.com/mchi/mis/view-internal")
        page.wait_for_selector('select:has-text("Filter by status")')

        print("▶️  Applying Recall filter...")
        page.select_option('select', label="Recall")
        page.click('button:has-text("Apply Filter")')
        page.wait_for_selector("table tbody tr")

        rows = page.query_selector_all("table tbody tr")
        print(f"🔍  Found {len(rows)} rows in the table.")

        now     = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        horizon = now + datetime.timedelta(minutes=TIME_WINDOW_MIN)

        for r in rows:
            cells     = r.query_selector_all("td")
            proposal  = cells[1].inner_text().strip()
            remarks   = cells[13].inner_text().strip()
            sched_dt  = parse_datetime(remarks)
            if sched_dt and now <= sched_dt <= horizon:
                due_list.append((proposal, remarks, sched_dt.strftime("%d/%m %I:%M %p")))

        browser.close()

    print(f"✅  Done scraping. {len(due_list)} callback(s) due in next {TIME_WINDOW_MIN} min.")

    if due_list:
        print("📨  Sending to Discord…")
        header = f"🔔 **{len(due_list)} callback(s) due in {TIME_WINDOW_MIN} min:**"
        lines  = [header]
        for prop, rem, when in due_list:
            lines.append(f"• Proposal `{prop}` –  {rem}")
        notify_discord("\n".join(lines))
        print("✅  Notification sent.")
    else:
        print("ℹ️  No due callbacks found — nothing sent.")


if __name__ == "__main__":
    run()
