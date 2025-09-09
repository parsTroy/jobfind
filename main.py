# main.py
import os
import time
import sqlite3
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

# --- Configuration (from env) ---
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # your telegram chat id
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "120"))  # default every 2 minutes
COUNTRY = os.getenv("COUNTRY", "us")
REMOTE_ONLY = os.getenv("REMOTE_ONLY", "1")  # filter remote roles if available

# JSearch API Configuration
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
JSEARCH_HOST = "jsearch.p.rapidapi.com"

# Active Jobs API Configuration
ACTIVE_JOBS_API_KEY = os.getenv("ACTIVE_JOBS_API_KEY")
ACTIVE_JOBS_HOST = "active-jobs-db.p.rapidapi.com"

# LinkedIn Jobs API Configuration
LINKEDIN_JOBS_API_KEY = os.getenv("LINKEDIN_JOBS_API_KEY")
LINKEDIN_JOBS_HOST = "linkedin-job-search-api.p.rapidapi.com"

# Glassdoor API Configuration
GLASSDOOR_API_KEY = os.getenv("GLASSDOOR_API_KEY")
GLASSDOOR_HOST = "glassdoor-real-time.p.rapidapi.com"

# Indeed API Configuration
INDEED_API_KEY = os.getenv("INDEED_API_KEY")
INDEED_HOST = "indeed12.p.rapidapi.com"

# Keywords from resume (extendable)
KEYWORDS = [
    "full stack","full-stack","fullstack","frontend","backend","react","typescript",
    "next.js","nextjs","tailwind","shadcn","c#",".net","dotnet","blazor","asp.net",
    "postgres","postgresql","supabase","aws","python","c++","tRPC","prisma",
    "javascript","node.js","nodejs","vue","angular","svelte","swift","kotlin",
    "docker","kubernetes","microservices","api","rest","graphql","mongodb",
    "redis","elasticsearch","machine learning","ai","data science","devops",
    "git","github","gitlab","ci/cd","jenkins","terraform","cloud","azure",
    "gcp","serverless","lambda","kubernetes","k8s","agile","scrum"
]

# Experience cap in years
MAX_YEARS_EXP = int(os.getenv("MAX_YEARS_EXP", "5"))

# DB for seen jobs
DB_PATH = os.getenv("DB_PATH", "/app/seen_jobs.db")

# --- DB helpers ---
def init_db():
    # Ensure the directory exists
    import os
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS seen_jobs (
        id TEXT PRIMARY KEY,
        source TEXT,
        title TEXT,
        company TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def is_seen(job_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job_id,))
    r = cur.fetchone()
    conn.close()
    return bool(r)

def mark_seen(job_id, source, title, company, created_at):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO seen_jobs (id, source, title, company, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, source, title, company, created_at))
    conn.commit()
    conn.close()

# --- Notification (Telegram) ---
def notify_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured; skipping notify. Message:", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("Failed to send telegram:", e)

# --- Utility: check recent (<= 1 hour) ---
def is_recent_iso(timestr):
    # Try parse common ISO formats
    try:
        # attempt RFC3339 / ISO format
        dt = datetime.fromisoformat(timestr.replace("Z", "+00:00"))
    except Exception:
        try:
            dt = datetime.strptime(timestr, "%a, %d %b %Y %H:%M:%S %Z")
        except Exception:
            return False
    now = datetime.now(timezone.utc)
    return (now - dt) <= timedelta(hours=1)

def is_recent_epoch(epoch_seconds):
    now = datetime.now(timezone.utc)
    dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    return (now - dt) <= timedelta(hours=1)

# --- Matching logic ---
def match_keywords(text):
    if not text:
        return False
    s = text.lower()
    for kw in KEYWORDS:
        if kw.lower() in s:
            return True
    return False

