from jobspy import scrape_jobs
import pandas as pd


JOBSPY_SITES = ["linkedin", "indeed"]


def fetch_jobspy_jobs(job_titles: list, locations: list, max_results: int) -> list:
    """
    Scrape LinkedIn, Indeed, Glassdoor, ZipRecruiter for each (title, location) combo.
    Returns a flat list of job dicts normalized to our schema.
    """
    results = []

    for title in job_titles:
        for location in locations:
            jobs = _scrape(title, location, max_results)
            results.extend(jobs)
            print(f"[jobspy] '{title}' in '{location}' → {len(jobs)} results")

    return results


def _scrape(title: str, location: str, max_results: int) -> list:
    try:
        df = scrape_jobs(
            site_name=JOBSPY_SITES,
            search_term=title,
            location=location,
            results_wanted=max_results,
            hours_old=24 * 30,  # last 30 days
            country_indeed="Canada",
        )
    except Exception as e:
        print(f"[jobspy] Scrape failed for '{title}' / '{location}': {e}")
        return []

    if df is None or df.empty:
        return []

    jobs = []
    for _, row in df.iterrows():
        jobs.append({
            "company": _safe(row, "company"),
            "position": _safe(row, "title"),
            "location": _safe(row, "location"),
            "apply_url": _safe(row, "job_url"),
            "date_posted": _format_date(_safe(row, "date_posted")),
            "description_snippet": _safe(row, "description")[:300] if _safe(row, "description") else "",
            "source": f"jobspy:{_safe(row, 'site')}",
        })

    return jobs


def _safe(row, col: str) -> str:
    val = row.get(col, "")
    if pd.isna(val) if val.__class__.__name__ in ("float", "NAType") else False:
        return ""
    return str(val) if val else ""


def _format_date(val: str) -> str:
    if not val or val == "nan":
        return ""
    # jobspy returns dates as strings like "2026-06-01" or datetime objects
    try:
        return str(val)[:10]
    except Exception:
        return ""