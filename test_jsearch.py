#!/usr/bin/env python3
"""
Test script to verify JSearch API configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_jsearch_connection():
    """Test if JSearch API is properly configured and working"""
    api_key = os.getenv("JSEARCH_API_KEY")
    
    if not api_key:
        print("❌ JSEARCH_API_KEY not found in environment variables")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Test the API
    url = "https://jsearch.p.rapidapi.com/search"
    params = {
        "query": "developer software engineer",
        "page": 1,
        "num_pages": 1,
        "country": "us",
        "date_posted": "today"
    }
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'jsearch.p.rapidapi.com'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'OK':
            jobs_count = len(data.get('data', []))
            print(f"✅ JSearch API is working! Found {jobs_count} jobs")
            
            if jobs_count > 0:
                sample_job = data['data'][0]
                print(f"📋 Sample job: {sample_job.get('job_title')} at {sample_job.get('employer_name')}")
                print(f"🏠 Remote: {'Yes' if sample_job.get('job_is_remote') else 'No'}")
                if sample_job.get('job_min_salary'):
                    print(f"💰 Salary: ${sample_job.get('job_min_salary'):,} - ${sample_job.get('job_max_salary', 'N/A'):,}")
            
            return True
        else:
            print(f"❌ API returned error: {data}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to JSearch API: {e}")
        return False

if __name__ == "__main__":
    print("Testing JSearch API configuration...")
    test_jsearch_connection()