# --- Fetch RemoteOK ---
def fetch_remoteok():
    # RemoteOK returns JSON array
    try:
        r = requests.get("https://remoteok.com/api", timeout=10, headers={"User-Agent": "job-bot/1.0"})
        data = r.json()
    except Exception as e:
        print("RemoteOK fetch error:", e)
        return []

    jobs = []
    for item in data:
        # skip the first meta object if present
        if isinstance(item, dict) and 'id' not in item:
            continue
        job_id = f"remoteok_{item.get('id')}"
        # created_at sometimes as epoch or string
        epoch = item.get('epoch')
        is_recent = False
        if epoch:
            is_recent = is_recent_epoch(epoch)
        else:
            created = item.get('date') or item.get('created_at')
            if created:
                is_recent = is_recent_iso(created)
        if not is_recent:
            continue
        title = item.get('position') or item.get('title')
        company = item.get('company')
        tags = " ".join(item.get('tags', []))
        desc = item.get('description') or ""
        combined = " ".join(filter(None, [title, company, tags, desc]))
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "remoteok",
                "title": title,
                "company": company,
                "url": item.get('url'),
                "created_at": datetime.utcfromtimestamp(item.get('epoch')).isoformat() if item.get('epoch') else item.get('date'),
                "raw": item
            })
    return jobs

# --- Fetch JSearch Jobs ---
def fetch_jsearch_jobs():
    """Fetch jobs from JSearch API (RapidAPI)"""
    if not JSEARCH_API_KEY:
        print("JSearch API key not configured")
        return []
    
    try:
        # JSearch API parameters
        params = {
            "query": "developer software engineer programmer remote",
            "page": 1,
            "num_pages": 1,
            "country": "us",  # Focus on US
            "date_posted": "today"  # Only today's jobs
        }
        
        url = f"https://{JSEARCH_HOST}/search"
        headers = {
            'x-rapidapi-key': JSEARCH_API_KEY,
            'x-rapidapi-host': JSEARCH_HOST
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("JSearch API fetch error:", e)
        return []

    jobs = []
    for item in data.get('data', []):
        job_id = f"jsearch_{item.get('job_id')}"
        
        # Check if job is recent (within last 24 hours)
        posted_at = item.get('job_posted_at_datetime_utc')
        if not posted_at:
            continue
            
        # Parse the datetime and check if recent
        try:
            job_date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - job_date) > timedelta(hours=24):
                continue
        except:
            continue
            
        title = item.get('job_title')
        company = item.get('employer_name')
        description = item.get('job_description', "")
        location = item.get('job_location', "")
        is_remote = item.get('job_is_remote', False)
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, description, location]))
        
        # Additional filtering for remote jobs if REMOTE_ONLY is set
        if REMOTE_ONLY == "1" and not is_remote:
            continue
            
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "jsearch",
                "title": title,
                "company": company,
                "url": item.get('job_apply_link'),
                "created_at": posted_at,
                "location": location,
                "is_remote": is_remote,
                "salary_min": item.get('job_min_salary'),
                "salary_max": item.get('job_max_salary'),
                "employment_type": item.get('job_employment_type_text'),
                "raw": item
            })
    
    return jobs

# --- Fetch Active Jobs ---
def fetch_active_jobs():
    """Fetch jobs from Active Jobs API (RapidAPI)"""
    if not ACTIVE_JOBS_API_KEY:
        print("Active Jobs API key not configured")
        return []
    
    try:
        # Active Jobs API parameters - using hourly endpoint with better filtering
        url = f"https://{ACTIVE_JOBS_HOST}/active-ats-1h"
        params = {
            "offset": 0,
            "title_filter": "developer OR engineer OR programmer OR software",
            "location_filter": "United States OR Canada OR Remote OR US OR America",
            "description_type": "text"
        }
        headers = {
            'x-rapidapi-key': ACTIVE_JOBS_API_KEY,
            'x-rapidapi-host': ACTIVE_JOBS_HOST
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Active Jobs API fetch error:", e)
        return []

    jobs = []
    for item in data:
        if not isinstance(item, dict):
            continue
            
        job_id = f"active_{item.get('id')}"
        
        # Check if job is recent (within last hour)
        posted_at = item.get('date_posted')
        if not posted_at:
            continue
            
        # Parse the datetime and check if recent
        try:
            job_date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - job_date) > timedelta(hours=1):
                continue
        except:
            continue
            
        title = item.get('title')
        company = item.get('organization')
        location = item.get('locations_derived', [])
        location_str = ', '.join(location) if location else ""
        is_remote = item.get('remote_derived', False)
        
        # Parse salary if available
        salary_raw = item.get('salary_raw')
        salary_min = None
        salary_max = None
        if salary_raw and isinstance(salary_raw, str):
            try:
                import json
                salary_data = json.loads(salary_raw)
                if 'value' in salary_data and 'minValue' in salary_data['value']:
                    salary_min = salary_data['value']['minValue']
                if 'value' in salary_data and 'maxValue' in salary_data['value']:
                    salary_max = salary_data['value']['maxValue']
            except:
                pass
        
        # Get employment type
        employment_type = item.get('employment_type', [])
        employment_type_str = ', '.join(employment_type) if employment_type else ""
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, location_str]))
        
        # Additional filtering for remote jobs if REMOTE_ONLY is set
        if REMOTE_ONLY == "1" and not is_remote:
            continue
            
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "active_jobs",
                "title": title,
                "company": company,
                "url": item.get('url'),
                "created_at": posted_at,
                "location": location_str,
                "is_remote": is_remote,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "employment_type": employment_type_str,
                "raw": item
            })
    
    return jobs

