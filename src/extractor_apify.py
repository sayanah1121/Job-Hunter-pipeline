import os
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

# Actor IDs for different job portals on Apify
ACTORS = {
    "linkedin": "nexgendata~linkedin-jobs-scraper",
    "indeed":   "misceres~indeed-scraper",          # optional, add later
}

def extract_jobs_apify(target_roles: list[str], location: str = "India", max_results: int = 50) -> list[dict]:
    """
    Calls Apify LinkedIn Jobs Actor for each role and returns
    a list of raw job dicts in the same schema your pipeline expects:
    {title, company, location, link, snippet}
    """
    raw_jobs = []

    for role in target_roles:
        print(f"--- [APIFY] Searching LinkedIn for: {role} ---")

        actor_input = {
            "keywords":   role,
            "location":   location,
            "datePosted": "week",       # last 7 days — matches your tbs=qdr:w logic
            "jobType":    "FULLTIME",
            "maxResults": max_results,
        }

        try:
            run = client.actor(ACTORS["linkedin"]).call(run_input=actor_input)

            if run is None:
                print(f"  [APIFY] Actor run failed for: {role}")
                continue

            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            print(f"  -> [APIFY] Found {len(items)} raw listings for '{role}'")

            for item in items:
                raw_jobs.append({
                    "title":    item.get("job_title") or item.get("title", ""),
                    "company":  item.get("company_name") or item.get("company", "Unknown"),
                    "location": item.get("location", location),
                    "link":     item.get("URL") or item.get("url", ""),
                    # Build a snippet from available fields for the evaluator
                    "snippet":  _build_snippet(item),
                })

        except Exception as e:
            print(f"  [APIFY] Error for role '{role}': {e}")

    return raw_jobs


def _build_snippet(item: dict) -> str:
    """
    Apify returns richer data than Serper snippets.
    Concatenate key fields so Claude's evaluator has enough context.
    """
    parts = []

    if item.get("description"):
        parts.append(item["description"][:600])   # cap to keep tokens low
    if item.get("salary"):
        parts.append(f"Salary: {item['salary']}")
    if item.get("job_type"):
        parts.append(f"Type: {item['job_type']}")
    if item.get("posted_date") or item.get("date"):
        parts.append(f"Posted: {item.get('posted_date') or item.get('date')}")

    return " | ".join(parts) if parts else ""