import os
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

OUTPUT_COLUMNS = [
    "source",
    "evaluator",
    "job_title",
    "company_name",
    "location",
    "experience_bracket",
    "resume_match_score",
    "matched_skills",
    "missing_skills",
    "application_link",
]


def save_to_excel(jobs_list: list[dict], filename: str) -> str:
    filepath = os.path.join("data", filename)
    os.makedirs("data", exist_ok=True)

    df = pd.DataFrame(jobs_list)

    # Fill any missing columns gracefully
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[OUTPUT_COLUMNS]

    expected_brackets = ["0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", "Unknown"]

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Summary sheet — all qualified jobs sorted by score descending
        summary = df.sort_values("resume_match_score", ascending=False)
        summary.to_excel(writer, sheet_name="ALL (sorted)", index=False)

        # ── Evaluator agreement sheet ─────────────────────────────────────────
        # Jobs confirmed by 2+ evaluators are the highest-confidence picks.
        if not df.empty and "evaluator" in df.columns:
            multi_eval = df[df["evaluator"].str.contains(",", na=False)].sort_values(
                "resume_match_score", ascending=False
            )
        else:
            multi_eval = pd.DataFrame(columns=OUTPUT_COLUMNS)

        multi_eval.to_excel(writer, sheet_name="★ Multi-Evaluator Confirmed", index=False)

        # ── Per-experience-bracket sheets ─────────────────────────────────────
        for bracket in expected_brackets:
            if not df.empty and "experience_bracket" in df.columns:
                sheet_data = df[df["experience_bracket"] == bracket].sort_values(
                    "resume_match_score", ascending=False
                )
            else:
                sheet_data = pd.DataFrame(columns=OUTPUT_COLUMNS)

            if sheet_data.empty:
                pd.DataFrame(columns=OUTPUT_COLUMNS).to_excel(
                    writer, sheet_name=bracket, index=False
                )
            else:
                sheet_data.to_excel(writer, sheet_name=bracket, index=False)

    print(f"\n  Excel report saved → {filepath}")
    return filepath


def send_job_report(excel_path: str):
    sender_email    = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_APP_PASSWORD")
    receiver_email  = os.getenv("RECEIVER_EMAIL")

    if not all([sender_email, sender_password, receiver_email]):
        print("  Email credentials missing — skipping dispatch.")
        return

    print(f"\n[DISPATCH] Sending report to {receiver_email}...")

    msg = MIMEMultipart()
    msg["From"]    = sender_email
    msg["To"]      = receiver_email
    msg["Subject"] = "📊 Daily Data Analyst Job Matches — AI Pipeline Report"

    body = (
        "Hi Sayan,\n\n"
        "Your daily Data Analyst job report is attached.\n\n"
        "Sources    : Serper (Google Search) + Apify (LinkedIn)\n"
        "Evaluators : Gemini 2.0 Flash-Lite · Groq Llama 3.3 70B · "
        "GitHub GPT-4o-mini · Mistral-Small · Together/Qwen2.5-72B\n"
        "Filter     : Score ≥ 60, posted within 7 days, experience ≤ 2 years\n\n"
        "Sheets:\n"
        "  • ALL (sorted)               — every qualified job by match score\n"
        "  • ★ Multi-Evaluator Confirmed — jobs approved by 2+ AI models (highest confidence)\n"
        "  • 0 to 1 yrs                 — fresher / entry-level roles\n"
        "  • 0 to 2 yrs                 — flexible experience range\n"
        "  • 1 to 2 yrs                 — roles requiring at least 1 year\n"
        "  • Unknown                    — no experience requirement stated\n\n"
        "Tip: Start with the ★ Multi-Evaluator Confirmed sheet — "
        "those are the highest-confidence matches.\n\n"
        "Good luck with your applications!\n"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with open(excel_path, "rb") as attachment:
            part = MIMEApplication(attachment.read(), Name=os.path.basename(excel_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(excel_path)}"'
        msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("  [SUCCESS] Email dispatched!")

    except Exception as e:
        print(f"  [ERROR] Email failed: {e}")