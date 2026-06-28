import os
import time
import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
BATCH_SIZE = 50
RETRY_DELAY = 10  # seconds to wait on rate limit before retrying


def filter_with_gemini(jobs: list) -> list:
    """
    Filter jobs through Gemini in batches of BATCH_SIZE.
    Waits for each response before sending the next batch.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[gemini] Skipping — GEMINI_API_KEY not set.")
        return jobs

    if not jobs:
        return jobs

    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
    print(f"[gemini] Processing {len(jobs)} jobs in {len(batches)} batches of {BATCH_SIZE}...")

    kept = []
    total_dropped = 0

    for batch_num, batch in enumerate(batches, start=1):
        print(f"[gemini] Batch {batch_num}/{len(batches)}...", end=" ", flush=True)
        result = _filter_batch(batch, api_key)
        kept.extend(result)
        dropped = len(batch) - len(result)
        total_dropped += dropped
        print(f"kept {len(result)}, dropped {dropped}")

        # Small pause between batches to avoid rate limiting
        if batch_num < len(batches):
            time.sleep(2)

    print(f"[gemini] Done. Kept {len(kept)}, dropped {total_dropped} irrelevant jobs.")
    return kept


def _filter_batch(batch: list, api_key: str, attempt: int = 1) -> list:
    """Send one batch to Gemini. Retries once on 429."""
    lines = [f"{i}: {job.get('company', '')} — {job.get('position', '')}" for i, job in enumerate(batch)]
    job_list = "\n".join(lines)

    prompt = f"""You are filtering job postings for a computer science student looking for software internships or entry-level roles in Canada.

Return ONLY the index numbers (comma-separated) of jobs that match ALL of these criteria:
- Software/tech role (software engineer, developer, data engineer, devops, mobile, frontend, backend, full stack, ML, etc.)
- Internship, co-op, student, or new grad / entry-level position
- NOT senior, staff, lead, principal, manager, director, or requiring 3+ years experience
- NOT from unrelated fields (petroleum, mechanical, civil, electrical hardware, finance, HR, marketing, etc.)

Job list:
{job_list}

Respond with ONLY a comma-separated list of index numbers to KEEP. Nothing else. Example: 0,2,5,7"""

    try:
        resp = requests.post(
            f"{GEMINI_API_URL}?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )

        if resp.status_code == 429 and attempt == 1:
            print(f"rate limited, waiting {RETRY_DELAY}s...", end=" ", flush=True)
            time.sleep(RETRY_DELAY)
            return _filter_batch(batch, api_key, attempt=2)

        resp.raise_for_status()
        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    except Exception as e:
        print(f"\n[gemini] Batch failed: {e} — keeping all {len(batch)} jobs in this batch.")
        return batch

    try:
        indices = {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
        return [job for i, job in enumerate(batch) if i in indices]
    except Exception:
        print(f"\n[gemini] Could not parse response: '{raw}' — keeping all jobs in this batch.")
        return batch