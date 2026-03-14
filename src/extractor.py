import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables from the hidden .env file
load_dotenv()

# Securely fetch the API key
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SEARCH_ENDPOINT = "https://google.serper.dev/search"

def extract_raw_jobs(target_roles, location="India", pages_per_role=2):
    """
    Fetches raw job listings from Google Jobs via Serper.dev for multiple roles.
    """
    if not SERPER_API_KEY:
        raise ValueError("CRITICAL ERROR: SERPER_API_KEY not found. Check your .env file.")

    all_raw_jobs = []
    
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    print(f"Starting extraction for roles: {', '.join(target_roles)} in {location}...\n")

    for role in target_roles:
        print(f"--- Searching for: {role} ---")
        
        for page in range(pages_per_role):
            offset = page * 10 
            
            # Using exact boolean search operators to enforce the experience limits
            query = f'"{role}" (fresher OR "0 years experience" OR "entry level") jobs in {location}'
            
            payload = json.dumps({
                "q": query,
                "gl": "in", # Country: India
                "hl": "en", # Language: English
                "start": offset
            })
            
            try:
                print(f"  Fetching page {page + 1}...")
                response = requests.post(SEARCH_ENDPOINT, headers=headers, data=payload)
                response.raise_for_status()
                data = response.json()
                
                # Append the raw job listings if they exist
                if "organic" in data:
                    all_raw_jobs.extend(data["organic"])
                    print(f"  -> Found {len(data['organic'])} raw listings on this page.")
                
                # Polite delay to respect API rate limits
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                print(f"  -> API Error on page {page + 1}: {e}")
                break

    # Remove potential duplicates based on the job link
    unique_jobs = {job.get('link'): job for job in all_raw_jobs if job.get('link')}
    return list(unique_jobs.values())

if __name__ == "__main__":
    # Test the extraction layer
    roles_to_search = ["Data Engineer", "Junior Data Engineer", "ETL Developer", "Azure Data Engineer"]
    
    print("Initiating Pipeline: Phase 1 (Extraction)\n" + "="*40)
    raw_data = extract_raw_jobs(target_roles=roles_to_search, pages_per_role=2)
    
    print("="*40)
    print(f"Extraction Complete. Total unique raw jobs pulled: {len(raw_data)}")
    
    if raw_data:
        print("\nSample of the first extracted job:")
        print(json.dumps(raw_data[0], indent=2))