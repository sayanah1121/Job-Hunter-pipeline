import concurrent.futures
from src.extractor import extract_raw_jobs
from src.extractor_apify import extract_jobs_apify          # <-- NEW
from src.evaluator import process_and_filter_jobs           # <-- Claude Haiku for Apify branch
from src.evaluator_gemini import process_with_gemini
from src.evaluator_groq import process_with_groq
from src.evaluator_github import process_with_github
from src.loader import save_to_excel, send_job_report


def run_branch(branch_name, target_roles, evaluator_function):
    """Serper-based branches (Gemini / Groq / GitHub)"""
    print(f"\n [STARTING THREAD] {branch_name} Extractor -> {branch_name} Evaluator")
    raw_jobs = extract_raw_jobs(target_roles=target_roles, location="India", pages_per_role=2)
    if not raw_jobs:
        print(f"⚠️ [WARNING] No jobs found for {branch_name} branch.")
        return []
    return evaluator_function(raw_jobs)


def run_apify_branch(target_roles):
    """Apify (LinkedIn) branch — uses Claude Haiku evaluator"""
    print(f"\n [STARTING THREAD] APIFY (LinkedIn) Extractor -> Claude Haiku Evaluator")
    raw_jobs = extract_jobs_apify(target_roles=target_roles, location="India", max_results=50)
    if not raw_jobs:
        print("⚠️ [WARNING] No jobs found for APIFY branch.")
        return []
    return process_and_filter_jobs(raw_jobs)   # your existing Claude evaluator


if __name__ == "__main__":
    print("==================================================")
    print(" INITIALIZING MULTI-MODEL AI PIPELINE")
    print("==================================================")

    batch_1 = ["Data Engineer", "Junior Data Engineer", "Associate Data Engineer"]
    batch_2 = ["Fresher Data Engineer", "Data Engineer Trainee", "ETL Developer"]
    batch_3 = ["Data Pipeline Engineer", "Cloud Data Engineer", "Azure Data Engineer", "PySpark Developer"]
    batch_4 = ["Data Engineer", "ETL Developer", "Azure Data Engineer", "PySpark Developer"]  # LinkedIn via Apify

    all_qualified_jobs = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:      # 3 -> 4
        future_gemini = executor.submit(run_branch, "GEMINI",  batch_1, process_with_gemini)
        future_groq   = executor.submit(run_branch, "GROQ",    batch_2, process_with_groq)
        future_github = executor.submit(run_branch, "GITHUB",  batch_3, process_with_github)
        future_apify  = executor.submit(run_apify_branch, batch_4)              # <-- NEW

        results_gemini = future_gemini.result()
        results_groq   = future_groq.result()
        results_github = future_github.result()
        results_apify  = future_apify.result()                                  # <-- NEW

    for results in [results_gemini, results_groq, results_github, results_apify]:
        if results:
            all_qualified_jobs.extend(results)

    # Add source tag so you can tell LinkedIn results apart in Excel
    for job in results_apify or []:
        job["source"] = "LinkedIn (Apify)"

    print(f"\n[PHASE 3: LOADER] Merging {len(all_qualified_jobs)} total qualified jobs...")

    if all_qualified_jobs:
        excel_path = save_to_excel(all_qualified_jobs, "Daily_Data_Engineering_Jobs.xlsx")
        send_job_report(excel_path)
    else:
        print("Pipeline finished, but no jobs passed the strict LLM evaluations today.")