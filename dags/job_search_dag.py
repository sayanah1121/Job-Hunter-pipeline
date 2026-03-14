from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
from datetime import datetime, timedelta
import sys
import os

# Ensure Airflow can find your 'src' folder
sys.path.append('/opt/airflow')

# Lock the timezone to Indian Standard Time (IST)
local_tz = pendulum.timezone("Asia/Kolkata")

default_args = {
    'owner': 'sayan_sarkar',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# --- Task 1: The Extractor ---
def run_extractor(**kwargs):
    from src.extractor import extract_raw_jobs
    
    target_roles = [
        "Data Engineer", "Junior Data Engineer", "Associate Data Engineer", 
        "Fresher Data Engineer", "Data Engineer Trainee", "ETL Developer", 
        "Data Pipeline Engineer", "Cloud Data Engineer", "Azure Data Engineer",
        "PySpark Developer"
    ]
    
    print("[PHASE 1] Pulling jobs from Serper API...")
    raw_data = extract_raw_jobs(target_roles=target_roles, location="India", pages_per_role=2)
    
    if not raw_data:
        raise ValueError("Extraction failed or no jobs found.")
        
    # Returning data automatically pushes it to Airflow XCom so the next task can use it
    return raw_data 

# --- Task 2: The Evaluator ---
def run_evaluator(**kwargs):
    from src.evaluator import process_and_filter_jobs, save_to_excel
    
    # Pull the raw JSON data from Task 1 via XCom
    ti = kwargs['ti']
    raw_data = ti.xcom_pull(task_ids='extract_task')
    
    if not raw_data:
        raise ValueError("No raw data received from the extractor task.")
        
    print(f"[PHASE 2] Evaluating {len(raw_data)} jobs with Claude...")
    evaluated_jobs = process_and_filter_jobs(raw_data)
    
    excel_filename = f"Daily_Data_Engineering_Jobs_{datetime.now(local_tz).strftime('%Y%m%d')}.xlsx"
    filepath = save_to_excel(evaluated_jobs, excel_filename)
    
    # Push the generated file path to XCom for the loader task
    return filepath

# --- Task 3: The Loader ---
def run_loader(**kwargs):
    from src.loader import send_job_report
    
    # Pull the Excel file path from Task 2 via XCom
    ti = kwargs['ti']
    excel_filepath = ti.xcom_pull(task_ids='evaluate_task')
    
    if not excel_filepath:
        raise ValueError("No file path received from the evaluator task.")
        
    print(f"[PHASE 3] Dispatching email with attachment: {excel_filepath}")
    success = send_job_report(excel_filepath)
    
    if not success:
        raise RuntimeError("Failed to send the email report.")
    print("Pipeline completed successfully!")

# --- Define the DAG ---
with DAG(
    dag_id='daily_ai_job_pipeline',
    default_args=default_args,
    description='Decoupled ETL Job Search Pipeline (Extractor -> Evaluator -> Loader)',
    schedule_interval='0 21 * * *', # 9:00 PM IST
    start_date=datetime(2026, 3, 13, tzinfo=local_tz),
    catchup=False,
    tags=['etl', 'data_engineering', 'ai'],
) as dag:

    # Define the three distinct boxes (tasks)
    extract_task = PythonOperator(
        task_id='extract_task',
        python_callable=run_extractor,
        provide_context=True,
    )

    evaluate_task = PythonOperator(
        task_id='evaluate_task',
        python_callable=run_evaluator,
        provide_context=True,
    )

    load_task = PythonOperator(
        task_id='load_task',
        python_callable=run_loader,
        provide_context=True,
    )

    # Set the dependencies to create the visual flow: Box 1 -> Box 2 -> Box 3
    extract_task >> evaluate_task >> load_task