# --- Fetch LinkedIn Jobs ---
def fetch_linkedin_jobs():
    """Fetch jobs from LinkedIn Jobs API (RapidAPI)"""
    if not LINKEDIN_JOBS_API_KEY:
        print("LinkedIn Jobs API key not configured")
        return []
    
    try:
        # LinkedIn Jobs API parameters - using 24h endpoint with proper filtering
        url = f"https://{LINKEDIN_JOBS_HOST}/active-jb-24h"
        params = {
            "limit": 50,
            "offset": 0,
            "title_filter": "developer OR engineer OR programmer OR software",
            "location_filter": "United States OR United Kingdom OR Canada OR Remote"
        }
        headers = {
            'x-rapidapi-key': LINKEDIN_JOBS_API_KEY,
            'x-rapidapi-host': LINKEDIN_JOBS_HOST
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("LinkedIn Jobs API fetch error:", e)
        return []

    jobs = []
    for item in data:
        if not isinstance(item, dict):
            continue
            
        job_id = f"linkedin_{item.get('id')}"
        
        # Check if job is recent (within last 24 hours)
        posted_at = item.get('date_posted')
        if not posted_at:
            continue
            
        # Parse the datetime and check if recent
        try:
            job_date = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - job_date) > timedelta(hours=24):
                continue
        except:
            continue
            
        title = item.get('title')
        company = item.get('organization')
        location = item.get('locations_derived', [])
        location_str = ', '.join(location) if location else ""
        is_remote = item.get('remote_derived', False)
        
        # Parse salary if available
        salary_raw = item.get('salary_raw')
        salary_min = None
        salary_max = None
        if salary_raw and isinstance(salary_raw, dict):
            try:
                if 'value' in salary_raw and 'minValue' in salary_raw['value']:
                    salary_min = salary_raw['value']['minValue']
                if 'value' in salary_raw and 'maxValue' in salary_raw['value']:
                    salary_max = salary_raw['value']['maxValue']
            except:
                pass
        
        # Get employment type
        employment_type = item.get('employment_type', [])
        employment_type_str = ', '.join(employment_type) if employment_type else ""
        
        # Get company details
        company_size = item.get('linkedin_org_size', '')
        company_industry = item.get('linkedin_org_industry', '')
        company_employees = item.get('linkedin_org_employees', '')
        
        # Get recruiter info
        recruiter_name = item.get('recruiter_name', '')
        recruiter_title = item.get('recruiter_title', '')
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, location_str, company_industry]))
        
        # Additional filtering for remote jobs if REMOTE_ONLY is set
        if REMOTE_ONLY == "1" and not is_remote:
            continue
            
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "linkedin",
                "title": title,
                "company": company,
                "url": item.get('url'),
                "created_at": posted_at,
                "location": location_str,
                "is_remote": is_remote,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "employment_type": employment_type_str,
                "company_size": company_size,
                "company_industry": company_industry,
                "company_employees": company_employees,
                "recruiter_name": recruiter_name,
                "recruiter_title": recruiter_title,
                "raw": item
            })
    
    return jobs

