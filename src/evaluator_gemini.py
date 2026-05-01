import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from src.candidate_profile import FULL_SYSTEM_PROMPT

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("CRITICAL ERROR: GEMINI_API_KEY not found.")

client = genai.Client(api_key=GEMINI_API_KEY)

# ── Model selection ───────────────────────────────────────────────────────────
# gemini-1.5-flash was deprecated — replaced with gemini-2.0-flash-lite.
# It is faster, cheaper, and supports JSON mode natively.
# Fallback: "gemini-2.0-flash" (slightly more capable, same price tier)
GEMINI_MODEL = "gemini-2.0-flash-lite"

# Gemini free tier: 30 RPM for 2.0-flash-lite → 2 s sleep is safe
_RATE_LIMIT_SLEEP = 2.0


def evaluate_job_gemini(job_snippet: str, job_title: str) -> dict | None:
    """
    Stage-1 fast triage: Is this a real individual job listing?
    Gemini 2.0 Flash-Lite handles bulk filtering cheaply.
    Returns parsed JSON dict or None on error.
    """
    prompt = (
        f"Job Title: {job_title}\n"
        f"Job Description Snippet:\n{job_snippet}"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=FULL_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )

        raw_text = response.text.strip()

        # Belt-and-suspenders JSON extraction
        start = raw_text.find("{")
        end   = raw_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw_text[start : end + 1])
        return None

    except Exception as e:
        print(f"  [GEMINI] -> Evaluation Error for '{job_title}': {e}")
        return None


def process_with_gemini(raw_jobs_list: list[dict]) -> list[dict]:
    """
    Runs bulk triage over every raw listing.
    Marks invalid / low-score jobs so downstream evaluators skip them.
    """
    qualified_jobs = []
    print(f"\n[GEMINI] Evaluating {len(raw_jobs_list)} raw jobs with {GEMINI_MODEL}...")

    for job in raw_jobs_list:
        title    = job.get("title",    "Unknown Title")
        company  = job.get("company",  "Unknown Company")
        location = job.get("location", "India")
        link     = job.get("link",     "")
        snippet  = job.get("snippet",  "")
        source   = job.get("source",   "serper")

        if not snippet:
            continue

        evaluation = evaluate_job_gemini(snippet, title)

        # Respect rate limit — 2 s between calls
        time.sleep(_RATE_LIMIT_SLEEP)

        if not evaluation:
            continue

        if not evaluation.get("is_valid"):
            reason = evaluation.get("invalid_reason", "")
            print(f"  [SKIP]  {title} | {reason or 'failed validity check'}")
            continue

        score   = evaluation.get("resume_match_score", 0)
        bracket = evaluation.get("experience_bracket", "Unknown")

        if score >= 60:
            print(f"  [GEMINI ✓] {title} @ {company} | {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":             source,
                "evaluator":          "Gemini",
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

    print(f"[GEMINI] {len(qualified_jobs)} qualified out of {len(raw_jobs_list)}.")
    return qualified_jobs