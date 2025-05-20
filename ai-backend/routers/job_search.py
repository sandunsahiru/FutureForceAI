import os
import logging
import requests
import json
import re
from typing import Set, Dict, Any, List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Body, Header, Cookie, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import jwt
import motor.motor_asyncio
from bson import ObjectId
from .cv_utils import find_cv_by_id

from .interviewprep import (
    SECRET_KEY,
    openai_client,
    call_openai
)





logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
THEIRSTACK_API_KEY = os.getenv("THEIRSTACK_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzYW5kdW4xMjQ1NkB3ZWJjb2Rvb3MxLnh5eiIsInBlcm1pc3Npb25zIjoidXNlciIsImNyZWF0ZWRfYXQiOiIyMDI1LTA1LTA3VDEyOjU2OjUyLjIwOTAzMSswMDowMCJ9.gwuZTLC23dh7Vf4DSZuUpFg4lebW0Dg_V-nVoDlUIrE")
THEIRSTACK_API_URL = "http://api.theirstack.com/v1/jobs/search"

#eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzYW5kdW4xMjQ1MjNAd2ViY29kb29zMS54eXoiLCJwZXJtaXNzaW9ucyI6InVzZXIiLCJjcmVhdGVkX2F0IjoiMjAyNS0wNS0xOVQwMDo1NDo1My4yNzYyMDMrMDA6MDAifQ.AroxTuVe9XVLf7qW5DKDaKOKyezKCSGDd5MgXnj-Tqg

router = APIRouter()
logger.info("Job Search Router created")


try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    job_searches_col = db["job_searches"]  
    saved_jobs_col = db["saved_jobs"]      
    logger.info("MongoDB connection established for job search")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB for job search: {e}")
    client = None
    db = None
    job_searches_col = None
    saved_jobs_col = None

#
class JobSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    job_type: Optional[str] = "all"
    experience_level: Optional[str] = "all"
    salary_range: Optional[str] = "all"
    date_posted: Optional[str] = "all"
    sort_by: Optional[str] = "relevance"
    page: Optional[int] = 1
    cv_id: Optional[str] = None

class SaveJobRequest(BaseModel):
    job: Dict[str, Any]

class JobApplication(BaseModel):
    job_id: str
    cv_id: Optional[str] = None
    job_url: Optional[str] = None


async def get_token_from_request(request: Request):
    """Extract token from request cookies, headers, or body"""
    token = request.cookies.get("token")
    
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  

    if not token:
        return None
        
    return token

async def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return user_id if valid"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            return None
        return user_id
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None



