import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")


def _parse_company_from_snippet(snippet: str, title: str) -> str:
    """
    Attempt to extract company name from the snippet text.
    Serper doesn't return company directly — it's often embedded in the snippet
    e.g. "Accenture · 3 days ago" or "TCS — Mumbai, India"
    """
    if not snippet:
        return "Unknown"

    # Common patterns: "Company · N days ago" or "Company — Location"
    for separator in [" · ", " - ", " — ", " | "]:
        if separator in snippet:
            candidate = snippet.split(separator)[0].strip()
            # Sanity check: company name shouldn't be too long
            if candidate and len(candidate) < 60 and len(candidate) > 1:
                return candidate

    return "Unknown"


def _parse_location_from_snippet(snippet: str, fallback: str) -> str:
    """
    Try to extract city/location from snippet.
    e.g. "Bengaluru, Karnataka · 2 days ago"
    """
    if not snippet:
        return fallback

    # Look for Indian city names commonly appearing in job snippets
    indian_cities = [
        "Bengaluru", "Bangalore", "Mumbai", "Delhi", "Hyderabad",
        "Chennai", "Pune", "Noida", "Gurugram", "Gurgaon",
        "Kolkata", "Ahmedabad", "Coimbatore", "Jaipur", "Indore",
    ]
    snippet_lower = snippet.lower()
    for city in indian_cities:
        if city.lower() in snippet_lower:
            return city

    return fallback


def extract_raw_jobs(
    target_roles: list[str],
    location: str = "India",
    pages_per_role: int = 2,
) -> list[dict]:
    """
    Thread-safe extractor. Pulls Data Analyst / BI job listings from
    Google Search via Serper API with a strict 7-day recency filter.

    Returns list of dicts with schema:
      {title, company, location, link, snippet, source}
    """
    raw_jobs = []
    url = "https://google.serper.dev/search"

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    for role in target_roles:
        print(f"--- [SERPER] Searching: '{role}' in {location} ---")

        for page in range(pages_per_role):
            print(f"  Page {page + 1}...")

            # Use Google Jobs vertical when available, fallback to organic
            payload = json.dumps({
                "q": f"{role} jobs {location}",
                "page": page + 1,
                "tbs": "qdr:w",        # strict 7-day filter
                "num": 10,             # max results per page
                "gl": "in",            # geo: India
                "hl": "en",
            })

            try:
                response = requests.post(url, headers=headers, data=payload, timeout=15)
                response.raise_for_status()
                data = response.json()

                # Pull from both 'jobs' (Google Jobs cards) and 'organic' (regular results)
                jobs_cards  = data.get("jobs", [])
                organic     = data.get("organic", [])

                # ── Google Jobs cards (richer data) ──────────────────
                for job in jobs_cards:
                    snippet = job.get("description", "") or job.get("snippet", "")
                    raw_jobs.append({
                        "title":    job.get("title", ""),
                        "company":  job.get("company", "Unknown"),
                        "location": job.get("location", location),
                        "link":     job.get("link", ""),
                        "snippet":  snippet[:800],
                        "source":   "serper_jobs",
                    })

                # ── Organic results (fallback, less structured) ───────
                for job in organic:
                    snippet  = job.get("snippet", "")
                    company  = _parse_company_from_snippet(snippet, job.get("title", ""))
                    loc      = _parse_location_from_snippet(snippet, location)
                    raw_jobs.append({
                        "title":    job.get("title", ""),
                        "company":  company,
                        "location": loc,
                        "link":     job.get("link", ""),
                        "snippet":  snippet,
                        "source":   "serper_organic",
                    })

                print(f"  -> {len(jobs_cards)} job cards + {len(organic)} organic results")

            except requests.exceptions.Timeout:
                print(f"  -> [TIMEOUT] Serper timed out for '{role}' page {page + 1}")
            except Exception as e:
                print(f"  -> [ERROR] '{role}' page {page + 1}: {e}")

    print(f"\n[SERPER] Total raw listings collected: {len(raw_jobs)}")
    return raw_jobs