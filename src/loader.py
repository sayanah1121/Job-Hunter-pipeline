import os
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

# All columns in final output — order matters for Excel readability
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

    # Fill missing columns gracefully (e.g. Serper branches don't have 'evaluator')
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[OUTPUT_COLUMNS]

    expected_brackets = ["0 to 1 yrs", "0 to 2 yrs", "1 to 2 yrs", "Unknown"]

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        for bracket in expected_brackets:
            if not df.empty and 'experience_bracket' in df.columns:
                sheet_data = df[df['experience_bracket'] == bracket].sort_values(
                    'resume_match_score', ascending=False
                )
            else:
                sheet_data = pd.DataFrame(columns=OUTPUT_COLUMNS)

            if sheet_data.empty:
                pd.DataFrame(columns=OUTPUT_COLUMNS).to_excel(
                    writer, sheet_name=bracket, index=False
                )
            else:
                sheet_data.to_excel(writer, sheet_name=bracket, index=False)

    print(f"\nSuccess! Excel report saved to {filepath}")
    return filepath


def send_job_report(excel_path: str):
    sender_email    = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_APP_PASSWORD")
    receiver_email  = os.getenv("RECEIVER_EMAIL")

    if not all([sender_email, sender_password, receiver_email]):
        print("Email credentials missing. Skipping email dispatch.")
        return

    print(f"\n[DISPATCH] Sending report to {receiver_email}...")

    msg = MIMEMultipart()
    msg['From']    = sender_email
    msg['To']      = receiver_email
    msg['Subject'] = "🚀 Daily AI Job Matches (Data Engineering)"

    body = (
        "Attached is your daily automated job report.\n\n"
        "Sources  : Serper (Google Search) + Apify (LinkedIn)\n"
        "Evaluators: Gemini · Groq · GitHub Models (GPT-4o-mini)\n"
        "Sheets   : Organised by experience bracket, sorted by match score.\n"
    )
    msg.attach(MIMEText(body, 'plain'))

    try:
        with open(excel_path, "rb") as attachment:
            part = MIMEApplication(attachment.read(), Name=os.path.basename(excel_path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(excel_path)}"'
        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("  -> [SUCCESS] Email dispatched successfully!")

    except Exception as e:
        print(f"  -> [ERROR] Failed to send email: {e}")