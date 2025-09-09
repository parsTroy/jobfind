#!/usr/bin/env python3
"""
Test script to verify Glassdoor API configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_glassdoor_connection():
    """Test if Glassdoor API is properly configured and working"""
    api_key = os.getenv("GLASSDOOR_API_KEY")
    
    if not api_key:
        print("❌ GLASSDOOR_API_KEY not found in environment variables")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Test the API
    url = "https://glassdoor-real-time.p.rapidapi.com/jobs/search"
    params = {
        "query": "developer software engineer programmer remote",
        "location": "United States"
    }
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'glassdoor-real-time.p.rapidapi.com'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') and data.get('data'):
            jobs_data = data.get('data', {})
            jobs_list = jobs_data.get('jobListings', []) if isinstance(jobs_data, dict) else []
            
            if isinstance(jobs_list, list) and len(jobs_list) > 0:
                jobs_count = len(jobs_list)
                print(f"✅ Glassdoor API is working! Found {jobs_count} jobs")
                
                if jobs_count > 0:
                    sample_job = jobs_list[0]
                    jobview = sample_job.get('jobview', {})
                    job_data = jobview.get('job', {})
                    header_data = jobview.get('header', {})
                    
                    print(f"📋 Sample job: {job_data.get('jobTitleText', 'N/A')} at {header_data.get('employerNameFromSearch', 'N/A')}")
                    print(f"📍 Location: {header_data.get('locationName', 'N/A')}")
                    print(f"⭐ Company Rating: {header_data.get('rating', 'N/A')}/5")
                    print(f"⏰ Age: {header_data.get('ageInDays', 'N/A')} days")
                    print(f"✅ Easy Apply: {'Yes' if header_data.get('easyApply') else 'No'}")
                    
                    # Check for salary info
                    pay_data = header_data.get('payPeriodAdjustedPay', {})
                    if pay_data and isinstance(pay_data, dict):
                        p10 = pay_data.get('p10')
                        p90 = pay_data.get('p90')
                        if p10 and p90:
                            print(f"💰 Salary Range: ${p10:,.0f} - ${p90:,.0f}")
                    
                    # Check for job type
                    indeed_attr = header_data.get('indeedJobAttribute', {})
                    if indeed_attr and isinstance(indeed_attr, dict):
                        extracted_attrs = indeed_attr.get('extractedJobAttributes', [])
                        if extracted_attrs:
                            job_type = extracted_attrs[0].get('value', '')
                            print(f"⏰ Job Type: {job_type}")
                    
                    # Check for urgency
                    urgency = header_data.get('urgencySignal', {})
                    if urgency and urgency.get('labelKey') == 'search-jobs.urgent-jobs.new':
                        print(f"🚨 Urgent: New Job")
                
                return True
            else:
                print("❌ API returned empty job list")
                return False
        else:
            print(f"❌ API returned error: {data}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Glassdoor API: {e}")
        return False

if __name__ == "__main__":
    print("Testing Glassdoor API configuration...")
    test_glassdoor_connection()
