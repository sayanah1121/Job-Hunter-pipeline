import os
import time
from datetime import datetime

# Import our custom pipeline modules
from src.extractor import extract_raw_jobs
from src.evaluator import process_and_filter_jobs, save_to_excel
from src.loader import send_job_report

def run_pipeline():
    print("==================================================")
    print(f" INITIALIZING JOB AUTOMATION PIPELINE")
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==================================================\n")
    
    start_time = time.time()

    # 1. Define the target parameters
    # Using the comprehensive list we built to catch all naming conventions
    target_roles = [
        "Data Engineer", 
        "Junior Data Engineer", 
        "Associate Data Engineer", 
        "Fresher Data Engineer", 
        "Data Engineer Trainee", 
        "ETL Developer", 
        "Data Pipeline Engineer", 
        "Cloud Data Engineer",
        "Azure Data Engineer",
        "PySpark Developer"
    ]
    location = "India"
    pages_per_role = 2  # Adjust this to 3 or 4 if you want a larger daily batch
    
    excel_filename = f"Daily_Data_Engineering_Jobs_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    try:
        # --- PHASE 1: EXTRACT ---
        print("\n[PHASE 1: EXTRACTION STARTED]")
        raw_data = extract_raw_jobs(target_roles=target_roles, location=location, pages_per_role=pages_per_role)
        
        if not raw_data:
            print("\n Pipeline Halted: No raw jobs were extracted today. API might be down or rate-limited.")
            return

        # --- PHASE 2: TRANSFORM (EVALUATE & SAVE) ---
        print("\n[PHASE 2: EVALUATION STARTED]")
        evaluated_jobs = process_and_filter_jobs(raw_data)
        
        # We always generate the Excel file, even if empty, so you know the pipeline ran
        excel_filepath = save_to_excel(evaluated_jobs, excel_filename)
        
        if not evaluated_jobs:
            print("\n Note: No jobs passed the strict 0-2 year AI filters today.")
            # We still send the email so you know the pipeline completed successfully
            
        # --- PHASE 3: LOAD (EMAIL) ---
        print("\n[PHASE 3: DISPATCH STARTED]")
        email_success = send_job_report(excel_filepath)
        
        if email_success:
            print("\n Pipeline completed successfully! Check your inbox.")
        else:
            print("\n Pipeline finished, but email dispatch failed.")

    except Exception as e:
        print(f"\n CRITICAL PIPELINE FAILURE: {e}")
        
    finally:
        end_time = time.time()
        execution_time = round(end_time - start_time, 2)
        print("==================================================")
        print(f" Total Execution Time: {execution_time} seconds")
        print("==================================================")

if __name__ == "__main__":
    # Ensure the data directory exists before running
    os.makedirs("data", exist_ok=True)
    
    # Run the orchestrator
    run_pipeline()