# --- Fetch Glassdoor Jobs ---
def fetch_glassdoor_jobs():
    """Fetch jobs from Glassdoor API (RapidAPI)"""
    if not GLASSDOOR_API_KEY:
        print("Glassdoor API key not configured")
        return []
    
    try:
        # Glassdoor API parameters - using job search endpoint
        url = f"https://{GLASSDOOR_HOST}/jobs/search"
        params = {
            "query": "developer software engineer programmer remote",
            "location": "United States"
        }
        headers = {
            'x-rapidapi-key': GLASSDOOR_API_KEY,
            'x-rapidapi-host': GLASSDOOR_HOST
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Glassdoor API fetch error:", e)
        return []

    jobs = []
    # Parse the correct response structure
    job_list = data.get('data', {}).get('jobListings', []) if isinstance(data.get('data'), dict) else []
    
    for item in job_list:
        if not isinstance(item, dict):
            continue
            
        # Navigate the nested structure
        jobview = item.get('jobview', {})
        if not jobview:
            continue
            
        job_data = jobview.get('job', {})
        header_data = jobview.get('header', {})
        
        job_id = f"glassdoor_{job_data.get('listingId', '')}"
        
        # Check if job is recent (within last 7 days)
        age_in_days = header_data.get('ageInDays', 999)
        if age_in_days > 7:  # Only jobs from last week
            continue
            
        title = job_data.get('jobTitleText', '')
        company = header_data.get('employerNameFromSearch', '')
        location = header_data.get('locationName', '')
        
        # Get salary information
        salary_min = None
        salary_max = None
        pay_data = header_data.get('payPeriodAdjustedPay', {})
        if pay_data and isinstance(pay_data, dict):
            salary_min = pay_data.get('p10')
            salary_max = pay_data.get('p90')
        
        # Get job type from Indeed attributes
        job_type = ""
        indeed_attr = header_data.get('indeedJobAttribute', {})
        if indeed_attr and isinstance(indeed_attr, dict):
            extracted_attrs = indeed_attr.get('extractedJobAttributes', [])
            if extracted_attrs:
                job_type = extracted_attrs[0].get('value', '')
        
        # Get company rating
        rating = header_data.get('rating', 0)
        
        # Get Easy Apply status
        easy_apply = header_data.get('easyApply', False)
        
        # Get job view URL
        job_view_url = header_data.get('jobViewUrl', '')
        if job_view_url and not job_view_url.startswith('http'):
            job_view_url = f"https://www.glassdoor.com{job_view_url}"
        
        # Get urgency signal (new jobs)
        urgency = header_data.get('urgencySignal', {})
        is_urgent = urgency.get('labelKey') == 'search-jobs.urgent-jobs.new' if urgency else False
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, location]))
        
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "glassdoor",
                "title": title,
                "company": company,
                "url": job_view_url,
                "created_at": datetime.now(timezone.utc).isoformat(),  # Use current time since we filtered by age
                "location": location,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "job_type": job_type,
                "company_rating": rating,
                "easy_apply": easy_apply,
                "is_urgent": is_urgent,
                "age_days": age_in_days,
                "raw": item
            })
    
    return jobs

