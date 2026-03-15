import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def extract_raw_jobs(target_roles, location="India", pages_per_role=2):
    raw_jobs = []
    
    # Using the dedicated jobs endpoint
    url = "https://google.serper.dev/jobs"

    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    for role in target_roles:
        print(f"--- Searching for: {role} ---")
        for page in range(pages_per_role):
            print(f"  Fetching page {page + 1}...")
            
            # THE FIX: Added the 'tbs' parameter for strict 7-day filtering (qdr:w = past week)
            payload = json.dumps({
                "q": f"{role} {location}",
                "page": page + 1,
                "tbs": "qdr:w" 
            })

            try:
                response = requests.post(url, headers=headers, data=payload)
                response.raise_for_status()
                data = response.json()
                
                # Serper's /jobs endpoint returns a 'jobs' array
                jobs_list = data.get("jobs", [])
                print(f"  -> Found {len(jobs_list)} raw listings.")
                
                for job in jobs_list:
                    raw_jobs.append({
                        "title": job.get("title", ""),
                        "company": job.get("companyName", ""),
                        "location": job.get("location", ""),
                        "link": job.get("url", ""),
                        "snippet": job.get("description", "") 
                    })
            except Exception as e:
                print(f"  -> Error fetching data for {role}: {e}")
                
    return raw_jobs