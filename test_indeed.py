#!/usr/bin/env python3
"""
Test script to verify Indeed API configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_indeed_connection():
    """Test if Indeed API is properly configured and working"""
    api_key = os.getenv("INDEED_API_KEY")
    
    if not api_key:
        print("❌ INDEED_API_KEY not found in environment variables")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Test the API
    url = "https://indeed12.p.rapidapi.com/jobs/search"
    params = {
        "query": "developer software engineer programmer remote",
        "location": "United States",
        "page_id": 1,
        "locality": "us",
        "fromage": 1,  # Last 1 day
        "radius": 50,
        "sort": "date",
        "job_type": "permanent"
    }
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'indeed12.p.rapidapi.com'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('hits') and isinstance(data.get('hits'), list):
            jobs_count = len(data['hits'])
            print(f"✅ Indeed API is working! Found {jobs_count} jobs")
            
            if jobs_count > 0:
                sample_job = data['hits'][0]
                print(f"📋 Sample job: {sample_job.get('title', 'N/A')} at {sample_job.get('company_name', 'N/A')}")
                print(f"📍 Location: {sample_job.get('location', 'N/A')}")
                print(f"⏰ Posted: {sample_job.get('formatted_relative_time', 'N/A')}")
                
                # Check for salary info
                salary_data = sample_job.get('salary', {})
                if salary_data and isinstance(salary_data, dict):
                    salary_min = salary_data.get('min')
                    salary_max = salary_data.get('max')
                    salary_type = salary_data.get('type', '')
                    if salary_min and salary_max:
                        print(f"💰 Salary: ${salary_min:,.0f} - ${salary_max:,.0f} ({salary_type})")
                    elif salary_min:
                        print(f"💰 Salary: ${salary_min:,.0f}+ ({salary_type})")
                
                # Check for job link
                job_link = sample_job.get('link', '')
                if job_link:
                    if not job_link.startswith('http'):
                        job_link = f"https://www.indeed.com{job_link}"
                    print(f"🔗 Job Link: {job_link}")
            
            return True
        else:
            print("❌ API returned empty or invalid data")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Indeed API: {e}")
        return False

if __name__ == "__main__":
    print("Testing Indeed API configuration...")
    test_indeed_connection()
