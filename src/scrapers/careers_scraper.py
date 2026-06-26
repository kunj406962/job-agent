import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 10


def fetch_careers_jobs(companies: list, keywords_required: list) -> list:
    """
    Scrape each company's careers URL.
    Returns a flat list of job dicts normalized to our schema.
    """
    results = []

    for company in companies:
        name = company.get("name", "")
        url = company.get("careers_url", "")
        if not url:
            continue

        jobs = _scrape_company(name, url, keywords_required)
        results.extend(jobs)
        print(f"[careers] {name} → {len(jobs)} results")

    return results


def _scrape_company(company_name: str, url: str, keywords: list) -> list:
    ats = _detect_ats(url)

    try:
        if ats == "lever":
            return _scrape_lever(company_name, url, keywords)
        elif ats == "greenhouse":
            return _scrape_greenhouse(company_name, url, keywords)
        elif ats == "workday":
            return _scrape_workday(company_name, url, keywords)
        else:
            return _scrape_generic(company_name, url, keywords)
    except Exception as e:
        print(f"[careers] {company_name} failed: {e}")
        return []


def _detect_ats(url: str) -> str:
    if "lever.co" in url:
        return "lever"
    if "greenhouse.io" in url or "boards.greenhouse" in url:
        return "greenhouse"
    if "myworkdayjobs.com" in url or "wd3.myworkdayjobs" in url or "wd5.myworkdayjobs" in url:
        return "workday"
    return "generic"


# --- Lever ---
def _scrape_lever(company_name: str, url: str, keywords: list) -> list:
    # Lever has a JSON API at the same base URL + .json
    json_url = url.split("?")[0].rstrip("/") + "?mode=json"
    try:
        resp = requests.get(json_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return _scrape_generic(company_name, url, keywords)

    jobs = []
    for posting in data:
        title = posting.get("text", "")
        if not _matches_keywords(title, "", keywords):
            continue
        jobs.append({
            "company": company_name,
            "position": title,
            "location": posting.get("categories", {}).get("location", ""),
            "apply_url": posting.get("hostedUrl", url),
            "date_posted": "",
            "description_snippet": BeautifulSoup(
                posting.get("descriptionPlain", "")[:300], "html.parser"
            ).get_text()[:300],
            "source": "careers:lever",
        })

    return jobs


# --- Greenhouse ---
def _scrape_greenhouse(company_name: str, url: str, keywords: list) -> list:
    # Extract the board token from the URL
    # e.g. https://boards.greenhouse.io/acme/jobs
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    board_token = parts[0] if parts else ""

    if not board_token:
        return _scrape_generic(company_name, url, keywords)

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return _scrape_generic(company_name, url, keywords)

    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        location = job.get("location", {}).get("name", "")
        if not _matches_keywords(title, "", keywords):
            continue
        jobs.append({
            "company": company_name,
            "position": title,
            "location": location,
            "apply_url": job.get("absolute_url", url),
            "date_posted": job.get("updated_at", "")[:10],
            "description_snippet": "",
            "source": "careers:greenhouse",
        })

    return jobs


# --- Workday ---
def _scrape_workday(company_name: str, url: str, keywords: list) -> list:
    # Workday pages are JS-heavy — we do a best-effort HTML parse
    return _scrape_generic(company_name, url, keywords)


# --- Generic HTML fallback ---
def _scrape_generic(company_name: str, url: str, keywords: list) -> list:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"[careers] {company_name} HTTP error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    jobs = []
    # Look for anchor tags whose text contains a keyword
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if not _matches_keywords(text, "", keywords):
            continue

        href = a["href"]
        if not href.startswith("http"):
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            href = base + ("" if href.startswith("/") else "/") + href

        jobs.append({
            "company": company_name,
            "position": text[:120],
            "location": "",
            "apply_url": href,
            "date_posted": "",
            "description_snippet": "",
            "source": "careers:generic",
        })

    # Deduplicate by URL within this company
    seen = set()
    unique = []
    for job in jobs:
        if job["apply_url"] not in seen:
            seen.add(job["apply_url"])
            unique.append(job)

    return unique


def _matches_keywords(title: str, desc: str, keywords: list) -> bool:
    combined = (title + " " + desc).lower()
    return any(kw.lower() in combined for kw in keywords)