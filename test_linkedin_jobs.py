#!/usr/bin/env python3
"""
Test script to verify LinkedIn Jobs API configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_linkedin_jobs_connection():
    """Test if LinkedIn Jobs API is properly configured and working"""
    api_key = os.getenv("LINKEDIN_JOBS_API_KEY")
    
    if not api_key:
        print("❌ LINKEDIN_JOBS_API_KEY not found in environment variables")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Test the API - using 24h endpoint with proper filtering
    url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-24h"
    params = {
        "limit": 10,
        "offset": 0,
        "title_filter": "developer OR engineer OR programmer OR software",
        "location_filter": "United States OR United Kingdom OR Canada OR Remote"
    }
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'linkedin-job-search-api.p.rapidapi.com'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            jobs_count = len(data)
            print(f"✅ LinkedIn Jobs API is working! Found {jobs_count} jobs")
            
            if jobs_count > 0:
                sample_job = data[0]
                print(f"📋 Sample job: {sample_job.get('title')} at {sample_job.get('organization')}")
                print(f"🏠 Remote: {'Yes' if sample_job.get('remote_derived') else 'No'}")
                print(f"📍 Location: {', '.join(sample_job.get('locations_derived', []))}")
                print(f"🏭 Industry: {sample_job.get('linkedin_org_industry', 'N/A')}")
                print(f"🏢 Company Size: {sample_job.get('linkedin_org_size', 'N/A')}")
                
                # Check for salary info
                salary_raw = sample_job.get('salary_raw')
                if salary_raw and isinstance(salary_raw, dict):
                    try:
                        if 'value' in salary_raw and 'minValue' in salary_raw['value']:
                            min_sal = salary_raw['value']['minValue']
                            max_sal = salary_raw['value'].get('maxValue', 'N/A')
                            print(f"💰 Salary: ${min_sal:,} - ${max_sal:,}")
                    except:
                        print("💰 Salary: Available but couldn't parse")
                
                # Check for recruiter info
                recruiter_name = sample_job.get('recruiter_name')
                if recruiter_name:
                    recruiter_title = sample_job.get('recruiter_title', '')
                    print(f"👤 Recruiter: {recruiter_name} ({recruiter_title})" if recruiter_title else f"👤 Recruiter: {recruiter_name}")
            
            return True
        else:
            print("❌ API returned empty or invalid data")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to LinkedIn Jobs API: {e}")
        return False

if __name__ == "__main__":
    print("Testing LinkedIn Jobs API configuration...")
    test_linkedin_jobs_connection()
