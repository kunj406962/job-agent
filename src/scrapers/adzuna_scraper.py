import os
import requests
from datetime import datetime, timezone


ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/ca/search/1"


def fetch_adzuna_jobs(job_titles: list, locations: list, max_results: int) -> list:
    """
    Query Adzuna for each (title, location) combo.
    Returns a flat list of job dicts normalized to our schema.
    """
    app_id = os.environ.get("ADZUNA_APP_ID")
    api_key = os.environ.get("ADZUNA_API_KEY")

    if not app_id or not api_key:
        print("[adzuna] Skipping — ADZUNA_APP_ID or ADZUNA_API_KEY not set.")
        return []

    results = []

    for title in job_titles:
        for location in locations:
            jobs = _query(app_id, api_key, title, location, max_results)
            results.extend(jobs)
            print(f"[adzuna] '{title}' in '{location}' → {len(jobs)} results")

    return results


def _query(app_id: str, api_key: str, title: str, location: str, max_results: int) -> list:
    params = {
        "app_id": app_id,
        "app_key": api_key,
        "what": title,
        "where": location,
        "results_per_page": min(max_results, 50),  # Adzuna max per page is 50
        "content-type": "application/json",
    }

    try:
        response = requests.get(ADZUNA_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[adzuna] Request failed for '{title}' / '{location}': {e}")
        return []

    jobs = []
    for item in data.get("results", []):
        jobs.append({
            "company": item.get("company", {}).get("display_name", ""),
            "position": item.get("title", ""),
            "location": item.get("location", {}).get("display_name", location),
            "apply_url": item.get("redirect_url", ""),
            "date_posted": _parse_date(item.get("created")),
            "description_snippet": item.get("description", "")[:300],
            "source": "adzuna",
        })

    return jobs


def _parse_date(date_str: str | None) -> str:
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str