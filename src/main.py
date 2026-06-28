import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import yaml
from scrapers.adzuna_scraper import fetch_adzuna_jobs
from scrapers.jobspy_scraper import fetch_jobspy_jobs
from scrapers.careers_scraper import fetch_careers_jobs
from processor import filter_jobs, deduplicate
from gemini_filter import filter_with_gemini
from excel_writer import load_existing_ids, write_jobs
from discord_notifier import notify


def load_config():
    config_path = Path(__file__).parent.parent / "config" / "search_config.yml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_companies():
    companies_path = Path(__file__).parent.parent / "config" / "companies.yml"
    with open(companies_path, "r") as f:
        return yaml.safe_load(f)["companies"]


def main():
    print("=== Job Search Agent ===")
    config = load_config()
    companies = load_companies()

    job_titles = config["job_titles"]
    locations = config["locations"]
    max_results = config.get("max_results_per_source", 50)
    keywords_required = config.get("keywords_required", [])

    all_raw = []

    # --- Layer 1: Adzuna ---
    print("\n[1/3] Fetching from Adzuna...")
    adzuna_jobs = fetch_adzuna_jobs(job_titles, locations, max_results)
    print(f"[1/3] Adzuna total: {len(adzuna_jobs)}")
    all_raw.extend(adzuna_jobs)

    # --- Layer 2: jobspy (LinkedIn, Indeed) ---
    print("\n[2/3] Fetching from jobspy...")
    jobspy_jobs = fetch_jobspy_jobs(job_titles, locations, max_results)
    print(f"[2/3] jobspy total: {len(jobspy_jobs)}")
    all_raw.extend(jobspy_jobs)

    # --- Layer 3: Direct careers pages ---
    print("\n[3/3] Scraping careers pages...")
    careers_jobs = fetch_careers_jobs(companies, keywords_required)
    print(f"[3/3] Careers pages total: {len(careers_jobs)}")
    all_raw.extend(careers_jobs)

    # --- Keyword + date filter ---
    print(f"\n[filter] Raw total: {len(all_raw)}")
    filtered = filter_jobs(all_raw, config)
    print(f"[filter] After keyword/date filter: {len(filtered)}")

    # --- Gemini filter ---
    print(f"\n[gemini] Sending {len(filtered)} jobs to Gemini for relevance check...")
    filtered = filter_with_gemini(filtered)

    # --- Dedup ---
    existing_ids = load_existing_ids()
    print(f"\n[dedup] Existing jobs in Excel: {len(existing_ids)}")
    new_jobs = deduplicate(filtered, existing_ids)
    print(f"[dedup] New jobs after dedup: {len(new_jobs)}")

    # --- Write ---
    written = write_jobs(new_jobs)
    print(f"\n=== Done. {written} new rows added to data/jobs.xlsx ===")

    # --- Discord ---
    notify(new_jobs)


if __name__ == "__main__":
    main()