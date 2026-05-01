"""
evaluator_github.py
────────────────────
Stage-2b evaluator using GitHub Models (GPT-4o-mini via Azure inference endpoint).

WHY GPT-4o-MINI HERE:
  • Free with a GitHub account (5k requests/day, no credit card).
  • GPT-4o-mini follows JSON schemas very reliably — almost zero malformed
    responses in practice.
  • Used as a parallel Stage-2 evaluator alongside Groq, so the final shortlist
    has been independently validated by two different model families.
  • After deduplication, jobs confirmed by both Groq AND GitHub are flagged
    with multiple evaluators — a strong signal for the candidate to prioritise.

SETUP:
  Add to .env:  GH_MODELS_API_KEY=<your GitHub Personal Access Token>
  The PAT needs no special scopes — just "public repositories" is sufficient.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from src.candidate_profile import FULL_SYSTEM_PROMPT

load_dotenv()

GITHUB_AI_TOKEN = os.getenv("GH_MODELS_API_KEY")
if not GITHUB_AI_TOKEN:
    raise ValueError("CRITICAL ERROR: GH_MODELS_API_KEY not found.")

client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_AI_TOKEN,
)

GITHUB_MODEL = "gpt-4o-mini"


def evaluate_job_github(job_snippet: str, job_title: str) -> dict | None:
    """
    Parallel Stage-2 evaluator.
    GPT-4o-mini is reliable on the strict JSON schema and rarely hallucinates
    experience brackets or skill labels.
    Returns parsed JSON dict or None on error.
    """
    try:
        response = client.chat.completions.create(
            model=GITHUB_MODEL,
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

        # Defensive extraction
        start = raw_text.find("{")
        end   = raw_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw_text[start : end + 1])
        return None

    except Exception as e:
        print(f"  [GITHUB] -> Evaluation Error for '{job_title}': {e}")
        return None


def process_with_github(raw_jobs_list: list[dict]) -> list[dict]:
    """
    Runs GPT-4o-mini evaluation over provided raw job listings.
    Designed to run in parallel with Groq in the main pipeline thread.
    """
    qualified_jobs = []
    print(f"\n[GITHUB] Evaluating {len(raw_jobs_list)} raw jobs with {GITHUB_MODEL}...")

    for job in raw_jobs_list:
        title    = job.get("title",    "Unknown Title")
        company  = job.get("company",  "Unknown Company")
        location = job.get("location", "India")
        link     = job.get("link",     "")
        snippet  = job.get("snippet",  "")
        source   = job.get("source",   "serper")

        if not snippet:
            continue

        evaluation = evaluate_job_github(snippet, title)

        if not evaluation:
            continue

        if not evaluation.get("is_valid"):
            reason = evaluation.get("invalid_reason", "")
            print(f"  [SKIP]  {title} | {reason or 'failed validity check'}")
            continue

        score   = evaluation.get("resume_match_score", 0)
        bracket = evaluation.get("experience_bracket", "Unknown")

        if score >= 60:
            print(f"  [GITHUB ✓] {title} @ {company} | {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":             source,
                "evaluator":          "GitHub",
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

    print(f"[GITHUB] {len(qualified_jobs)} qualified out of {len(raw_jobs_list)}.")
    return qualified_jobs