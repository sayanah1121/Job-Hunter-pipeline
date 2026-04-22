import os
import json
import pandas as pd
import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("CRITICAL ERROR: ANTHROPIC_API_KEY not found. Check your .env file.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

CANDIDATE_PROFILE = """
Candidate Name: Sayan Sarkar
Current Role: Trainee Data Engineer at Bitwise Solutions (BFSI domain, ~8 months experience)
Target Roles: Data Engineer, Junior Data Engineer, Associate Data Engineer, ETL Developer, Azure Data Engineer, PySpark Developer, Data Pipeline Engineer

=== TECHNICAL STACK ===
Cloud & Storage   : Azure Data Factory (ADF), ADLS Gen2, Azure Databricks, Snowflake, GCP
Streaming         : Apache Kafka, Apache Zookeeper, Spark Streaming
Batch/Orchestration: Apache Airflow, Apache Spark / PySpark, dbt, Ab Initio GDE
DevOps & Infra    : Docker, GitHub Actions, Git
Languages         : Python (strong), SQL (strong — query optimization, performance tuning)
Databases         : PostgreSQL
Integration       : Serper API, Anthropic Claude API, Apify API

=== CORE COMPETENCIES ===
- ETL/ELT pipeline design and implementation
- Real-time event streaming architectures
- SQL query optimisation and performance tuning
- Data quality automation and duplicate detection
- Root cause analysis of transformation failures
- Medallion architecture (bronze/silver/gold layers)
- Metadata-driven pipeline design

=== PROJECTS ===
1. Bitwise Solutions (Production):
   - Reduced batch pipeline execution time by 30% via SQL optimisation + TWS schedule tuning
   - Built automated duplicate record detection system
   - Root cause analysis of transformation failures in BFSI ETL pipelines

2. LiveKart Real-Time Streaming Engine (Portfolio):
   - Fault-tolerant event streaming for high-velocity e-commerce data
   - Stack: Apache Kafka, Zookeeper, Spark Streaming, Docker

3. AI Job Hunter Pipeline (Portfolio):
   - End-to-End ETL: Serper API extraction → Claude Haiku evaluation → Airflow + GitHub Actions orchestration
   - Multi-model parallel evaluation (Gemini, Groq, GitHub Models, Anthropic)
   - Apify LinkedIn integration with medallion architecture

=== EXPERIENCE LEVEL ===
0–1 year total. Suitable for roles requiring 0–2 years. HARD REJECT if minimum is 2+ years stated explicitly.
"""

# ---------------------------------------------------------------------------
# Improved system prompt — tighter rules, richer scoring rubric
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""
You are a precise Technical Recruiter AI evaluating job listings for a specific Data Engineer candidate.
Your evaluations directly affect which jobs the candidate applies to — accuracy is critical.

{CANDIDATE_PROFILE}

=== EVALUATION RULES ===

STEP 1 — VALIDITY CHECK (mark is_valid: false if ANY condition below is true):
  a) The snippet is an aggregate/category page (e.g. "100+ Data Engineer jobs on LinkedIn").
  b) The job was posted MORE than 7 days ago. Signals: "30+ days ago", "1 month ago", "2 weeks ago", "3 years ago".
     NOTE: "1 week ago", "5 days ago", "today", "3 days ago" are VALID.
  c) The job EXPLICITLY requires a MINIMUM of 2 or more years experience (e.g. "minimum 2 years", "3-5 years required", "at least 2 years").
     NOTE: Ranges like "0-2 years", "1-2 years", "up to 2 years" are VALID.

STEP 2 — EXPERIENCE BRACKET (assign EXACTLY one of these four strings):
  "0 to 1 yrs"  → Job states 0-1 year, or fresher/entry-level/trainee explicitly
  "0 to 2 yrs"  → Job states 0-2 years, or 1-2 years, or similar range within 0–2
  "1 to 2 yrs"  → Job explicitly states 1-2 years minimum with no flexibility
  "Unknown"     → No experience requirement mentioned at all

