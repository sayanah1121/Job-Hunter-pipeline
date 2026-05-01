

import os
import json
import time
from mistralai.client.sdk import Mistral
from dotenv import load_dotenv
from src.candidate_profile import FULL_SYSTEM_PROMPT

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("CRITICAL ERROR: MISTRAL_API_KEY not found. Add it to your .env file.")

client = Mistral(api_key=MISTRAL_API_KEY)

# ── Model selection ───────────────────────────────────────────────────────────
# mistral-small-latest → fast, free-tier, strong at instruction following.
# Upgrade to "mistral-medium-latest" for higher accuracy if you have paid credits.
MISTRAL_MODEL  = "mistral-small-latest"
_SLEEP_BETWEEN = 1.1   # free tier: 1 req/s → 1.1 s gives a comfortable buffer


def evaluate_job_mistral(job_snippet: str, job_title: str) -> dict | None:
    """
    Cross-validates borderline scores from Groq.
    Returns parsed JSON evaluation dict, or None on error.
    """
    try:
        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": FULL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Job Title: {job_title}\nJob Description Snippet:\n{job_snippet}",
                },
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content.strip()

        # Defensive JSON extraction
        start = raw_text.find("{")
        end   = raw_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw_text[start : end + 1])
        return None

    except Exception as e:
        print(f"  [MISTRAL] -> Evaluation Error for '{job_title}': {e}")
        return None


def process_with_mistral(raw_jobs_list: list[dict]) -> list[dict]:
    """
    Runs Mistral evaluation over a list of raw job dicts.
    Intended use: cross-validate borderline candidates from Groq,
    or run as a standalone parallel evaluator.
    """
    qualified_jobs = []
    print(f"\n[MISTRAL] Evaluating {len(raw_jobs_list)} jobs with {MISTRAL_MODEL}...")

    for job in raw_jobs_list:
        title    = job.get("title",    "Unknown Title")
        company  = job.get("company",  "Unknown Company")
        location = job.get("location", "India")
        link     = job.get("link",     "")
        snippet  = job.get("snippet",  "")
        source   = job.get("source",   "serper")

        if not snippet:
            continue

        evaluation = evaluate_job_mistral(snippet, title)
        time.sleep(_SLEEP_BETWEEN)

        if not evaluation:
            continue

        if not evaluation.get("is_valid"):
            reason = evaluation.get("invalid_reason", "")
            print(f"  [SKIP]  {title} | {reason or 'failed validity check'}")
            continue

        score   = evaluation.get("resume_match_score", 0)
        bracket = evaluation.get("experience_bracket", "Unknown")

        if score >= 60:
            print(f"  [MISTRAL ✓] {title} @ {company} | {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":             source,
                "evaluator":          "Mistral",
                "job_title":          title,
                "company_name":       company,
                "location":           location,
                "experience_bracket": bracket,
                "resume_match_score": score,
                "matched_skills":     evaluation.get("matched_skills", ""),
                "missing_skills":     evaluation.get("missing_skills", ""),
                "application_link":   link,
            })
        else:
            print(f"  [LOW]   {title} @ {company} | Score: {score}")

    print(f"[MISTRAL] {len(qualified_jobs)} qualified out of {len(raw_jobs_list)}.")
    return qualified_jobs