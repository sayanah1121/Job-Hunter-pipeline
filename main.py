"""
main.py — AI Job Hunter Pipeline
─────────────────────────────────
Architecture (5 evaluators, 2 sources):

  Phase 1 — EXTRACT (parallel threads)
    • Serper   → 3 batches × Google Search → batch_1/2/3/4/5
    • Apify    → LinkedIn scrape           → batch_apify

  Phase 1.5 — DEDUP RAW
    • deduplicate_raw() removes duplicate listings before any LLM call
      (saves API quota and prevents the same job scoring twice)

  Phase 2 — EVALUATE (parallel threads, one model per Serper batch)
    • Batch 1 → Gemini 2.0 Flash-Lite   (fast bulk triage, free)
    • Batch 2 → Groq Llama 3.3 70B      (strong rubric scoring, free)
    • Batch 3 → GitHub GPT-4o-mini       (reliable JSON, free)
    • Batch 4 → Mistral-Small-Latest     (cross-validator, free tier)
    • Batch 5 → Together/Qwen2.5-72B     (high-confidence scorer, $1 free credits)
    • Apify   → all 5 evaluators in parallel (LinkedIn jobs get broader coverage)

  Phase 3 — DEDUP & MERGE QUALIFIED
    • deduplicate_and_merge() collapses same jobs across evaluators,
      keeps highest score, records which models agreed (multi-evaluator flag)

  Phase 4 — LOAD
    • Excel report with ★ Multi-Evaluator Confirmed sheet + per-bracket sheets
    • Email dispatch
"""

import concurrent.futures
from src.extractor          import extract_raw_jobs
from src.extractor_apify    import extract_jobs_apify
from src.evaluator_gemini   import process_with_gemini
from src.evaluator_groq     import process_with_groq
from src.evaluator_github   import process_with_github
from src.evaluator_mistral  import process_with_mistral
from src.evaluator_together import process_with_together
from src.deduplicator       import deduplicate_raw, deduplicate_and_merge
from src.loader             import save_to_excel, send_job_report


# ── Serper batch runner ───────────────────────────────────────────────────────

def run_branch(branch_name: str, target_roles: list[str], evaluator_function) -> list[dict]:
    """
    Serper extraction → dedup raw → single evaluator.
    Each Serper batch runs in its own thread with its assigned model.
    """
    print(f"\n [THREAD] {branch_name} → {len(target_roles)} role searches")
    raw_jobs = extract_raw_jobs(target_roles=target_roles, location="India", pages_per_role=2)

    if not raw_jobs:
        print(f"  [WARNING] No jobs found for {branch_name} branch.")
        return []

    raw_jobs = deduplicate_raw(raw_jobs)
    return evaluator_function(raw_jobs)


# ── Apify (LinkedIn) branch ───────────────────────────────────────────────────