async def search_jobs_theirstack(request_data: JobSearchRequest) -> Dict[str, Any]:
    """
    Search for jobs using TheirStack API with improved field mapping and error handling
    """
    try:
        logger.info(f"Searching jobs with TheirStack API: {request_data.query} in {request_data.location}")
        
        # Map request parameters to TheirStack API parameters
        date_posted_map = {
            "all": 30,  # Default to 30 days if not specified
            "24h": 1,
            "3d": 3,
            "7d": 7,
            "14d": 14, 
            "30d": 30
        }
        
        # Set up headers with API key
        headers = {
            "Authorization": f"Bearer {THEIRSTACK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Construct search filters for TheirStack API
        payload = {
            "page": request_data.page - 1,
            "limit": 25,
            "include_total_results": True,
            "order_by": [
                {"desc": True, "field": "date_posted"},
                {"desc": True, "field": "discovered_at"}
            ]
        }
        
        # Add keyword search parameters
        if request_data.query:
            # Add job title pattern search
            payload["job_title_pattern_or"] = [request_data.query]
            
            # Also search in job description for more comprehensive results
            payload["job_description_pattern_or"] = [request_data.query]
            payload["job_description_pattern_is_case_insensitive"] = True
        
        # Add location filter
        if request_data.location:
            if request_data.location.lower() == "remote":
                payload["remote"] = True
            else:
                payload["job_location_pattern_or"] = [request_data.location]
        
        # Add date filter
        if request_data.date_posted in date_posted_map:
            payload["posted_at_max_age_days"] = date_posted_map[request_data.date_posted]
        else:
            # Default to 30 days to ensure we get results and not hit API rate limits
            payload["posted_at_max_age_days"] = 30
            
        # Add job type filter
        if request_data.job_type != "all":
            job_type_pattern = request_data.job_type.replace("-", "\\s+")
            if "job_description_pattern_or" not in payload:
                payload["job_description_pattern_or"] = []
            payload["job_description_pattern_or"].append(f"\\b{job_type_pattern}\\b")
        
        # Add experience level filter
        if request_data.experience_level != "all":
            experience_mapping = {
                "entry": ["junior", "entry", "graduate", "entry-level"],
                "mid": ["mid", "intermediate", "mid-level"],
                "senior": ["senior", "expert", "lead", "principal"],
                "executive": ["executive", "director", "head", "chief", "vp", "president"]
            }
            if request_data.experience_level in experience_mapping:
                if "job_title_pattern_or" not in payload:
                    payload["job_title_pattern_or"] = []
                for term in experience_mapping[request_data.experience_level]:
                    payload["job_title_pattern_or"].append(f"\\b{term}\\b")
        
        # Add salary range filter if specified
        if request_data.salary_range != "all":
            salary_ranges = {
                "0-50k": {"min_salary_usd": 0, "max_salary_usd": 50000},
                "50k-75k": {"min_salary_usd": 50000, "max_salary_usd": 75000},
                "75k-100k": {"min_salary_usd": 75000, "max_salary_usd": 100000},
                "100k-150k": {"min_salary_usd": 100000, "max_salary_usd": 150000},
                "150k+": {"min_salary_usd": 150000}
            }
            if request_data.salary_range in salary_ranges:
                range_values = salary_ranges[request_data.salary_range]
                if "min_salary_usd" in range_values:
                    payload["min_salary_usd"] = range_values["min_salary_usd"]
                if "max_salary_usd" in range_values:
                    payload["max_salary_usd"] = range_values["max_salary_usd"]
        
        # Log the payload for debugging
        logger.debug(f"TheirStack API payload: {json.dumps(payload)}")
        
        # Send request to TheirStack API
        response = requests.post(
            THEIRSTACK_API_URL,
            headers=headers,
            json=payload,
            timeout=30  # Add timeout for better error handling
        )
        
        # Check for API errors
        if response.status_code != 200:
            logger.error(f"Error from TheirStack API: {response.status_code} - {response.text}")
            return {
                "jobs": [], 
                "total_pages": 0, 
                "current_page": 1, 
                "error": f"Error from API: {response.status_code}"
            }
        
        # Parse response
        result = response.json()
        
        jobs = []
        if "data" in result:
            for job_item in result["data"]:
                # Extract job ID
                job_id = str(job_item.get("id", str(ObjectId())))
                
                # Extract company information
                company_name = "Unknown Company"
                company_info = None
                company_logo = None
                company_object = job_item.get("company_object")
                
                if company_object:
                    company_name = company_object.get("name", "Unknown Company")
                    company_info = company_object.get("long_description")
                    company_logo = company_object.get("logo")
                else:
                    company = job_item.get("company", "Unknown Company")
                    if isinstance(company, dict):
                        company_name = company.get("name", "Unknown Company")
                    else:
                        company_name = str(company)
                
                # Extract job description
                description = job_item.get("description", "")
                
                # Extract job location information
                location = job_item.get("location", "")
                if not location and "country" in job_item:
                    location = job_item.get("country", "")
                
                # Determine if job is remote
                is_remote = False
                if job_item.get("remote") is True:
                    is_remote = True
                elif isinstance(location, str) and "remote" in location.lower():
                    is_remote = True
                
                # Extract job type
                job_type = "Full-time"
                if job_item.get("employment_statuses") and len(job_item.get("employment_statuses")) > 0:
                    job_type = job_item.get("employment_statuses")[0]
                
                # Format skills
                skills = []
                if job_item.get("technology_slugs"):
                    skills = job_item.get("technology_slugs", [])
                
                # Determine experience level
                experience_level = None
                if job_item.get("seniority"):
                    seniority_mapping = {
                        "junior": "Entry Level",
                        "mid_level": "Mid Level",
                        "senior": "Senior Level",
                        "c_level": "Executive",
                        "staff": "Mid Level"
                    }
                    experience_level = seniority_mapping.get(job_item.get("seniority"), None)
                
                # Extract salary information
                salary = job_item.get("salary_string")
                if not salary:
                    min_salary = job_item.get("min_annual_salary_usd")
                    max_salary = job_item.get("max_annual_salary_usd")
                    if min_salary and max_salary:
                        salary = f"${min_salary:,} - ${max_salary:,} per year"
                    elif min_salary:
                        salary = f"${min_salary:,}+ per year"
                    elif max_salary:
                        salary = f"Up to ${max_salary:,} per year"
                
                # Extract requirements, responsibilities and benefits from description
                extracted_requirements = extract_requirements(description) or []
                extracted_responsibilities = extract_responsibilities(description) or []
                extracted_benefits = extract_benefits(description) or []
                
                # Create structured job object
                processed_job = {
                    "id": job_id,
                    "title": job_item.get("job_title", "Unknown Title"),
                    "company": company_name,
                    "company_logo": company_logo,
                    "location": location or "Unknown Location",
                    "type": job_type,
                    "experience_level": experience_level,
                    "description": description[:500] + "..." if len(description) > 500 else description,
                    "full_description": description,
                    "url": job_item.get("url", ""),
                    "posted_date": job_item.get("date_posted", ""),
                    "discovered_at": job_item.get("discovered_at", ""),
                    "match_score": 75,  # Default score, will be updated if CV is provided
                    "remote": is_remote,
                    "hybrid": job_item.get("hybrid", False),
                    "source": "TheirStack API",
                    "skills": skills,
                    "salary": salary,
                    "company_info": company_info,
                    "requirements": extracted_requirements,
                    "responsibilities": extracted_responsibilities,
                    "benefits": extracted_benefits
                }
                
                jobs.append(processed_job)
        
        # Calculate pagination information
        total_results = result.get("metadata", {}).get("total_results", 0)
        if total_results is None:
            total_results = len(jobs)
            
        total_pages = max(1, (total_results + 24) // 25)  # 25 items per page
        
        return {
            "jobs": jobs,
            "total_pages": total_pages,
            "current_page": request_data.page,
            "total_results": total_results
        }
        
    except requests.RequestException as e:
        logger.error(f"Network error when searching jobs with TheirStack API: {e}")
        return {"jobs": [], "total_pages": 0, "current_page": 1, "error": f"Network error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error searching jobs with TheirStack API: {e}")
        return {"jobs": [], "total_pages": 0, "current_page": 1, "error": str(e)}

def extract_requirements(description: str) -> List[str]:
    """
    Extract job requirements from the job description
    """
    requirements = []
    
    # Common section titles for requirements
    requirement_sections = [
        r"(?:Requirements|Qualifications|What You'll Need|What You Need|Skills Required|Required Skills|Required Experience|Must Have|Required Qualifications|Key Requirements|The ideal candidate|We're looking for)s?:?\s*",
    ]
    
    # Try to extract requirements section
    for section_pattern in requirement_sections:
        section_match = re.search(f"{section_pattern}(.*?)(?:\n\n|\n#|\n\*\*|$)", description, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(1).strip()
            
            # Extract bullet points or numbered list items
            items = re.findall(r'(?:^|\n)(?:\*|\-|\d+\.|\•|\+)\s*(.*?)(?:\n|$)', section_text)
            
            if items:
                requirements.extend([item.strip() for item in items if item.strip()])
            else:
                # If no bullet points found, split by newlines
                lines = [line.strip() for line in section_text.split('\n') if line.strip()]
                requirements.extend(lines)
            
            break  # Stop after finding the first matching section
    
    # Limit to reasonable number of requirements
    return requirements[:10]



def extract_responsibilities(description: str) -> List[str]:
    """
    Extract job responsibilities from the job description
    """
    responsibilities = []
    
    # Common section titles for responsibilities
    responsibility_sections = [
        r"(?:Responsibilities|Duties|What You'll Do|What You Will Do|Role Description|Job Description|In this role|The Role|Key Responsibilities|Day to day|Day-to-day|Your Role)s?:?\s*",
    ]
    
    # Try to extract responsibilities section
    for section_pattern in responsibility_sections:
        section_match = re.search(f"{section_pattern}(.*?)(?:\n\n|\n#|\n\*\*|$)", description, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(1).strip()
            
            # Extract bullet points or numbered list items
            items = re.findall(r'(?:^|\n)(?:\*|\-|\d+\.|\•|\+)\s*(.*?)(?:\n|$)', section_text)
            
            if items:
                responsibilities.extend([item.strip() for item in items if item.strip()])
            else:
                # If no bullet points found, split by newlines
                lines = [line.strip() for line in section_text.split('\n') if line.strip()]
                responsibilities.extend(lines)
            
            break  # Stop after finding the first matching section
    
    # Limit to reasonable number of responsibilities
    return responsibilities[:10]


def extract_benefits(description: str) -> List[str]:
    """
    Extract job benefits from the job description
    """
    benefits = []
    
    # Common section titles for benefits
    benefits_sections = [
        r"(?:Benefits|Perks|What We Offer|We Offer|Compensation|Compensation & Benefits|Why Join Us|What's in it for you|Why work with us)s?:?\s*",
    ]
    
    # Try to extract benefits section
    for section_pattern in benefits_sections:
        section_match = re.search(f"{section_pattern}(.*?)(?:\n\n|\n#|\n\*\*|$)", description, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(1).strip()
            
            # Extract bullet points or numbered list items
            items = re.findall(r'(?:^|\n)(?:\*|\-|\d+\.|\•|\+)\s*(.*?)(?:\n|$)', section_text)
            
            if items:
                benefits.extend([item.strip() for item in items if item.strip()])
            else:
                # If no bullet points found, split by newlines
                lines = [line.strip() for line in section_text.split('\n') if line.strip()]
                benefits.extend(lines)
            
            break  # Stop after finding the first matching section
    
    # Limit to reasonable number of benefits
    return benefits[:10]

def calculate_match_score(cv_text: str, job: Dict[str, Any]) -> int:
    """
    Calculate a match score between a CV and job details with improved algorithm
    """
    try:
        if not cv_text:
            return 70  # Default score if no CV
        
        cv_text_lower = cv_text.lower()
        
        # Skills matching
        skills_score = 0
        skills_weight = 0.4
        matched_skills = 0
        job_skills = job.get("skills", [])
        
        if job_skills:
            for skill in job_skills:
                skill_lower = skill.lower()
                # Check for exact matches or with common prefixes/suffixes
                if (f" {skill_lower} " in f" {cv_text_lower} " or 
                    f" {skill_lower}," in f" {cv_text_lower} " or 
                    f" {skill_lower}." in f" {cv_text_lower} " or 
                    f" {skill_lower}\n" in f" {cv_text_lower} "):
                    matched_skills += 1
            
            if len(job_skills) > 0:
                skills_score = (matched_skills / len(job_skills)) * 100 * skills_weight
        
        # Title matching
        title_score = 0
        title_weight = 0.3
        job_title = job.get("title", "").lower()
        
        if job_title:
            # Extract key terms from the job title
            title_terms = set(re.findall(r'\b\w+\b', job_title))
            matched_terms = 0
            
            for term in title_terms:
                if len(term) >= 3:  # Only consider meaningful terms
                    if re.search(r'\b' + re.escape(term) + r'\b', cv_text_lower):
                        matched_terms += 1
            
            if len(title_terms) > 0:
                title_score = (matched_terms / len(title_terms)) * 100 * title_weight
        
        # Experience level matching
        experience_score = 0
        experience_weight = 0.2
        experience_level = job.get("experience_level", "").lower()
        
        if experience_level:
            experience_keywords = {
                "entry level": ["intern", "graduate", "entry", "junior", "trainee"],
                "mid level": ["mid", "intermediate", "associate"],
                "senior level": ["senior", "lead", "principal", "staff", "expert"],
                "executive": ["executive", "director", "head", "chief", "vp", "president"]
            }
            
            for level, keywords in experience_keywords.items():
                if level in experience_level:
                    for keyword in keywords:
                        if re.search(r'\b' + re.escape(keyword) + r'\b', cv_text_lower):
                            experience_score = 100 * experience_weight
                            break
        
        # Job description keyword matching
        description_score = 0
        description_weight = 0.1
        description = job.get("full_description", "").lower()
        
        if description:
            # Extract important keywords from job description
            description_words = set(re.findall(r'\b\w{4,}\b', description))
            important_words = [word for word in description_words 
                               if word not in common_stop_words()
                               and len(word) >= 4]
            
            # Count the top 20 most frequent words
            word_freq = {}
            for word in important_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]
            matched_keywords = sum(1 for word, _ in top_keywords 
                                   if re.search(r'\b' + re.escape(word) + r'\b', cv_text_lower))
            
            if top_keywords:
                description_score = (matched_keywords / len(top_keywords)) * 100 * description_weight
        
        # Calculate final match score
        total_score = skills_score + title_score + experience_score + description_score
        
        # Add base score and adjust final score to be between 60-95
        final_score = 60 + (total_score * 0.35)
        final_score = min(95, max(60, final_score))
        
        return int(final_score)
        
    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        return 70 


def common_stop_words() -> Set[str]:
    """
    Return common stop words to exclude from keyword matching
    """
    return {
        "able", "about", "above", "according", "across", "after", "again", 
        "against", "also", "always", "among", "analysis", "another", "any", 
        "anyone", "anything", "around", "because", "become", "been", "before", 
        "behind", "being", "below", "between", "both", "business", "came", 
        "cannot", "come", "company", "could", "days", "dear", "does", "doing", 
        "done", "during", "each", "either", "else", "ever", "every", "experience", 
        "first", "from", "further", "good", "great", "have", "having", "here", 
        "however", "into", "just", "know", "knowledge", "like", "look", "made", 
        "make", "many", "more", "most", "much", "must", "need", "next", "only", 
        "other", "over", "part", "people", "please", "position", "review", "role", 
        "same", "skill", "skills", "some", "such", "team", "than", "that", "their", 
        "them", "then", "there", "these", "they", "this", "those", "through", 
        "time", "today", "under", "until", "very", "want", "well", "were", "what", 
        "when", "where", "which", "while", "will", "with", "within", "without", 
        "work", "working", "would", "your"
    }


async def get_cv_text(cv_id: str, user_id: str) -> Optional[str]:
    """
    Get CV text from database
    """
    try:
        if not cv_id or not user_id or db is None:
            return None
            
      
        cv_document = await find_cv_by_id(db, cv_id, user_id)
        
        if not cv_document:
            logger.warning(f"CV not found: {cv_id}")
            return None
            
        cv_text = cv_document.get("extractedText")
        
        if not cv_text:
            cv_text = cv_document.get("content")
            
        return cv_text
    except Exception as e:
        logger.error(f"Error getting CV text: {e}")
        return None




# API Routes
@router.post("/api/job-search")
async def search_jobs(
    request: Request,
    data: JobSearchRequest
):
    """
    Search for jobs based on criteria
    """
    logger.info(f"Job search request: {data.query} in {data.location}")
    
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    cv_text = None
    if data.cv_id:
        cv_text = await get_cv_text(data.cv_id, user_id)
        if cv_text:
            logger.info(f"Retrieved CV text for job matching")
    
    # Search for jobs using TheirStack API
    job_results = await search_jobs_theirstack(data)
    
    # Calculate match scores if CV is provided
    if cv_text and job_results.get("jobs"):
        for job in job_results["jobs"]:
            # Calculate match score with full job details
            job["match_score"] = calculate_match_score(cv_text, job)
        
        # Sort jobs by match score
        job_results["jobs"] = sorted(
            job_results["jobs"],
            key=lambda x: x.get("match_score", 0),
            reverse=True
        )
    
    # Save search history
    if job_searches_col is not None:
        try:
            search_record = {
                "user_id": user_id,
                "query": data.query,
                "location": data.location,
                "created_at": datetime.utcnow(),
                "job_count": len(job_results.get("jobs", [])),
                "cv_id": data.cv_id
            }
            
            await job_searches_col.insert_one(search_record)
            logger.info(f"Saved job search to history: {data.query}")
        except Exception as db_err:
            logger.error(f"Error saving search history: {db_err}")
    
    return job_results


@router.post("/api/user/saved-jobs")
async def save_job(
    request: Request,
    data: SaveJobRequest
):
    """
    Save a job to user's saved jobs
    """
    logger.info(f"Saving job: {data.job.get('title', 'Unknown job')}")

    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )

    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    if saved_jobs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        existing_job = await saved_jobs_col.find_one({
            "user_id": user_id,
            "job.id": data.job.get("id")
        })
        
        if existing_job:
            logger.info(f"Job already saved: {data.job.get('id')}")
            return {"status": "success", "detail": "Job already saved"}

        job_record = {
            "user_id": user_id,
            "job": data.job,
            "saved_at": datetime.utcnow()
        }
        
        result = await saved_jobs_col.insert_one(job_record)
        logger.info(f"Job saved with ID: {result.inserted_id}")
        
        return {"status": "success", "detail": "Job saved successfully"}
    except Exception as e:
        logger.error(f"Error saving job: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error saving job: {str(e)}"}
        )

@router.delete("/api/user/saved-jobs/{job_id}")
async def unsave_job(
    request: Request,
    job_id: str
):
    """
    Remove a job from user's saved jobs
    """
    logger.info(f"Removing saved job: {job_id}")

    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    

    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    if saved_jobs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        result = await saved_jobs_col.delete_one({
            "user_id": user_id,
            "job.id": job_id
        })
        
        if result.deleted_count > 0:
            logger.info(f"Job removed from saved jobs: {job_id}")
            return {"status": "success", "detail": "Job removed from saved jobs"}
        else:
            logger.warning(f"Job not found in saved jobs: {job_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Job not found in saved jobs"}
            )
    except Exception as e:
        logger.error(f"Error removing saved job: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error removing saved job: {str(e)}"}
        )

