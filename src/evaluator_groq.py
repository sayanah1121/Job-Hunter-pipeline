import os
import json
import time
from groq import Groq
from dotenv import load_dotenv
from src.candidate_profile import FULL_SYSTEM_PROMPT

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("CRITICAL ERROR: GROQ_API_KEY not found.")

client = Groq(api_key=GROQ_API_KEY)

# ── Model selection ───────────────────────────────────────────────────────────
# llama-3.1-8b-instant → replaced with llama-3.3-70b-versatile.
# The 8b model was too small for nuanced rubric scoring — it passed borderline
# jobs too easily (many score-70 false positives in the logs).
# 70b is still free on Groq and ~3× more accurate on structured evaluation tasks.
# RPM limit on free tier: 30 → we add a small sleep between calls.
GROQ_MODEL     = "llama-3.3-70b-versatile"
_SLEEP_BETWEEN = 2.1   # seconds — keeps us under 30 RPM comfortably


def evaluate_job_groq(job_snippet: str, job_title: str) -> dict | None:
    """
    Stage-2 skills & experience evaluator.
    Llama 3.3 70B is used here because it follows the multi-rule scoring rubric
    reliably and returns clean JSON.
    """
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": FULL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Job Title: {job_title}\nJob Description Snippet:\n{job_snippet}",
                },
            ],
            model=GROQ_MODEL,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content
        return json.loads(raw_text)

    except Exception as e:
        print(f"  [GROQ] -> Evaluation Error for '{job_title}': {e}")
        return None


def process_with_groq(raw_jobs_list: list[dict]) -> list[dict]:
    """
    Evaluates jobs that passed Stage-1 (Gemini triage).
    Focuses on accurate skills matching and experience-bracket assignment.
    """
    qualified_jobs = []
    print(f"\n[GROQ] Evaluating {len(raw_jobs_list)} raw jobs with {GROQ_MODEL}...")

    for job in raw_jobs_list:
        title    = job.get("title",    "Unknown Title")
        company  = job.get("company",  "Unknown Company")
        location = job.get("location", "India")
        link     = job.get("link",     "")
        snippet  = job.get("snippet",  "")
        source   = job.get("source",   "serper")

        if not snippet:
            continue

        evaluation = evaluate_job_groq(snippet, title)
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
            print(f"  [GROQ ✓] {title} @ {company} | {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":             source,
                "evaluator":          "Groq",
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

    print(f"[GROQ] {len(qualified_jobs)} qualified out of {len(raw_jobs_list)}.")
    return qualified_jobs