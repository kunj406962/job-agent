import os
import requests
from pathlib import Path

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
XLSX_PATH = Path(__file__).parent.parent / "data" / "jobs.xlsx"


def notify(new_jobs: list) -> None:
    """Upload jobs.xlsx to Discord with a summary message."""
    if not WEBHOOK_URL:
        print("[discord] Skipping — DISCORD_WEBHOOK_URL not set.")
        return

    if not new_jobs:
        print("[discord] No new jobs — skipping notification.")
        return

    if not XLSX_PATH.exists():
        print("[discord] jobs.xlsx not found — skipping notification.")
        return

    count = len(new_jobs)
    message = (
        f"🆕 **{count} new internship{'s' if count != 1 else ''} found!**\n"
        f"Green rows are new this run. Open the file to review and apply."
    )

    try:
        with open(XLSX_PATH, "rb") as f:
            resp = requests.post(
                WEBHOOK_URL,
                data={"content": message},
                files={"file": ("jobs.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                timeout=30,
            )
        resp.raise_for_status()
        print(f"[discord] Uploaded jobs.xlsx ({count} new jobs)")
    except Exception as e:
        print(f"[discord] Failed to send: {e}")