@router.get("/api/user/saved-jobs")
async def get_saved_jobs(
    request: Request
):
    """
    Get user's saved jobs
    """
    logger.info("Getting saved jobs")
    
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    if saved_jobs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        cursor = saved_jobs_col.find({"user_id": user_id}).sort("saved_at", -1)
        saved_jobs = await cursor.to_list(length=100)
        
        jobs = []
        for item in saved_jobs:
            job = item.get("job", {})
            job["saved_at"] = item.get("saved_at", datetime.utcnow()).isoformat()
            jobs.append(job)
        
        return {"jobs": jobs}
    except Exception as e:
        logger.error(f"Error getting saved jobs: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error getting saved jobs: {str(e)}"}
        )

@router.post("/api/job-apply")
async def apply_for_job(
    request: Request,
    data: JobApplication
):
    """
    Start job application process
    """
    logger.info(f"Applying for job: {data.job_id}")
    
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    if not data.cv_id:
        logger.warning("No CV provided for job application")
        return JSONResponse(
            status_code=400,
            content={"detail": "CV is required for job application"}
        )
    
    cv_document = await find_cv_by_id(db, data.cv_id, user_id)
    if not cv_document:
        logger.warning(f"CV not found: {data.cv_id}")
        return JSONResponse(
            status_code=404,
            content={"detail": "CV not found"}
        )
    
    if not data.job_url:
        logger.warning("No job URL provided for application")
        return JSONResponse(
            status_code=400,
            content={"detail": "Job URL is required for application"}
        )
    
    try:
        if job_searches_col is not None:
            application_record = {
                "user_id": user_id,
                "job_id": data.job_id,
                "cv_id": data.cv_id,
                "job_url": data.job_url,
                "applied_at": datetime.utcnow(),
                "status": "started"
            }
            
            await job_searches_col.insert_one(application_record)
            logger.info(f"Logged job application: {data.job_id}")
        
        return {"status": "success", "detail": "Job application started", "job_url": data.job_url}
    except Exception as e:
        logger.error(f"Error starting job application: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error starting job application: {str(e)}"}
        )

@router.post("/api/generate-job-notification")
async def generate_job_notification(
    request: Request,
    data: JobSearchRequest
):
    """
    Generate and save a job search notification/alert
    """
    logger.info(f"Setting up job notification for: {data.query}")
    
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    if job_searches_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        notification = {
            "user_id": user_id,
            "query": data.query,
            "location": data.location,
            "job_type": data.job_type,
            "experience_level": data.experience_level,
            "created_at": datetime.utcnow(),
            "frequency": "daily",  
            "active": True
        }
        
        result = await job_searches_col.insert_one(notification)
        logger.info(f"Job notification created: {result.inserted_id}")
        
        return {
            "status": "success", 
            "detail": "Job notification created",
            "notification_id": str(result.inserted_id)
        }
    except Exception as e:
        logger.error(f"Error creating job notification: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error creating job notification: {str(e)}"}
        )

def setup_job_search_routes(app):
    """
    Set up job search routes in the main FastAPI app
    """
    app.include_router(router, tags=["job-search"])