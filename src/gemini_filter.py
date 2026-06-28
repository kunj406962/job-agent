import os
import json
import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def filter_with_gemini(jobs: list) -> list:
    """
    Send job titles + companies to Gemini in one batch.
    Returns only the jobs Gemini thinks are relevant software internships / entry-level roles.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[gemini] Skipping — GEMINI_API_KEY not set.")
        return jobs

    if not jobs:
        return jobs

    # Build a numbered list for Gemini to respond to
    lines = []
    for i, job in enumerate(jobs):
        lines.append(f"{i}: {job.get('company', '')} — {job.get('position', '')}")
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
        resp.raise_for_status()
        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[gemini] API call failed: {e} — skipping filter, keeping all jobs.")
        return jobs

    # Parse the indices Gemini returned
    try:
        indices = {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
    except Exception:
        print(f"[gemini] Could not parse response: '{raw}' — keeping all jobs.")
        return jobs

    kept = [job for i, job in enumerate(jobs) if i in indices]
    dropped = len(jobs) - len(kept)
    print(f"[gemini] Kept {len(kept)}, dropped {dropped} irrelevant jobs.")
    return kept