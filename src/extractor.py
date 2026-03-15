import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def extract_raw_jobs(target_roles, location="India", pages_per_role=2):
    """Thread-safe extractor function. Pulls from Serper API with strict 7-day limit."""
    raw_jobs = []
    url = "https://google.serper.dev/search"

    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    for role in target_roles:
        print(f"--- Searching for: {role} ---")
        for page in range(pages_per_role):
            print(f"  Fetching page {page + 1}...")
            
            payload = json.dumps({
                "q": f"{role} jobs {location}",
                "page": page + 1,
                "tbs": "qdr:w"  # Strict 7-day time filter
            })

            try:
                response = requests.post(url, headers=headers, data=payload)
                response.raise_for_status()
                data = response.json()
                
                jobs_list = data.get("organic", [])
                print(f"  -> Found {len(jobs_list)} raw listings.")
                
                for job in jobs_list:
                    raw_jobs.append({
                        "title": job.get("title", ""),
                        "company": "Unknown", 
                        "location": location,
                        "link": job.get("link", ""),
                        "snippet": job.get("snippet", "") 
                    })
            except Exception as e:
                print(f"  -> Error fetching data for {role}: {e}")
                
    return raw_jobs