STEP 3 — RESUME MATCH SCORE (0–100 integer):
  Score based on how well the candidate's skills align with the job requirements.
  
  SCORING RUBRIC (add points):
  +20 if core stack matches (Spark/PySpark, Kafka, Airflow, ADF, ADLS)
  +15 if SQL / Python explicitly required and candidate is strong in both
  +15 if cloud platform matches (Azure preferred, GCP acceptable)
  +10 if domain matches (BFSI/banking/fintech) — candidate has direct BFSI ETL experience
  +10 if ETL/ELT pipeline experience is the core requirement
  +10 if streaming/real-time experience is required (Kafka, Spark Streaming)
  +10 if orchestration tools match (Airflow, ADF)
  +5  if containerisation / DevOps mentioned (Docker, GitHub Actions)
  +5  if data modelling / dbt / warehousing mentioned

  DEDUCTIONS:
  -20 if job requires technologies the candidate has ZERO exposure to (e.g. Hadoop, Hive, Scala, Java — not Python)
  -15 if role is primarily a Data Analyst, Data Scientist, or BI role (not engineering)
  -10 if requires 5+ years even if stated as preferred

  Final score must be between 0 and 100.

STEP 4 — SKILL EXTRACTION:
  matched_skills: Comma-separated list of skills from the job that the candidate HAS.
  missing_skills: Comma-separated list of skills from the job that the candidate LACKS or has no evidence of.
  Keep each list concise (max 8 items each). Use short labels like "PySpark", "Kafka", "Airflow", "Scala".

=== OUTPUT FORMAT ===
Respond ONLY with a valid JSON object. No markdown, no explanation, no extra text.

Schema:
{{
    "is_valid": boolean,
    "invalid_reason": "string or empty string if valid",
    "experience_bracket": "string",
    "resume_match_score": integer,
    "matched_skills": "string",
    "missing_skills": "string"
}}
"""


def evaluate_job(job_snippet: str, job_title: str) -> dict | None:
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=350,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Job Title: {job_title}\nJob Description Snippet:\n{job_snippet}"
            }]
        )

        raw_text = response.content[0].text.strip()

        # Robust JSON extraction — handles any stray text
        start_idx = raw_text.find('{')
        end_idx   = raw_text.rfind('}')

        if start_idx != -1 and end_idx != -1:
            return json.loads(raw_text[start_idx:end_idx + 1])
        return None

    except Exception as e:
        print(f"  -> [CLAUDE] Evaluation Error for '{job_title}': {e}")
        return None


def process_and_filter_jobs(raw_jobs_list: list[dict]) -> list[dict]:
    qualified_jobs = []
    print(f"\n[CLAUDE] Evaluating {len(raw_jobs_list)} raw jobs using Claude Haiku...")

    for job in raw_jobs_list:
        title   = job.get("title",   "Unknown Title")
        company = job.get("company", "Unknown Company")
        location = job.get("location", "India")
        link    = job.get("link",    "")
        snippet = job.get("snippet", "")
        source  = job.get("source",  "serper")

        if not snippet:
            continue

        evaluation = evaluate_job(snippet, title)

        if not evaluation:
            continue

        if not evaluation.get("is_valid"):
            reason = evaluation.get("invalid_reason", "")
            print(f"  [SKIP]  {title} | Reason: {reason or 'failed validity check'}")
            continue

        score   = evaluation.get("resume_match_score", 0)
        bracket = evaluation.get("experience_bracket", "Unknown")

        if score >= 60:
            print(f"  [MATCH] {title} @ {company} | Bracket: {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":               source,
                "job_title":            title,
                "company_name":         company,
                "location":             location,
                "experience_bracket":   bracket,
                "resume_match_score":   score,
                "matched_skills":       evaluation.get("matched_skills", ""),
                "missing_skills":       evaluation.get("missing_skills", ""),
                "application_link":     link,
            })
        else:
            print(f"  [LOW]   {title} @ {company} | Score: {score} (below 60, skipping)")

    print(f"[CLAUDE] {len(qualified_jobs)} jobs qualified out of {len(raw_jobs_list)} evaluated.")
    return qualified_jobs


def save_to_excel(jobs_list: list[dict], filename: str) -> str:
    filepath = os.path.join("data", filename)
    os.makedirs("data", exist_ok=True)

    df = pd.DataFrame(jobs_list)
    expected_brackets = ["0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", "Unknown"]

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        for bracket in expected_brackets:
            if not df.empty and 'experience_bracket' in df.columns:
                sheet_data = df[df['experience_bracket'] == bracket].sort_values(
                    'resume_match_score', ascending=False
                )
            else:
                sheet_data = pd.DataFrame()

            cols = ["source", "job_title", "company_name", "location", "experience_bracket",
                    "resume_match_score", "matched_skills", "missing_skills", "application_link"]

            if sheet_data.empty:
                pd.DataFrame(columns=cols).to_excel(writer, sheet_name=bracket, index=False)
            else:
                sheet_data.to_excel(writer, sheet_name=bracket, index=False)

    print(f"\nSuccess! Excel report saved to {filepath}")
    return filepath