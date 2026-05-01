"""
deduplicator.py
───────────────
Two utilities used at different points in the pipeline:

  1. deduplicate_raw(jobs)
     Call BEFORE evaluation — removes duplicate raw listings so each job
     is only evaluated once. Duplicates were visible in the logs:
     "Associate Data Analyst - Ecolab" appeared twice with identical scores.

  2. deduplicate_and_merge(qualified_jobs)
     Call AFTER all evaluators run — merges the same job if it was
     independently qualified by multiple evaluators, keeping the highest score
     and recording which evaluators agreed on it (a strong quality signal).
"""

from __future__ import annotations
import re


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation/whitespace — used for key generation."""
    return re.sub(r"[^a-z0-9]", "", text.lower().strip())


def _raw_key(job: dict) -> str:
    """
    Dedup key for raw listings.
    Uses (title, company) — good enough before evaluation because two entries
    with the same title from the same company are the same job regardless of
    which search query or page surfaced them.
    Falls back to link if both title and company are empty.
    """
    title   = _normalise(job.get("title",   ""))
    company = _normalise(job.get("company", ""))
    link    = job.get("link", "").strip()

    if title and company:
        return f"{title}::{company}"
    if link:
        return link
    return title  # last resort


def _qualified_key(job: dict) -> str:
    """
    Dedup key for qualified (post-evaluation) jobs.
    Same logic as _raw_key but operates on evaluator output field names.
    """
    title   = _normalise(job.get("job_title",    ""))
    company = _normalise(job.get("company_name", ""))
    link    = job.get("application_link", "").strip()

    if title and company:
        return f"{title}::{company}"
    if link:
        return link
    return title


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def deduplicate_raw(jobs: list[dict]) -> list[dict]:
    """
    Remove duplicate raw listings BEFORE evaluation.

    Strategy: first-seen wins. Keeps the entry that appeared earliest in the
    combined extractor output (Serper jobs cards are preferred over organic
    because they're richer, and Serper runs before Apify in the pipeline).

    Returns the deduplicated list and prints a summary line.
    """
    seen:   dict[str, dict] = {}
    dupes = 0

    for job in jobs:
        key = _raw_key(job)
        if key not in seen:
            seen[key] = job
        else:
            dupes += 1

    unique = list(seen.values())
    print(f"[DEDUP] Raw listings: {len(jobs)} → {len(unique)} unique ({dupes} duplicates removed)")
    return unique


def deduplicate_and_merge(qualified_jobs: list[dict]) -> list[dict]:
    """
    Merge qualified jobs that were independently approved by multiple evaluators.

    Rules:
      • Same job (same key) found by 2+ evaluators → keep the HIGHEST score.
      • Record all agreeing evaluators in a comma-separated "evaluator" field,
        e.g. "Gemini, Groq, Mistral" — useful for sorting in Excel.
      • The merged entry inherits matched_skills / missing_skills from the
        highest-scoring evaluator's output.

    Returns deduplicated, merged list sorted by resume_match_score descending.
    """
    merged: dict[str, dict] = {}

    for job in qualified_jobs:
        key       = _qualified_key(job)
        evaluator = job.get("evaluator", "Unknown")
        score     = job.get("resume_match_score", 0)

        if key not in merged:
            merged[key] = dict(job)  # copy so we don't mutate the original
            merged[key]["_evaluators"] = [evaluator]
        else:
            existing = merged[key]
            existing["_evaluators"].append(evaluator)

            # Promote to higher score + richer skill data
            if score > existing.get("resume_match_score", 0):
                existing["resume_match_score"] = score
                existing["matched_skills"]     = job.get("matched_skills", "")
                existing["missing_skills"]     = job.get("missing_skills", "")
                existing["experience_bracket"] = job.get("experience_bracket", "Unknown")

    # Finalise: write evaluator list, sort, clean up temp key
    result = []
    for job in merged.values():
        evaluators = sorted(set(job.pop("_evaluators", [])))
        job["evaluator"] = ", ".join(evaluators)
        result.append(job)

    result.sort(key=lambda j: j.get("resume_match_score", 0), reverse=True)

    before = len(qualified_jobs)
    after  = len(result)
    multi  = sum(1 for j in result if "," in j.get("evaluator", ""))
    print(
        f"[DEDUP] Qualified jobs: {before} → {after} unique "
        f"({before - after} dupes merged, {multi} confirmed by multiple evaluators)"
    )
    return result