def run_apify_branch(target_roles: list[str]) -> list[dict]:
    """
    LinkedIn extraction via Apify → dedup raw →
    all 5 evaluators in parallel → dedup & merge results.

    LinkedIn jobs get evaluated by every model because:
      a) They tend to have richer descriptions (more context for scoring).
      b) The multi-evaluator confirmation flag is especially valuable here —
         a LinkedIn job confirmed by 3+ models is very high confidence.
    """
    print(f"\n [THREAD] APIFY (LinkedIn) → {len(target_roles)} role searches")
    raw_jobs = extract_jobs_apify(target_roles=target_roles, location="India", max_results=50)

    if not raw_jobs:
        print("  [WARNING] No LinkedIn jobs found via Apify.")
        return []

    # Tag source before dedup so the field is preserved
    for job in raw_jobs:
        job["source"] = "LinkedIn (Apify)"

    raw_jobs = deduplicate_raw(raw_jobs)

    print(f"\n [APIFY] Fanning out {len(raw_jobs)} LinkedIn jobs → 5 evaluators in parallel...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        f_gemini   = executor.submit(process_with_gemini,   raw_jobs)
        f_groq     = executor.submit(process_with_groq,     raw_jobs)
        f_github   = executor.submit(process_with_github,   raw_jobs)
        f_mistral  = executor.submit(process_with_mistral,  raw_jobs)
        f_together = executor.submit(process_with_together, raw_jobs)

        apify_all = (
            f_gemini.result()
            + f_groq.result()
            + f_github.result()
            + f_mistral.result()
            + f_together.result()
        )

    apify_qualified = deduplicate_and_merge(apify_all)
    print(f"\n [APIFY] {len(apify_qualified)} unique LinkedIn jobs qualified after merge.")
    return apify_qualified


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AI JOB HUNTER — DATA ANALYST EDITION")
    print("=" * 60)

    # ── SERPER BATCHES ───────────────────────────────────────────
    # Each batch is assigned to one evaluator to spread API load.
    # The same role searched by multiple batches is fine — dedup handles it.

    # Core DA titles → Gemini (fast, free, handles high volume well)
    batch_1 = [
        "Data Analyst",
        "Junior Data Analyst",
        "Associate Data Analyst",
        "Entry Level Data Analyst",
    ]

    # BI / reporting titles → Groq Llama 3.3 70B (strong rubric adherence)
    batch_2 = [
        "Business Analyst Data",
        "BI Analyst",
        "MIS Analyst",
        "Reporting Analyst",
        "SQL Analyst",
    ]

    # BI tool / domain titles → GitHub GPT-4o-mini (reliable JSON output)
    batch_3 = [
        "Power BI Analyst",
        "Tableau Analyst",
        "Analytics Analyst",
        "Operations Analyst Data",
    ]

    # Domain-specific DA roles → Mistral (cross-validator for niche titles)
    batch_4 = [
        "Data Analyst Banking",
        "Data Analyst BFSI",
        "Data Analyst Finance",
        "Analytics Engineer",
    ]

    # Fresher / trainee DA titles → Together/Qwen (high-confidence final scorer)
    batch_5 = [
        "Fresher Data Analyst",
        "Trainee Data Analyst",
        "Graduate Data Analyst",
        "Data Analyst Fresher",
    ]

    # ── APIFY BATCH (LinkedIn) ───────────────────────────────────
    batch_apify = [
        "Data Analyst",
        "Junior Data Analyst",
        "Business Intelligence Analyst",
        "SQL Analyst",
        "Power BI Analyst",
        "Analytics Engineer",
    ]

    # ── PHASE 2: PARALLEL EXTRACTION + EVALUATION ───────────────
    # 6 threads: 5 Serper branches + 1 Apify branch
    print("\n" + "=" * 60)
    print("  PHASE 2: EXTRACTION + EVALUATION (6 threads)")
    print("=" * 60)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_b1    = executor.submit(run_branch, "GEMINI",   batch_1, process_with_gemini)
        f_b2    = executor.submit(run_branch, "GROQ",     batch_2, process_with_groq)
        f_b3    = executor.submit(run_branch, "GITHUB",   batch_3, process_with_github)
        f_b4    = executor.submit(run_branch, "MISTRAL",  batch_4, process_with_mistral)
        f_b5    = executor.submit(run_branch, "TOGETHER", batch_5, process_with_together)
        f_apify = executor.submit(run_apify_branch, batch_apify)

        results_b1    = f_b1.result()
        results_b2    = f_b2.result()
        results_b3    = f_b3.result()
        results_b4    = f_b4.result()
        results_b5    = f_b5.result()
        results_apify = f_apify.result()

    # ── PHASE 3: DEDUP & MERGE ALL RESULTS ──────────────────────
    print("\n" + "=" * 60)
    print("  PHASE 3: DEDUP & MERGE")
    print("=" * 60)

    raw_combined = (
        results_b1
        + results_b2
        + results_b3
        + results_b4
        + results_b5
        + results_apify
    )

    all_qualified_jobs = deduplicate_and_merge(raw_combined)

    total = len(all_qualified_jobs)
    multi = sum(1 for j in all_qualified_jobs if "," in j.get("evaluator", ""))

    print(f"\n  Total qualified  : {total}")
    print(f"  Multi-confirmed  : {multi} (approved by 2+ AI models)")

    # ── PHASE 4: LOAD ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  PHASE 4: LOADER — saving {total} jobs")
    print("=" * 60)

    if all_qualified_jobs:
        excel_path = save_to_excel(all_qualified_jobs, "Daily_DataAnalyst_Jobs.xlsx")
        send_job_report(excel_path)
    else:
        print("  Pipeline finished — no jobs passed all evaluations today.")