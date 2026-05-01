import os
import logging
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

# ── Actor registry ────────────────────────────────────────────────────────────
ACTORS = {
    "linkedin": "nexgendata~linkedin-jobs-scraper",
}

# ── Valid jobType values for nexgendata~linkedin-jobs-scraper ─────────────────
# The actor ONLY accepts these exact strings (validated server-side).
# Previously "FULLTIME" was used — that caused the ApifyApiError for every role.
VALID_JOB_TYPES = ("", "full-time", "part-time", "contract", "internship")
DEFAULT_JOB_TYPE = "full-time"   # empty string = no filter; "full-time" = restrict to FT

# ── Field name variants returned by different LinkedIn actor versions ─────────
FIELD_VARIANTS = {
    "title":       ["job_title", "title", "jobTitle", "position"],
    "company":     ["company_name", "company", "companyName", "employer"],
    "location":    ["location", "jobLocation", "city", "place"],
    "url":         ["URL", "url", "jobUrl", "applyUrl", "link", "jobLink"],
    "description": ["description", "jobDescription", "details", "body"],
    "salary":      ["salary", "salaryRange", "compensation", "pay"],
    "job_type":    ["job_type", "jobType", "employmentType", "type"],
    "posted_date": ["posted_date", "date", "postedAt", "datePosted", "publishedAt"],
    "experience":  ["experienceLevel", "experience", "seniority", "level"],
}


def _get_field(item: dict, field_key: str, default: str = "") -> str:
    """Try multiple field name variants and return first non-empty value."""
    for variant in FIELD_VARIANTS.get(field_key, [field_key]):
        val = item.get(variant)
        if val and str(val).strip():
            return str(val).strip()
    return default


def _build_snippet(item: dict) -> str:
    """
    Build a rich snippet from LinkedIn job data for the evaluator.
    Includes description (capped), experience level, salary, type, and posted date.
    """
    parts = []

    desc = _get_field(item, "description")
    if desc:
        parts.append(desc[:700])

    exp = _get_field(item, "experience")
    if exp:
        parts.append(f"Experience Level: {exp}")

    salary = _get_field(item, "salary")
    if salary:
        parts.append(f"Salary: {salary}")

    job_type = _get_field(item, "job_type")
    if job_type:
        parts.append(f"Type: {job_type}")

    posted = _get_field(item, "posted_date")
    if posted:
        parts.append(f"Posted: {posted}")

    return " | ".join(parts) if parts else ""


def _safe_job_type(job_type: str) -> str:
    """
    Coerce any jobType value to one the actor actually accepts.
    Logs a warning and falls back to empty string (= no filter) if invalid.
    """
    normalized = job_type.lower().strip()
    if normalized in VALID_JOB_TYPES:
        return normalized
    logger.warning(
        "Invalid jobType '%s' — falling back to '' (no filter). "
        "Valid values: %s", job_type, VALID_JOB_TYPES
    )
    return ""


def extract_jobs_apify(
    target_roles: list[str],
    location: str = "India",
    max_results: int = 50,
    job_type: str = DEFAULT_JOB_TYPE,
) -> list[dict]:
    """
    Calls Apify LinkedIn Jobs Actor for each role.
    Returns list of raw job dicts matching pipeline schema:
      {title, company, location, link, snippet, source}

    Args:
        target_roles : list of role search strings
        location     : geographic filter passed to LinkedIn
        max_results  : max listings per role (actor-level cap)
        job_type     : one of "", "full-time", "part-time", "contract", "internship"
                       Any other value is silently coerced to "" (no filter).
    """
    raw_jobs = []
    safe_type = _safe_job_type(job_type)

    for role in target_roles:
        print(f"--- [APIFY] LinkedIn search: '{role}' in {location} ---")

        actor_input = {
            "keywords":   role,
            "location":   location,
            "datePosted": "week",       # last 7 days — aligns with Serper tbs=qdr:w
            "jobType":    safe_type,    # FIX: was "FULLTIME" — now lowercase "full-time"
            "maxResults": max_results,
            # Uncomment to pre-filter by seniority on the LinkedIn side:
            # "experienceLevel": "entry level",
        }

        try:
            run = client.actor(ACTORS["linkedin"]).call(run_input=actor_input)

            if run is None:
                print(f"  [APIFY] Actor run returned None for: '{role}' — skipping")
                continue

            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                print(f"  [APIFY] No dataset ID returned for: '{role}' — skipping")
                continue

            items = list(client.dataset(dataset_id).iterate_items())
            print(f"  -> [APIFY] {len(items)} raw listings for '{role}'")

            for item in items:
                title   = _get_field(item, "title")
                company = _get_field(item, "company", "Unknown")
                loc     = _get_field(item, "location", location)
                link    = _get_field(item, "url")
                snippet = _build_snippet(item)

                if not title and not snippet:
                    continue

                raw_jobs.append({
                    "title":    title,
                    "company":  company,
                    "location": loc,
                    "link":     link,
                    "snippet":  snippet,
                    "source":   "LinkedIn (Apify)",
                })

        except Exception as e:
            print(f"  [APIFY] Error for '{role}': {e}")
            logger.exception(f"Apify actor failed for role: {role}")

    print(f"\n[APIFY] Total LinkedIn listings collected: {len(raw_jobs)}")
    return raw_jobs