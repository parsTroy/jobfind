#!/usr/bin/env python3
"""
Test script to verify Active Jobs API configuration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_active_jobs_connection():
    """Test if Active Jobs API is properly configured and working"""
    api_key = os.getenv("ACTIVE_JOBS_API_KEY")
    
    if not api_key:
        print("❌ ACTIVE_JOBS_API_KEY not found in environment variables")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Test the API - using hourly endpoint with better filtering
    url = "https://active-jobs-db.p.rapidapi.com/active-ats-1h"
    params = {
        "offset": 0,
        "title_filter": "developer OR engineer OR programmer OR software",
        "location_filter": "United States OR United Kingdom OR Canada OR Remote",
        "description_type": "text"
    }
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': 'active-jobs-db.p.rapidapi.com'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            jobs_count = len(data)
            print(f"✅ Active Jobs API is working! Found {jobs_count} jobs")
            
            if jobs_count > 0:
                sample_job = data[0]
                print(f"📋 Sample job: {sample_job.get('title')} at {sample_job.get('organization')}")
                print(f"🏠 Remote: {'Yes' if sample_job.get('remote_derived') else 'No'}")
                print(f"📍 Location: {', '.join(sample_job.get('locations_derived', []))}")
                
                # Check for salary info
                salary_raw = sample_job.get('salary_raw')
                if salary_raw:
                    try:
                        import json
                        salary_data = json.loads(salary_raw)
                        if 'value' in salary_data and 'minValue' in salary_data['value']:
                            min_sal = salary_data['value']['minValue']
                            max_sal = salary_data['value'].get('maxValue', 'N/A')
                            print(f"💰 Salary: ${min_sal:,} - ${max_sal:,}")
                    except:
                        print("💰 Salary: Available but couldn't parse")
            
            return True
        else:
            print("❌ API returned empty or invalid data")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Active Jobs API: {e}")
        return False

if __name__ == "__main__":
    print("Testing Active Jobs API configuration...")
    test_active_jobs_connection()
