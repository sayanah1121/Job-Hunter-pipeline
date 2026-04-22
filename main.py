import concurrent.futures
from src.extractor import extract_raw_jobs
from src.extractor_apify import extract_jobs_apify
from src.evaluator_gemini import process_with_gemini
from src.evaluator_groq import process_with_groq
from src.evaluator_github import process_with_github
from src.loader import save_to_excel, send_job_report


def run_branch(branch_name, target_roles, evaluator_function):
    """Serper-based branches (Gemini / Groq / GitHub)."""
    print(f"\n [STARTING THREAD] {branch_name} Extractor -> {branch_name} Evaluator")
    raw_jobs = extract_raw_jobs(target_roles=target_roles, location="India", pages_per_role=2)
    if not raw_jobs:
        print(f"  [WARNING] No jobs found for {branch_name} branch.")
        return []
    return evaluator_function(raw_jobs)


def run_apify_branch(target_roles):
    """
    Apify (LinkedIn) branch.
    Single extraction -> evaluated by all 3 models in parallel -> merged & deduplicated.
    No Anthropic key required.
    """
    print(f"\n [STARTING THREAD] APIFY (LinkedIn) Extractor")
    raw_jobs = extract_jobs_apify(target_roles=target_roles, location="India", max_results=50)

    if not raw_jobs:
        print("  [WARNING] No jobs found for APIFY branch.")
        return []

    print(f"\n [APIFY] Fanning out {len(raw_jobs)} LinkedIn jobs to 3 evaluators in parallel...")

    # Tag source before evaluation so it carries through to Excel
    for job in raw_jobs:
        job["source"] = "LinkedIn (Apify)"

    apify_qualified = []

    # Inner fan-out: same LinkedIn jobs evaluated by all 3 models simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_gemini = executor.submit(process_with_gemini, raw_jobs)
        future_groq   = executor.submit(process_with_groq,   raw_jobs)
        future_github = executor.submit(process_with_github,  raw_jobs)

        results_gemini = future_gemini.result()
        results_groq   = future_groq.result()
        results_github = future_github.result()

    # Tag which model approved each job
    for job in results_gemini: job["evaluator"] = "Gemini"
    for job in results_groq:   job["evaluator"] = "Groq"
    for job in results_github: job["evaluator"] = "GitHub"

    # Merge all 3 model results
    combined = results_gemini + results_groq + results_github

    # Deduplicate by application_link — keep highest score across models
    seen = {}
    for job in combined:
        link = job.get("application_link", "")
        if not link:
            apify_qualified.append(job)
            continue
        if link not in seen or job["resume_match_score"] > seen[link]["resume_match_score"]:
            seen[link] = job

    apify_qualified.extend(seen.values())

    print(f"\n [APIFY] {len(apify_qualified)} unique LinkedIn jobs qualified after deduplication.")
    return apify_qualified


if __name__ == "__main__":
    print("==================================================")
    print(" INITIALIZING MULTI-MODEL AI PIPELINE")
    print("==================================================")

    # Serper batches (search engine scraping)
    batch_1 = ["Data Engineer", "Junior Data Engineer", "Associate Data Engineer"]
    batch_2 = ["Fresher Data Engineer", "Data Engineer Trainee", "ETL Developer"]
    batch_3 = ["Data Pipeline Engineer", "Cloud Data Engineer", "Azure Data Engineer", "PySpark Developer"]

    # Apify batch (LinkedIn — richer data, no bot blocking)
    batch_apify = ["Data Engineer", "ETL Developer", "Azure Data Engineer", "PySpark Developer"]

    all_qualified_jobs = []

    # Outer fan-out: 4 branches in parallel
    # Branch 4 (Apify) itself fans out internally to 3 evaluators
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_gemini = executor.submit(run_branch, "GEMINI", batch_1, process_with_gemini)
        future_groq   = executor.submit(run_branch, "GROQ",   batch_2, process_with_groq)
        future_github = executor.submit(run_branch, "GITHUB", batch_3, process_with_github)
        future_apify  = executor.submit(run_apify_branch, batch_apify)

        results_gemini = future_gemini.result()
        results_groq   = future_groq.result()
        results_github = future_github.result()
        results_apify  = future_apify.result()

    # Fan-in: merge all branches
    for results in [results_gemini, results_groq, results_github, results_apify]:
        if results:
            all_qualified_jobs.extend(results)

    print(f"\n[PHASE 3: LOADER] Merging {len(all_qualified_jobs)} total qualified jobs...")

    if all_qualified_jobs:
        excel_path = save_to_excel(all_qualified_jobs, "Daily_Data_Engineering_Jobs.xlsx")
        send_job_report(excel_path)
    else:
        print("Pipeline finished, but no jobs passed the strict LLM evaluations today.")