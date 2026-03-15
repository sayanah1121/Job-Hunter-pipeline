import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("CRITICAL ERROR: GROQ_API_KEY not found.")

client = Groq(api_key=GROQ_API_KEY)

CANDIDATE_PROFILE = """
Candidate Name: Sayan Sarkar
Role: Data Engineer
Experience: 0-1 Years (Trainee Data Engineer at Bitwise Solutions)
Key Technologies: Azure Data Factory (ADF), ADLS Gen2, Azure Databricks, Snowflake, GCP, Apache Spark / PySpark, Apache Kafka, Apache Airflow, Python, SQL, Docker, GitHub Actions, dbt, Ab Initio GDE.
Core Competencies: ETL/ELT Pipelines, Real-Time Streaming, SQL Performance Tuning, Data Quality Automation, Root Cause Analysis.
Key Projects & Experience:
1. Bitwise Solutions: Reduced daily batch pipeline execution time by 30% via SQL query optimization and TWS schedule fine-tuning. 
2. LiveKart Real-Time Streaming Engine: Fault-tolerant event streaming platform using Apache Kafka, Zookeeper, and Spark Streaming.
3. Automated AI Job Hunter Pipeline: End-to-End ETL pipeline extracting jobs via Serper API.
"""

def evaluate_job_groq(job_snippet, job_title):
    system_prompt = f"""
    You are an expert Technical Recruiter evaluating jobs for a Data Engineer candidate.
    
    Candidate Profile:
    {CANDIDATE_PROFILE}
    
    Task:
    1. Read the provided Job Title and Description Snippet.
    2. VALIDITY: If the snippet is an aggregate list (e.g., "100+ Jobs"), mark is_valid as false.
    3. TIME CHECK: If the snippet mentions the job is older than 1 week, mark is_valid as false.
    4. EXPERIENCE FILTER: The candidate is looking for roles up to 1-2 years of experience.
       - If the job explicitly requires a MINIMUM of 2+ years, it is a FAIL (mark is_valid as false).
       - Categorize the experience into EXACTLY one of these strings for the experience_bracket: "0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", or "Unknown".
       - If no exact years are mentioned but keywords like "fresher" or "entry level" are present, categorize as "Unknown".
    5. Calculate resume_match_score (0-100) based on alignment with the candidate's Azure, Kafka, Spark, and Bitwise background.
    6. Extract matched_skills and missing_skills.
    
    You must return ONLY a valid JSON object matching this schema:
    {{
        "is_valid": boolean,
        "experience_bracket": "string",
        "resume_match_score": integer,
        "matched_skills": "string",
        "missing_skills": "string"
    }}
    """

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Title: {job_title}\nDescription: {job_snippet}"}
            ],
            model="llama-3.1-8b-instant", # Updated Model
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        raw_text = response.choices[0].message.content
        return json.loads(raw_text)
        
    except Exception as e:
        print(f"  [GROQ] -> Evaluation Error for {job_title}: {e}")
        return None

def process_with_groq(raw_jobs_list):
    qualified_jobs = []
    print(f"\n[GROQ] Evaluating {len(raw_jobs_list)} raw jobs...")
    
    for job in raw_jobs_list:
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company") 
        location = job.get("location", "India")
        link = job.get("link", "")
        snippet = job.get("snippet", "")
        
        if not snippet:
            continue
            
        evaluation = evaluate_job_groq(snippet, title)
        
        if evaluation and evaluation.get("is_valid"):
            score = evaluation.get("resume_match_score", 0)
            bracket = evaluation.get("experience_bracket", "Unknown")
            
            if score >= 60:
                print(f"  [GROQ MATCH] {title} | Bracket: {bracket} | Score: {score}")
                qualified_jobs.append({
                    "job_title": title, "company_name": company, "location": location,
                    "experience_bracket": bracket, "resume_match_score": score,
                    "matched_skills": evaluation.get("matched_skills", ""),
                    "missing_skills": evaluation.get("missing_skills", ""), "application_link": link
                })

    return qualified_jobs