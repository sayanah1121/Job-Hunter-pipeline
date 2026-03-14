Markdown
# 🚀 Automated AI Job Hunter Pipeline

An end-to-end Data Engineering ETL pipeline that autonomously scrapes job boards, uses Large Language Models (LLMs) to filter out fake "entry-level" roles, and delivers a categorized daily Excel report directly to your inbox.

## 🎯 The Problem
Finding true entry-level Data Engineering roles is incredibly time-consuming. Job portals are flooded with postings tagged as "Fresher" or "Junior" that actually require 3+ years of experience. Manually filtering through these daily is inefficient and frustrating.

## 💡 The Solution
I engineered an automated ETL pipeline that acts as a personal AI technical recruiter. It runs nightly in the cloud, extracts live job postings, evaluates them against my specific resume and experience level using Claude AI, and delivers highly relevant matches before I wake up.



## 🏗️ Pipeline Architecture (ETL)

* **1. Extract (The Web Scraper):** * Uses Python and the **Serper.dev API** to query real-time Google Jobs data.
    * Iterates through a dynamically generated list of 10+ target roles (e.g., "Azure Data Engineer", "PySpark Developer", "Junior Data Engineer").
* **2. Transform & Evaluate (The AI Engine):**
    * Passes raw job descriptions to **Anthropic's Claude (Haiku)**.
    * **Strict Logic Gate:** The LLM is explicitly prompted to drop any job requiring 2+ years of experience, regardless of the job title.
    * **Match Scoring:** Calculates a 0-100 match score based on alignment with my specific tech stack (Azure, PySpark, Airflow, SQL optimization).
* **3. Load & Dispatch (The Delivery):**
    * Uses **Pandas** and `openpyxl` to format the passing jobs into a multi-sheet `.xlsx` file categorized by experience requirements (0-1 yrs, 0-2 yrs, 1-2 yrs, Unknown/Fresher).
    * Automatically dispatches the report via **SMTP** email.

## 🛠️ Tech Stack & Tools
* **Core:** Python 3.10, Pandas, JSON
* **AI / LLM:** Anthropic API (Claude 3.5 / 4.5 Haiku) for intelligent text parsing and decision-making
* **APIs:** Serper.dev (REST API integration)
* **Cloud Orchestration:** GitHub Actions (CI/CD Cron scheduling)
* **Local Orchestration:** Docker, Apache Airflow (Used during local development and testing)

## 📊 Sample Output
The pipeline generates a daily Excel workbook (`Daily_Data_Engineering_Jobs_YYYYMMDD.xlsx`) containing distinct sheets:
1.  `0 to 1 yrs` 
2.  `0 to 2 yrs` 
3.  `1 to 2 yrs` 
4.  `Unknown / Fresher`

Each row includes the Job Title, Company, Location, AI Match Score, Matched/Missing Skills, and a direct application link.

## ⚙️ How to Run Locally

If you want to clone this project and run it yourself:

1. Clone the repository:
   ```bash
   git clone [https://github.com/sayanah1121/Job-Hunter-pipeline.git](https://github.com/sayanah1121/Job-Hunter-pipeline.git)
   cd Job-Hunter-pipeline
Install dependencies:

Bash
pip install -r requirements.txt
Create a .env file in the root directory and add your keys:

Code snippet
SERPER_API_KEY=your_serper_key
ANTHROPIC_API_KEY=your_anthropic_key
SENDER_EMAIL=your_bot_email@gmail.com
SENDER_APP_PASSWORD=your_gmail_app_password
RECEIVER_EMAIL=your_personal_email@gmail.com
Run the orchestrator:

Bash
python main.py
👨‍💻 About the Author
Built by Sayan Sarkar * Role: Data Engineer / Software Engineer

Background: 2025 B.Tech Graduate | Ex-Bitwise Solutions (FinTech Data Engineering)

Focus: Cloud Data Architecture, Metadata-driven Pipelines, and Process Automation.