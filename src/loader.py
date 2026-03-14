import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

def send_job_report(excel_filepath):
    if not all([SENDER_EMAIL, SENDER_APP_PASSWORD, RECEIVER_EMAIL]):
        print("CRITICAL ERROR: Email credentials missing in .env file.")
        return False

    if not os.path.exists(excel_filepath):
        print(f"Error: Could not find the file {excel_filepath} to attach.")
        return False

    print(f"\nPreparing to send Excel report to {RECEIVER_EMAIL}...")

    msg = EmailMessage()
    msg['Subject'] = f" Daily AI Job Matches: {os.path.basename(excel_filepath)}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    body = """
    Hello!
    
    Your automated data engineering pipeline has successfully finished running. 
    The AI Evaluator has categorized the latest job postings into distinct experience sheets (0-1 yrs, 0-2 yrs, 1-2 yrs, and Unknown).
    
    Open the attached Excel workbook to review your top matches.
    
    Happy hunting!
    """
    msg.set_content(body)

    try:
        with open(excel_filepath, 'rb') as f:
            file_data = f.read()
            file_name = os.path.basename(excel_filepath)
            
        msg.add_attachment(
            file_data, 
            maintype='application', 
            subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            filename=file_name
        )
    except Exception as e:
        print(f"Failed to read attachment: {e}")
        return False

    try:
        print("  -> Connecting to Gmail SMTP server...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            smtp.send_message(msg)
            
        print("  -> [SUCCESS] Excel report dispatched successfully!")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print("  -> [FAIL] Authentication Error: Check your App Password.")
        return False
    except Exception as e:
        print(f"  -> [FAIL] Failed to send email: {e}")
        return False

if __name__ == "__main__":
    test_file = os.path.join("data", "Daily_Data_Engineering_Jobs.xlsx")
    print("Initiating Pipeline: Phase 3 (Load/Email)\n" + "="*40)
    send_job_report(test_file)