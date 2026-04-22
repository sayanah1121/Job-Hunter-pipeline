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
Current Role: Trainee Data Engineer at Bitwise Solutions (BFSI domain, ~8 months experience)
Target Roles: Data Engineer, Junior Data Engineer, Associate Data Engineer, ETL Developer, Azure Data Engineer, PySpark Developer

=== TECHNICAL STACK ===
Cloud & Storage    : Azure Data Factory (ADF), ADLS Gen2, Azure Databricks, Snowflake, GCP
Streaming          : Apache Kafka, Apache Zookeeper, Spark Streaming
Batch/Orchestration: Apache Airflow, Apache Spark / PySpark, dbt, Ab Initio GDE
DevOps & Infra     : Docker, GitHub Actions, Git
Languages          : Python (strong), SQL (strong)
Databases          : PostgreSQL

=== PROJECTS ===
1. Bitwise Solutions (Production BFSI ETL): SQL optimisation, duplicate detection, TWS scheduling.
2. LiveKart (Portfolio): Kafka + Spark Streaming real-time e-commerce pipeline, Dockerized.
3. AI Job Hunter Pipeline (Portfolio): Serper API → Claude Haiku → Airflow + GitHub Actions.

=== EXPERIENCE LEVEL ===
0–1 year. Suitable for 0–2 year roles. HARD REJECT if minimum requirement is 2+ years stated explicitly.
"""

SYSTEM_PROMPT = f"""
You are a precise Technical Recruiter AI evaluating job listings for a specific Data Engineer candidate.
Your evaluations directly affect which jobs the candidate applies to — accuracy is critical.

{CANDIDATE_PROFILE}

=== EVALUATION RULES ===

STEP 1 — VALIDITY CHECK (mark is_valid: false if ANY condition is true):
  a) Snippet is an aggregate/category page (e.g. "100+ jobs on LinkedIn").
  b) Job was posted MORE than 7 days ago. Signals: "30+ days ago", "1 month ago", "2 weeks ago".
     NOTE: "1 week ago", "5 days ago", "today", "3 days ago" are VALID.
  c) Job EXPLICITLY requires MINIMUM 2 or more years (e.g. "minimum 2 years", "3-5 years required").
     NOTE: Ranges like "0-2 years", "1-2 years" are VALID.

STEP 2 — EXPERIENCE BRACKET (assign EXACTLY one):
  "0 to 1 yrs"  → fresher/entry-level/trainee or 0-1 year stated
  "0 to 2 yrs"  → 0-2 years or 1-2 years range
  "1 to 2 yrs"  → explicitly 1-2 years minimum
  "Unknown"     → no experience requirement mentioned

STEP 3 — RESUME MATCH SCORE (0–100 integer):
  SCORING RUBRIC (add points):
  +20 if core stack matches (Spark/PySpark, Kafka, Airflow, ADF, ADLS)
  +15 if SQL / Python explicitly required
  +15 if cloud platform matches (Azure preferred, GCP acceptable)
  +10 if BFSI/banking/fintech domain mentioned
  +10 if ETL/ELT pipeline design is the core requirement
  +10 if streaming/real-time experience required (Kafka, Spark Streaming)
  +10 if orchestration tools match (Airflow, ADF pipelines)
  +5  if containerisation / DevOps mentioned (Docker, GitHub Actions)
  +5  if data modelling / dbt / warehousing mentioned

  DEDUCTIONS:
  -20 if requires technologies candidate has zero exposure to (Hadoop, Hive, Scala, Java-only roles)
  -15 if role is primarily Data Analyst, Data Scientist, or BI (not engineering)
  -10 if requires 5+ years even if stated as "preferred"

  Final score must be between 0 and 100.

STEP 4 — SKILL EXTRACTION:
  matched_skills: Comma-separated skills from the job that the candidate HAS (max 8).
  missing_skills: Comma-separated skills from the job that the candidate LACKS (max 8).

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object. No markdown. No explanation.

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


def evaluate_job_groq(job_snippet: str, job_title: str) -> dict | None:
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Job Title: {job_title}\nJob Description Snippet:\n{job_snippet}"}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        raw_text = response.choices[0].message.content
        return json.loads(raw_text)

    except Exception as e:
        print(f"  [GROQ] -> Evaluation Error for '{job_title}': {e}")
        return None


def process_with_groq(raw_jobs_list: list[dict]) -> list[dict]:
    qualified_jobs = []
    print(f"\n[GROQ] Evaluating {len(raw_jobs_list)} raw jobs...")

    for job in raw_jobs_list:
        title    = job.get("title",    "Unknown Title")
        company  = job.get("company",  "Unknown Company")
        location = job.get("location", "India")
        link     = job.get("link",     "")
        snippet  = job.get("snippet",  "")
        source   = job.get("source",   "serper")

        if not snippet:
            continue

        evaluation = evaluate_job_groq(snippet, title)

        if not evaluation:
            continue

        if not evaluation.get("is_valid"):
            reason = evaluation.get("invalid_reason", "")
            print(f"  [SKIP]  {title} | Reason: {reason or 'failed validity check'}")
            continue

        score   = evaluation.get("resume_match_score", 0)
        bracket = evaluation.get("experience_bracket", "Unknown")

        if score >= 60:
            print(f"  [GROQ MATCH] {title} @ {company} | Bracket: {bracket} | Score: {score}")
            qualified_jobs.append({
                "source":             source,
                "job_title":          title,
                "company_name":       company,
                "location":           location,
                "experience_bracket": bracket,
                "resume_match_score": score,
                "matched_skills":     evaluation.get("matched_skills", ""),
                "missing_skills":     evaluation.get("missing_skills", ""),
                "application_link":   link,
            })
        else:
            print(f"  [LOW]   {title} @ {company} | Score: {score} (below 60, skipping)")

    print(f"[GROQ] {len(qualified_jobs)} jobs qualified out of {len(raw_jobs_list)} evaluated.")
    return qualified_jobs