import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlencode, parse_qs


def normalize_url(url: str) -> str:
    """Strip tracking params and normalize a URL to its core form."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        # Remove common tracking params
        STRIP_PARAMS = {
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
            "ref", "referer", "source", "src", "tracking", "trk", "trkInfo",
        }
        qs = parse_qs(parsed.query, keep_blank_values=False)
        filtered = {k: v for k, v in qs.items() if k.lower() not in STRIP_PARAMS}
        clean_query = urlencode(sorted(filtered.items()), doseq=True)
        clean = parsed._replace(query=clean_query, fragment="")
        return clean.geturl().rstrip("/").lower()
    except Exception:
        return url.strip().lower()


def make_id(url: str) -> str:
    """SHA-256 hash of the normalized URL. Used for deduplication."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


def filter_jobs(jobs: list, config: dict) -> list:
    required = [k.lower() for k in config.get("keywords_required", [])]
    excluded = [k.lower() for k in config.get("keywords_excluded", [])]
    max_age = config.get("max_age_days", 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)

    kept = []
    for job in jobs:
        title = job.get("position", "").lower()
        desc = job.get("description_snippet", "").lower()
        combined = title + " " + desc

        if required and not any(kw in combined for kw in required):
            continue

        if any(kw in title for kw in excluded):
            continue

        date_posted = job.get("date_posted", "")
        if date_posted:
            try:
                posted_dt = datetime.strptime(date_posted, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if posted_dt < cutoff:
                    continue
            except ValueError:
                pass

        kept.append(job)

    return kept


def deduplicate(jobs: list, existing_ids: set) -> list:
    """
    Deduplicate by normalized URL only.
    Also deduplicates within the current batch.
    """
    seen = set(existing_ids)
    unique = []

    for job in jobs:
        job_id = make_id(job.get("apply_url", ""))
        if job_id not in seen:
            job["id"] = job_id
            unique.append(job)
            seen.add(job_id)

    return unique