# --- Fetch Glassdoor Jobs Canada ---
def fetch_glassdoor_jobs_canada():
    """Fetch jobs from Glassdoor API for Canada (RapidAPI)"""
    if not GLASSDOOR_API_KEY:
        print("Glassdoor API key not configured")
        return []
    
    try:
        # Glassdoor API parameters - using job search endpoint for Canada
        url = f"https://{GLASSDOOR_HOST}/jobs/search"
        params = {
            "query": "developer software engineer programmer remote",
            "location": "Canada"
        }
        headers = {
            'x-rapidapi-key': GLASSDOOR_API_KEY,
            'x-rapidapi-host': GLASSDOOR_HOST
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Glassdoor Canada API fetch error:", e)
        return []

    jobs = []
    # Parse the correct response structure
    job_list = data.get('data', {}).get('jobListings', []) if isinstance(data.get('data'), dict) else []
    
    for item in job_list:
        if not isinstance(item, dict):
            continue
            
        # Navigate the nested structure
        jobview = item.get('jobview', {})
        if not jobview:
            continue
            
        job_data = jobview.get('job', {})
        header_data = jobview.get('header', {})
        
        job_id = f"glassdoor_ca_{job_data.get('listingId', '')}"
        
        # Check if job is recent (within last 7 days)
        age_in_days = header_data.get('ageInDays', 999)
        if age_in_days > 7:  # Only jobs from last week
            continue
            
        title = job_data.get('jobTitleText', '')
        company = header_data.get('employerNameFromSearch', '')
        location = header_data.get('locationName', '')
        
        # Get salary information
        salary_min = None
        salary_max = None
        pay_data = header_data.get('payPeriodAdjustedPay', {})
        if pay_data and isinstance(pay_data, dict):
            salary_min = pay_data.get('p10')
            salary_max = pay_data.get('p90')
        
        # Get job type from Indeed attributes
        job_type = ""
        indeed_attr = header_data.get('indeedJobAttribute', {})
        if indeed_attr and isinstance(indeed_attr, dict):
            extracted_attrs = indeed_attr.get('extractedJobAttributes', [])
            if extracted_attrs:
                job_type = extracted_attrs[0].get('value', '')
        
        # Get company rating
        rating = header_data.get('rating', 0)
        
        # Get Easy Apply status
        easy_apply = header_data.get('easyApply', False)
        
        # Get job view URL
        job_view_url = header_data.get('jobViewUrl', '')
        if job_view_url and not job_view_url.startswith('http'):
            job_view_url = f"https://www.glassdoor.com{job_view_url}"
        
        # Get urgency signal (new jobs)
        urgency = header_data.get('urgencySignal', {})
        is_urgent = urgency.get('labelKey') == 'search-jobs.urgent-jobs.new' if urgency else False
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, location]))
        
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "glassdoor_ca",
                "title": title,
                "company": company,
                "url": job_view_url,
                "created_at": datetime.now(timezone.utc).isoformat(),  # Use current time since we filtered by age
                "location": location,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "job_type": job_type,
                "company_rating": rating,
                "easy_apply": easy_apply,
                "is_urgent": is_urgent,
                "age_days": age_in_days,
                "raw": item
            })
    
    return jobs

# --- Fetch Indeed Jobs ---
def fetch_indeed_jobs():
    """Fetch jobs from Indeed API (RapidAPI)"""
    if not INDEED_API_KEY:
        print("Indeed API key not configured")
        return []
    
    try:
        # Indeed API parameters - try simpler query first
        url = f"https://{INDEED_HOST}/jobs/search"
        params = {
            "query": "developer",
            "location": "United States",
            "page_id": 1,
            "locality": "us",
            "fromage": 1,  # Last 1 day
            "radius": 50,
            "sort": "date"
        }
        headers = {
            'x-rapidapi-key': INDEED_API_KEY,
            'x-rapidapi-host': INDEED_HOST
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Indeed API fetch error:", e)
        return []

    jobs = []
    job_list = data.get('hits', [])
    
    for item in job_list:
        if not isinstance(item, dict):
            continue
            
        job_id = f"indeed_{item.get('id')}"
        
        # Check if job is recent (within last hour)
        pub_date_ts = item.get('pub_date_ts_milli')
        if not pub_date_ts:
            continue
            
        # Convert timestamp to datetime and check if recent
        try:
            job_date = datetime.fromtimestamp(pub_date_ts / 1000, tz=timezone.utc)
            if (datetime.now(timezone.utc) - job_date) > timedelta(hours=1):
                continue
        except:
            continue
            
        title = item.get('title', '')
        company = item.get('company_name', '')
        location = item.get('location', '')
        
        # Get salary information
        salary_data = item.get('salary', {})
        salary_min = None
        salary_max = None
        salary_type = None
        if salary_data and isinstance(salary_data, dict):
            salary_min = salary_data.get('min')
            salary_max = salary_data.get('max')
            salary_type = salary_data.get('type', '')
        
        # Get relative time posted
        relative_time = item.get('formatted_relative_time', '')
        
        # Get job link
        job_link = item.get('link', '')
        if job_link and not job_link.startswith('http'):
            job_link = f"https://www.indeed.com{job_link}"
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, location]))
        
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "indeed",
                "title": title,
                "company": company,
                "url": job_link,
                "created_at": job_date.isoformat(),
                "location": location,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_type": salary_type,
                "relative_time": relative_time,
                "raw": item
            })
    
    return jobs

