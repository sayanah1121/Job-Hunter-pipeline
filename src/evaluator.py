import os
import json
import pandas as pd
import anthropic
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("CRITICAL ERROR: ANTHROPIC_API_KEY not found. Check your .env file.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Candidate profile directly integrated for the AI's matching engine
CANDIDATE_PROFILE = """
Candidate Name: Sayan Sarkar
Role: Data Engineer / Software Engineer
Experience: 0-1 Years (8 months at Bitwise Solutions)
Key Technologies: Apache Airflow, PySpark, Docker, PostgreSQL, Python, SQL, C++, Kafka.
Cloud & Data Stack: Google Cloud Platform (GCP), Azure (ADLS, Azure Data Factory, Azure Databricks, Event Hub).
Core Competencies: ETL Optimization, Metadata-driven Pipelines, Incremental Data Loading (Backfilling), Slowly Changing Dimensions (SCD Type 1 & 2).
Key Projects & Experience:
1. Bitwise Solutions: Optimized SQL queries reducing batch execution by 30%. Handled functional analysis and root-cause triage in Ab Initio GDE environments.
2. Cloud Data Engineering: Metadata-driven pipelines on Azure using ADF, Databricks, and Event Hub with complex SCD implementations.
3. FinTech Nexus Pipeline: Scalable fan-out/fan-in architecture using Airflow, PySpark, and Docker.
4. Livekart Real-Time Streaming Engine: Fault-tolerant streaming using Kafka, Zookeeper, and Spark Streaming.
5. distributed-payment-engine: Secure, asynchronous transaction processing.
6. BookMySeat: High-concurrency booking engine design.
"""

def evaluate_job(job_snippet, job_title):
    system_prompt = f"""
    You are an expert Technical Recruiter evaluating jobs for a Data Engineer candidate.
    
    Candidate Profile:
    {CANDIDATE_PROFILE}
    
    Task:
    1. Read the provided Job Title and Description Snippet.
    2. VALIDITY: If the snippet is just an aggregate list (e.g., "100+ Jobs on LinkedIn"), mark is_valid as false.
    3. EXPERIENCE FILTER & CATEGORIZATION: The candidate is looking for roles up to 1-2 years of experience.
       - If the job explicitly requires a MINIMUM of 2+ years (e.g., "2-4 years", "3+ years"), it is a FAIL (mark is_valid as false).
       - Categorize the experience into EXACTLY one of these strings for the experience_bracket: "0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", or "Unknown".
       - If no exact years are mentioned but keywords like "fresher", "entry level" are present, OR if experience isn't specified at all, categorize as "Unknown".
    4. Calculate resume_match_score (0-100) based on alignment with the candidate's Azure, Bitwise, and system design background.
    5. Extract matched_skills and missing_skills.
    
    Respond strictly in JSON format. Do not include markdown tags.
    
    Schema:
    {{
        "is_valid": boolean,
        "experience_bracket": "string",
        "resume_match_score": integer,
        "matched_skills": "string",
        "missing_skills": "string"
    }}
    """

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            temperature=0.0, 
            system=system_prompt,
            messages=[{"role": "user", "content": f"Title: {job_title}\nDescription: {job_snippet}"}]
        )
        
        raw_text = response.content[0].text
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            return json.loads(raw_text[start_idx:end_idx+1])
        return None
            
    except Exception as e:
        print(f"  -> Evaluation Error for {job_title}: {e}")
        return None

def process_and_filter_jobs(raw_jobs_list):
    qualified_jobs = []
    print(f"\nEvaluating {len(raw_jobs_list)} raw jobs using Claude...")
    
    for job in raw_jobs_list:
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company") 
        location = job.get("location", "India")
        link = job.get("link", "")
        snippet = job.get("snippet", "")
        
        if not snippet:
            continue
            
        evaluation = evaluate_job(snippet, title)
        
        if evaluation and evaluation.get("is_valid"):
            score = evaluation.get("resume_match_score", 0)
            bracket = evaluation.get("experience_bracket", "Unknown")
            
            if score >= 60:
                print(f"  [MATCH] {title} | Bracket: {bracket} | Score: {score}")
                qualified_jobs.append({
                    "job_title": title,
                    "company_name": company,
                    "location": location,
                    "experience_bracket": bracket,
                    "resume_match_score": score,
                    "matched_skills": evaluation.get("matched_skills", ""),
                    "missing_skills": evaluation.get("missing_skills", ""),
                    "application_link": link
                })

    return qualified_jobs

def save_to_excel(jobs_list, filename):
    filepath = os.path.join("data", filename)
    os.makedirs("data", exist_ok=True)
    
    df = pd.DataFrame(jobs_list)
    expected_brackets = ["0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", "Unknown"]
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        for bracket in expected_brackets:
            if not df.empty and 'experience_bracket' in df.columns:
                sheet_data = df[df['experience_bracket'] == bracket]
            else:
                sheet_data = pd.DataFrame()
            
            # If no jobs match this bracket today, create an empty sheet with headers anyway
            if sheet_data.empty:
                empty_df = pd.DataFrame(columns=["job_title", "company_name", "location", "experience_bracket", "resume_match_score", "matched_skills", "missing_skills", "application_link"])
                empty_df.to_excel(writer, sheet_name=bracket, index=False)
            else:
                sheet_data.to_excel(writer, sheet_name=bracket, index=False)
                
    print(f"\nSuccess! Excel report saved to {filepath}")
    return filepath

if __name__ == "__main__":
    from extractor import extract_raw_jobs
    
    print("Initiating Pipeline: Phase 1 & 2 Testing\n" + "="*40)
    test_roles = ["Junior Data Engineer", "Azure Data Engineer", "Data Engineer Trainee"]
    raw_data = extract_raw_jobs(target_roles=test_roles, pages_per_role=1)
    
    final_jobs = process_and_filter_jobs(raw_data)
    save_to_excel(final_jobs, "Daily_Data_Engineering_Jobs.xlsx")