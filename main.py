import concurrent.futures
from src.extractor import extract_raw_jobs
from src.evaluator_gemini import process_with_gemini
from src.evaluator_groq import process_with_groq
from src.evaluator_github import process_with_github
from src.loader import save_to_excel, send_job_report

def run_branch(branch_name, target_roles, evaluator_function):
    print(f"\n [STARTING THREAD] {branch_name} Extractor -> {branch_name} Evaluator")
    
    # 1. Extractor
    raw_jobs = extract_raw_jobs(target_roles=target_roles, location="India", pages_per_role=2)
    if not raw_jobs:
        print(f"⚠️ [WARNING] No jobs found for {branch_name} branch.")
        return []
        
    # 2. Evaluator
    qualified_jobs = evaluator_function(raw_jobs)
    return qualified_jobs

if __name__ == "__main__":
    print("==================================================")
    print(" INITIALIZING MULTI-MODEL AI PIPELINE")
    print("==================================================")

    # Split the workload into three distinct extraction batches
    batch_1 = ["Data Engineer", "Junior Data Engineer", "Associate Data Engineer"]
    batch_2 = ["Fresher Data Engineer", "Data Engineer Trainee", "ETL Developer"]
    batch_3 = ["Data Pipeline Engineer", "Cloud Data Engineer", "Azure Data Engineer", "PySpark Developer"]

    all_qualified_jobs = []

    # FAN-OUT: Run all three Extractors and Evaluators in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_gemini = executor.submit(run_branch, "GEMINI", batch_1, process_with_gemini)
        future_groq = executor.submit(run_branch, "GROQ", batch_2, process_with_groq)
        future_github = executor.submit(run_branch, "GITHUB", batch_3, process_with_github)

        # Gather results as they finish
        results_gemini = future_gemini.result()
        results_groq = future_groq.result()
        results_github = future_github.result()

    # FAN-IN: Combine all data
    if results_gemini: all_qualified_jobs.extend(results_gemini)
    if results_groq: all_qualified_jobs.extend(results_groq)
    if results_github: all_qualified_jobs.extend(results_github)

    print(f"\n[PHASE 3: LOADER] Merging {len(all_qualified_jobs)} total qualified jobs...")
    
    # 3. Loader
    if all_qualified_jobs:
        excel_path = save_to_excel(all_qualified_jobs, "Daily_Data_Engineering_Jobs.xlsx")
        send_job_report(excel_path)
    else:
        print("Pipeline finished, but no jobs passed the strict LLM evaluations today.")