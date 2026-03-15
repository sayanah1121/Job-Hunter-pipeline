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

# Up-to-date candidate profile for the AI's matching engine
CANDIDATE_PROFILE = """
Candidate Name: Sayan Sarkar
Role: Data Engineer
Experience: 0-1 Years (Trainee Data Engineer at Bitwise Solutions)
Key Technologies: Azure Data Factory (ADF), ADLS Gen2, Azure Databricks, Snowflake, GCP, Apache Spark / PySpark, Apache Kafka, Apache Airflow, Python, SQL, Docker, GitHub Actions, dbt, Ab Initio GDE.
Core Competencies: ETL/ELT Pipelines, Real-Time Streaming, SQL Performance Tuning, Data Quality Automation, Root Cause Analysis.
Key Projects & Experience:
1. Bitwise Solutions: Reduced daily batch pipeline execution time by 30% via SQL query optimization and TWS schedule fine-tuning. Built automated duplicate record detection and conducted root-cause analysis of transformation failures.
2. LiveKart Real-Time Streaming Engine: Fault-tolerant event streaming platform using Apache Kafka, Zookeeper, and Spark Streaming for high-velocity e-commerce data. Containerized with Docker.
3. Automated AI Job Hunter Pipeline: End-to-End ETL pipeline extracting jobs via Serper API, evaluating with Claude Haiku, and orchestrating via Airflow and GitHub Actions.
"""

def evaluate_job(job_snippet, job_title):
    system_prompt = f"""
    You are an expert Technical Recruiter evaluating jobs for a Data Engineer candidate.
    
    Candidate Profile:
    {CANDIDATE_PROFILE}
    
    Task:
    1. Read the provided Job Title and Description Snippet.
    2. VALIDITY: If the snippet is just an aggregate list (e.g., "100+ Jobs on LinkedIn"), mark is_valid as false.
    3. TIME CHECK: If the snippet explicitly mentions the job is older than 1 week (e.g., "30+ days ago", "3 years ago", "months ago"), mark is_valid as false.
    4. EXPERIENCE FILTER & CATEGORIZATION: The candidate is looking for roles up to 1-2 years of experience.
       - If the job explicitly requires a MINIMUM of 2+ years (e.g., "2-4 years", "3+ years"), it is a FAIL (mark is_valid as false).
       - Categorize the experience into EXACTLY one of these strings for the experience_bracket: "0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", or "Unknown".
       - If no exact years are mentioned but keywords like "fresher", "entry level" are present, OR if experience isn't specified at all, categorize as "Unknown".
    5. Calculate resume_match_score (0-100) based on alignment with the candidate's Azure, Kafka, Spark, and Bitwise background.
    6. Extract matched_skills and missing_skills.
    
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
            
            if sheet_data.empty:
                empty_df = pd.DataFrame(columns=["job_title", "company_name", "location", "experience_bracket", "resume_match_score", "matched_skills", "missing_skills", "application_link"])
                empty_df.to_excel(writer, sheet_name=bracket, index=False)
            else:
                sheet_data.to_excel(writer, sheet_name=bracket, index=False)
                
    print(f"\nSuccess! Excel report saved to {filepath}")
    return filepath