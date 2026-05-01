"""
evaluator_together.py
──────────────────────
Stage-4 / Finals evaluator using Together AI.

WHY TOGETHER AI + QWEN 2.5 72B HERE:
  • Qwen2.5-72B-Instruct is one of the strongest open-source models for
    structured reasoning and follows complex multi-rule prompts very precisely.
  • Together AI offers $1 free credits on sign-up (enough for ~500 evaluations).
  • Used as the final-pass high-confidence scorer for the top candidates that
    multiple earlier evaluators agreed on (score ≥ 70 from ≥ 2 evaluators).
  • Its output quality is close to GPT-4o on structured JSON tasks.

SETUP:
  pip install together
  Add to .env:  TOGETHER_API_KEY=<your key from api.together.xyz>

ALTERNATIVE MODEL:
  "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo" — if Qwen quota runs out.
  Change TOGETHER_MODEL below.
"""

import os
import json
import time
from together import Together
from dotenv import load_dotenv
from src.candidate_profile import FULL_SYSTEM_PROMPT

load_dotenv()

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
if not TOGETHER_API_KEY:
    raise ValueError("CRITICAL ERROR: TOGETHER_API_KEY not found. Add it to your .env file.")

client = Together(api_key=TOGETHER_API_KEY)

# ── Model selection ───────────────────────────────────────────────────────────
# Qwen2.5-72B is the primary choice: excellent structured output, strong reasoning.
# Fallback: Meta-Llama-3.1-70B-Instruct-Turbo (same price, slightly faster).
TOGETHER_MODEL = "Qwen/Qwen2.5-72B-Instruct-Turbo"
_SLEEP_BETWEEN = 0.5   # Together AI is generous on rate limits for paid tokens


def evaluate_job_together(job_snippet: str, job_title: str) -> dict | None:
    """
    High-confidence final scorer for shortlisted candidates.
    Qwen2.5-72B follows the multi-rule rubric with high precision,
    reducing false positives at the top of the candidate list.
    Returns parsed JSON dict or None on error.
    """
    try:
        response = client.chat.completions.create(
            model=TOGETHER_MODEL,
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

        # Defensive extraction — strips any accidental markdown fences
        start = raw_text.find("{")
        end   = raw_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw_text[start : end + 1])
        return None

    except Exception as e:
        print(f"  [TOGETHER] -> Evaluation Error for '{job_title}': {e}")
        return None


def process_with_together(raw_jobs_list: list[dict]) -> list[dict]:
    """
    Final-pass evaluator. Best used on the condensed shortlist
    (jobs that scored ≥ 70 from at least one prior evaluator).
    """
    qualified_jobs = []
    print(f"\n[TOGETHER] Evaluating {len(raw_jobs_list)} jobs with {TOGETHER_MODEL}...")

    for job in raw_jobs_list:
        title    = job.get("title",    "Unknown Title")
        company  = job.get("company",  "Unknown Company")
        location = job.get("location", "India")
        link     = job.get("link",     "")
        snippet  = job.get("snippet",  "")
        source   = job.get("source",   "serper")

        if not snippet:
            continue

        evaluation = evaluate_job_together(snippet, title)
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
            print(f"  [TOGETHER ✓] {title} @ {company} | {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":             source,
                "evaluator":          "Together/Qwen",
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

    print(f"[TOGETHER] {len(qualified_jobs)} qualified out of {len(raw_jobs_list)}.")
    return qualified_jobs