# --- Fetch Authentic Jobs ---
def fetch_authentic_jobs():
    """Fetch jobs from Authentic Jobs API (no auth required)"""
    try:
        # Authentic Jobs API
        url = "https://authenticjobs.com/api/"
        params = {
            "method": "aj.jobs.search",
            "keywords": "developer,programmer,engineer",
            "perpage": 50,
            "format": "json"
        }
        r = requests.get(url, params=params, timeout=10, headers={"User-Agent": "job-bot/1.0"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Authentic Jobs fetch error:", e)
        return []

    jobs = []
    for item in data.get('listings', {}).get('listing', []):
        if not isinstance(item, dict):
            continue
            
        job_id = f"authentic_{item.get('id')}"
        
        # Check if job is recent (within last hour)
        created_at = item.get('post_date')
        if not created_at or not is_recent_iso(created_at):
            continue
            
        title = item.get('title')
        company = item.get('company', {}).get('name', '')
        description = item.get('description', "")
        location = item.get('location', "")
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, description, location]))
        
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "authentic",
                "title": title,
                "company": company,
                "url": item.get('url'),
                "created_at": created_at,
                "location": location,
                "raw": item
            })
    
    return jobs

# --- Fetch Jobs from Remote.co ---
def fetch_remote_co_jobs():
    """Fetch jobs from Remote.co (scraping approach)"""
    try:
        # Remote.co doesn't have a public API, so we'll use a simple approach
        # For now, let's return an empty list and focus on working APIs
        print("Remote.co integration not implemented yet")
        return []
    except Exception as e:
        print("Remote.co fetch error:", e)
        return []

# --- Fetch AngelList/Wellfound Jobs ---
def fetch_angellist_jobs():
    """Fetch jobs from AngelList/Wellfound (no auth required)"""
    try:
        # AngelList/Wellfound API - search for remote developer jobs
        url = "https://api.angel.co/1/jobs"
        params = {
            "keywords": "developer,programmer,engineer",
            "remote": "true",
            "per_page": 50
        }
        r = requests.get(url, params=params, timeout=10, headers={"User-Agent": "job-bot/1.0"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("AngelList fetch error:", e)
        return []

    jobs = []
    for item in data.get('jobs', []):
        job_id = f"angellist_{item.get('id')}"
        
        # Check if job is recent (within last hour)
        created_at = item.get('created_at')
        if not created_at or not is_recent_iso(created_at):
            continue
            
        title = item.get('title')
        company = item.get('startup', {}).get('name', '')
        description = item.get('description', "")
        location = item.get('location', "")
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, description, location]))
        
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "angellist",
                "title": title,
                "company": company,
                "url": item.get('angellist_url'),
                "created_at": created_at,
                "location": location,
                "raw": item
            })
    
    return jobs

# --- Fetch Stack Overflow Jobs ---
def fetch_stackoverflow_jobs():
    """Fetch jobs from Stack Overflow Jobs RSS feed"""
    try:
        # Stack Overflow Jobs RSS feed
        rss_url = "https://stackoverflow.com/jobs/feed"
        feed = feedparser.parse(rss_url)
    except Exception as e:
        print("Stack Overflow Jobs fetch error:", e)
        return []

    jobs = []
    for entry in feed.entries:
        # Extract job ID from the link
        job_id = f"stackoverflow_{hash(entry.link) % 1000000}"
        
        # Check if job is recent (within last hour)
        published = entry.get('published_parsed')
        if not published:
            continue
            
        # Convert to datetime and check if recent
        pub_date = datetime(*published[:6], tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - pub_date) > timedelta(hours=1):
            continue
            
        title = entry.get('title', '')
        company = entry.get('author', '')
        description = entry.get('summary', '')
        
        # Combine all text for keyword matching
        combined = " ".join(filter(None, [title, company, description]))
        
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "stackoverflow",
                "title": title,
                "company": company,
                "url": entry.get('link'),
                "created_at": pub_date.isoformat(),
                "raw": entry
            })
    
    return jobs

# --- Fetch Adzuna ---
def fetch_adzuna():
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": "software developer",
        "where": "United States",
        "results_per_page": 20,
        "sort_by": "date"
    }
    url = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search/1?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Adzuna fetch error:", e)
        return []
    jobs = []
    for item in data.get("results", []):
        job_id = "adzuna_" + item.get("id", "")
        created = item.get("created")  # ISO string
        if not created or not is_recent_iso(created):
            continue
        title = item.get("title")
        company = item.get("company", {}).get("display_name")
        desc = item.get("description", "")
        combined = " ".join(filter(None, [title, company, desc, item.get("category", {}).get("label", "")]))
        if match_keywords(combined):
            jobs.append({
                "id": job_id,
                "source": "adzuna",
                "title": title,
                "company": company,
                "url": item.get("redirect_url") or item.get("company", {}).get("url"),
                "created_at": created,
                "raw": item
            })
    return jobs

# --- Main loop ---
def check_and_notify():
    print(f"[{datetime.now().isoformat()}] Checking for new jobs...")
    
    # Check if Telegram is configured
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  WARNING: Telegram not configured. Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID environment variables.")
        print("   Jobs will be found but notifications will not be sent.")
    
    # Fetch from all sources
    try:
        remoteok_jobs = fetch_remoteok()
        print(f"RemoteOK: Found {len(remoteok_jobs)} matching jobs")
    except Exception as e:
        print(f"Error fetching RemoteOK jobs: {e}")
        remoteok_jobs = []
    
    try:
        jsearch_jobs = fetch_jsearch_jobs()
        print(f"JSearch API: Found {len(jsearch_jobs)} matching jobs")
    except Exception as e:
        print(f"Error fetching JSearch jobs: {e}")
        jsearch_jobs = []
    
    # LinkedIn Jobs - Skip if API key not configured
    if LINKEDIN_JOBS_API_KEY:
        try:
            linkedin_jobs = fetch_linkedin_jobs()
            print(f"LinkedIn Jobs: Found {len(linkedin_jobs)} matching jobs")
        except Exception as e:
            print(f"Error fetching LinkedIn Jobs: {e}")
            linkedin_jobs = []
    else:
        print("LinkedIn Jobs API: Skipped (no API key configured)")
        linkedin_jobs = []
    
    # Active Jobs - Skip if API key not configured
    if ACTIVE_JOBS_API_KEY:
        try:
            active_jobs = fetch_active_jobs()
            print(f"Active Jobs API: Found {len(active_jobs)} matching jobs")
        except Exception as e:
            print(f"Error fetching Active Jobs: {e}")
            active_jobs = []
    else:
        print("Active Jobs API: Skipped (no API key configured)")
        active_jobs = []
    
    # Indeed Jobs - Skip if API key not configured
    if INDEED_API_KEY:
        try:
            indeed_jobs = fetch_indeed_jobs()
            print(f"Indeed Jobs: Found {len(indeed_jobs)} matching jobs")
        except Exception as e:
            print(f"Error fetching Indeed Jobs: {e}")
            indeed_jobs = []
    else:
        print("Indeed Jobs API: Skipped (no API key configured)")
        indeed_jobs = []
    
    try:
        glassdoor_jobs = fetch_glassdoor_jobs()
        print(f"Glassdoor Jobs (US): Found {len(glassdoor_jobs)} matching jobs")
    except Exception as e:
        print(f"Error fetching Glassdoor Jobs (US): {e}")
        glassdoor_jobs = []
    
    try:
        glassdoor_ca_jobs = fetch_glassdoor_jobs_canada()
        print(f"Glassdoor Jobs (CA): Found {len(glassdoor_ca_jobs)} matching jobs")
    except Exception as e:
        print(f"Error fetching Glassdoor Jobs (CA): {e}")
        glassdoor_ca_jobs = []
    
    try:
        stackoverflow_jobs = fetch_stackoverflow_jobs()
        print(f"Stack Overflow Jobs: Found {len(stackoverflow_jobs)} matching jobs")
    except Exception as e:
        print(f"Error fetching Stack Overflow Jobs: {e}")
        stackoverflow_jobs = []
    
    adzuna_jobs = fetch_adzuna()
    found = remoteok_jobs + jsearch_jobs + linkedin_jobs + active_jobs + indeed_jobs + glassdoor_jobs + glassdoor_ca_jobs + stackoverflow_jobs + adzuna_jobs
    print(f"Total matches: {len(found)}")
    
    new_jobs = 0
    for job in found:
        if is_seen(job["id"]):
            continue
        
        new_jobs += 1
        # mark seen and notify
        mark_seen(job["id"], job["source"], job.get("title"), job.get("company"), job.get("created_at"))
        
        # Format the notification message
        url_text = f"\n🔗 {job.get('url')}" if job.get('url') else ""
        
        # Add salary info if available (from JSearch)
        salary_text = ""
        if job.get('salary_min') and job.get('salary_max'):
            salary_text = f"\n💰 Salary: ${job.get('salary_min'):,} - ${job.get('salary_max'):,}"
        elif job.get('salary_min'):
            salary_text = f"\n💰 Salary: ${job.get('salary_min'):,}+"
        
        # Add remote status if available
        remote_text = ""
        if job.get('is_remote') is not None:
            remote_text = f"\n🏠 Remote: {'Yes' if job.get('is_remote') else 'No'}"
        
        # Add employment type if available
        employment_text = ""
        if job.get('employment_type'):
            employment_text = f"\n⏰ Type: {job.get('employment_type')}"
        
        # Add LinkedIn-specific company details
        company_details = ""
        if job.get('source') == 'linkedin':
            if job.get('company_size'):
                company_details += f"\n🏢 Company Size: {job.get('company_size')}"
            if job.get('company_industry'):
                company_details += f"\n🏭 Industry: {job.get('company_industry')}"
            if job.get('company_employees'):
                company_details += f"\n👥 Employees: {job.get('company_employees')}"
            if job.get('recruiter_name'):
                recruiter_text = f"Recruiter: {job.get('recruiter_name')}"
                if job.get('recruiter_title'):
                    recruiter_text += f" ({job.get('recruiter_title')})"
                company_details += f"\n👤 {recruiter_text}"
        
        # Add Glassdoor-specific company details
        elif job.get('source') in ['glassdoor', 'glassdoor_ca']:
            if job.get('company_rating') and job.get('company_rating') > 0:
                company_details += f"\n⭐ Company Rating: {job.get('company_rating')}/5"
            if job.get('job_type'):
                company_details += f"\n⏰ Job Type: {job.get('job_type')}"
            if job.get('easy_apply'):
                company_details += f"\n✅ Easy Apply: Yes"
            if job.get('is_urgent'):
                company_details += f"\n🚨 Urgent: New Job"
            if job.get('age_days') is not None:
                if job.get('age_days') == 0:
                    company_details += f"\n📅 Posted: Today"
                elif job.get('age_days') == 1:
                    company_details += f"\n📅 Posted: Yesterday"
                else:
                    company_details += f"\n📅 Posted: {job.get('age_days')} days ago"
            if job.get('source') == 'glassdoor_ca':
                company_details += f"\n🇨🇦 Location: Canada"
        
        # Add Indeed-specific details
        elif job.get('source') == 'indeed':
            if job.get('relative_time'):
                company_details += f"\n⏰ Posted: {job.get('relative_time')}"
            if job.get('salary_type'):
                company_details += f"\n💰 Pay Type: {job.get('salary_type')}"
        
        text = f"🔔 New job match!\n\n📋 {job.get('title')}\n🏢 {job.get('company')}\n📅 Posted: {job.get('created_at')}\n🌐 Source: {job.get('source')}{salary_text}{remote_text}{employment_text}{company_details}{url_text}"
        
        notify_telegram(text)
        print(f"✅ Notified for: {job['id']}")
    
    if new_jobs == 0:
        print("No new jobs found this round.")
    else:
        print(f"🎉 Found {new_jobs} new job(s)!")

if __name__ == "__main__":
    init_db()
    # simple loop; run forever in the container
    while True:
        try:
            check_and_notify()
        except Exception as e:
            print("Main loop error:", e)
        time.sleep(POLL_SECONDS)
