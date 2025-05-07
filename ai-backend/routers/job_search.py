# Create a new file in your ai-backend/routers directory
# Save as job_search.py

import os
import logging
import requests
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Body, Header, Cookie, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import jwt
import motor.motor_asyncio
from bson import ObjectId

# Import shared utilities and connections
from .interviewprep import (
    SECRET_KEY,
    openai_client,
    call_openai
)

# Import CV utilities if needed
from .cv_utils import find_cv_by_id

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure environment variables
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
THEIRSTACK_API_KEY = os.getenv("THEIRSTACK_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzYW5kdW4xMjQ1NkB3ZWJjb2Rvb3MxLnh5eiIsInBlcm1pc3Npb25zIjoidXNlciIsImNyZWF0ZWRfYXQiOiIyMDI1LTA1LTA3VDEyOjU2OjUyLjIwOTAzMSswMDowMCJ9.gwuZTLC23dh7Vf4DSZuUpFg4lebW0Dg_V-nVoDlUIrE")
THEIRSTACK_API_URL = "http://api.theirstack.com/v1/jobs/search"

# Create router
router = APIRouter()
logger.info("Job Search Router created")

# Get database reference
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    job_searches_col = db["job_searches"]  # Collection for job search history
    saved_jobs_col = db["saved_jobs"]      # Collection for saved jobs
    logger.info("MongoDB connection established for job search")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB for job search: {e}")
    client = None
    db = None
    job_searches_col = None
    saved_jobs_col = None

# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------

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

# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------

async def get_token_from_request(request: Request):
    """Extract token from request cookies, headers, or body"""
    # Try to get token from cookies
    token = request.cookies.get("token")
    
    # Try Authorization header if no cookie
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
    
    # No valid token found
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
    Search for jobs using TheirStack API
    """
    try:
        logger.info(f"Searching jobs with TheirStack API: {request_data.query} in {request_data.location}")
        
        # Map request parameters to TheirStack API parameters
        job_type_map = {
            "all": None,
            "full-time": "fulltime",
            "part-time": "parttime",
            "contract": "contractor",
            "internship": "internship",
            "temporary": "temporary"
        }

        date_posted_map = {
            "all": None,
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
        
        # Construct payload for TheirStack API
        payload = {
            "page": request_data.page - 1,  # TheirStack uses 0-indexed pages
            "limit": 25,  # Default items per page
            "job_title_pattern_or": [request_data.query] if request_data.query else [],
            "job_location_pattern_or": [request_data.location] if request_data.location else []
        }
        
        # Add date filter
        if request_data.date_posted in date_posted_map and date_posted_map[request_data.date_posted]:
            payload["posted_at_max_age_days"] = date_posted_map[request_data.date_posted]
        else:
            # Default to last 7 days if no specific date filter
            payload["posted_at_max_age_days"] = 7
            
        # Add job type filter
        if request_data.job_type in job_type_map and job_type_map[request_data.job_type]:
            payload["job_type"] = job_type_map[request_data.job_type]
            
        # Send request to TheirStack API
        response = requests.post(
            THEIRSTACK_API_URL,
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Error from TheirStack API: {response.status_code} - {response.text}")
            return {"jobs": [], "total_pages": 0, "current_page": 1, "error": f"Error from API: {response.status_code}"}
        
        # Parse response
        result = response.json()
        
        # Transform TheirStack response to our expected format
        jobs = []
        if "data" in result:
            for job_item in result["data"]:
                # Generate a unique job ID if not provided
                job_id = job_item.get("id", str(ObjectId()))
                
                # Format company info
                company = job_item.get("company", "Unknown Company")
                if isinstance(company, dict):
                    company_name = company.get("name", "Unknown Company")
                else:
                    company_name = str(company)
                
                # Extract job description
                description = job_item.get("description", "")
                
                # Extract job location
                location = job_item.get("location", "")
                if not location and "country" in job_item:
                    location = job_item.get("country", "")
                
                # Check if remote
                is_remote = False
                if isinstance(location, str) and "remote" in location.lower():
                    is_remote = True
                    
                # Format skills
                skills = []
                if job_item.get("technology_slugs"):
                    skills = job_item.get("technology_slugs", [])
                    
                # Create job object
                processed_job = {
                    "id": job_id,
                    "title": job_item.get("job_title", "Unknown Title"),
                    "company": company_name,
                    "location": location,
                    "type": job_item.get("employment_statuses", ["Full-time"])[0] if job_item.get("employment_statuses") else "Full-time",
                    "description": description[:500] + "..." if len(description) > 500 else description,
                    "full_description": description,
                    "url": job_item.get("url", ""),
                    "posted_date": job_item.get("date_posted", ""),
                    "match_score": 75,  # Default match score
                    "remote": is_remote,
                    "source": "TheirStack API",
                    "skills": skills,
                    "salary": job_item.get("salary_string", None)
                }
                
                jobs.append(processed_job)
        
        # Calculate pagination info - FIX HERE
        total_results = result.get("metadata", {}).get("total_results", 0)
        # Handle the case when total_results might be None
        if total_results is None:
            total_results = 0
            
        total_pages = max(1, (total_results + 24) // 25)  # Ceiling division for pages
        
        return {
            "jobs": jobs,
            "total_pages": total_pages,
            "current_page": request_data.page,
            "total_results": total_results
        }
        
    except Exception as e:
        logger.error(f"Error searching jobs with TheirStack API: {e}")
        return {"jobs": [], "total_pages": 0, "current_page": 1, "error": str(e)}

async def get_cv_text(cv_id: str, user_id: str) -> Optional[str]:
    """
    Get CV text from database
    """
    try:
        if not cv_id or not user_id or db is None:
            return None
            
        # Find CV document
        cv_document = await find_cv_by_id(db, cv_id, user_id)
        
        if not cv_document:
            logger.warning(f"CV not found: {cv_id}")
            return None
            
        # Get extracted text
        cv_text = cv_document.get("extractedText")
        
        # If no extracted text, try other field names
        if not cv_text:
            cv_text = cv_document.get("content")
            
        return cv_text
    except Exception as e:
        logger.error(f"Error getting CV text: {e}")
        return None

def calculate_match_score(cv_text: str, job_skills: List[str]) -> int:
    """
    Calculate a match score between a CV and job skills
    """
    try:
        if not cv_text or not job_skills:
            return 70  # Default score
            
        # Count how many skills from the job match the CV
        cv_text_lower = cv_text.lower()
        matched_skills = 0
        
        for skill in job_skills:
            if skill.lower() in cv_text_lower:
                matched_skills += 1
                
        # Calculate match percentage
        if job_skills:
            match_percentage = (matched_skills / len(job_skills)) * 100
            
            # Adjust score to be between 60-95 (never perfect match or too low)
            adjusted_score = int(60 + (match_percentage * 0.35))
            adjusted_score = min(95, max(60, adjusted_score))
            
            return adjusted_score
        else:
            return 70  # Default score
            
    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        return 70  # Default score on error

# ------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------

@router.post("/api/job-search")
async def search_jobs(
    request: Request,
    data: JobSearchRequest
):
    """
    Search for jobs based on criteria
    """
    logger.info(f"Job search request: {data.query} in {data.location}")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Get CV text if cv_id is provided
    cv_text = None
    if data.cv_id:
        cv_text = await get_cv_text(data.cv_id, user_id)
        if cv_text:
            logger.info(f"Retrieved CV text for job matching")
    
    # Search for jobs using TheirStack API
    job_results = await search_jobs_theirstack(data)
    
    # If CV was provided, calculate match scores for each job
    if cv_text and job_results.get("jobs"):
        for job in job_results["jobs"]:
            # Calculate match score based on skills and CV text
            job_skills = job.get("skills", [])
            match_score = calculate_match_score(cv_text, job_skills)
            job["match_score"] = match_score
        
        # Sort by match score if CV provided
        job_results["jobs"] = sorted(
            job_results["jobs"],
            key=lambda x: x.get("match_score", 0),
            reverse=True
        )
    
    # Log job search to history
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
    
    # Return search results
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
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check if MongoDB is available
    if saved_jobs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        # Check if job already saved
        existing_job = await saved_jobs_col.find_one({
            "user_id": user_id,
            "job.id": data.job.get("id")
        })
        
        if existing_job:
            logger.info(f"Job already saved: {data.job.get('id')}")
            return {"status": "success", "detail": "Job already saved"}
        
        # Save job to database
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
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check if MongoDB is available
    if saved_jobs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        # Remove job from database
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
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check if MongoDB is available
    if saved_jobs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        # Get saved jobs from database
        cursor = saved_jobs_col.find({"user_id": user_id}).sort("saved_at", -1)
        saved_jobs = await cursor.to_list(length=100)
        
        # Extract job data
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
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check if CV is provided
    if not data.cv_id:
        logger.warning("No CV provided for job application")
        return JSONResponse(
            status_code=400,
            content={"detail": "CV is required for job application"}
        )
    
    # Get CV document
    cv_document = await find_cv_by_id(db, data.cv_id, user_id)
    if not cv_document:
        logger.warning(f"CV not found: {data.cv_id}")
        return JSONResponse(
            status_code=404,
            content={"detail": "CV not found"}
        )
    
    # Check if job URL is provided
    if not data.job_url:
        logger.warning("No job URL provided for application")
        return JSONResponse(
            status_code=400,
            content={"detail": "Job URL is required for application"}
        )
    
    try:
        # Log application in database (if job_searches_col is available)
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
        
        # Return success
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
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check if MongoDB is available
    if job_searches_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        # Create notification record
        notification = {
            "user_id": user_id,
            "query": data.query,
            "location": data.location,
            "job_type": data.job_type,
            "experience_level": data.experience_level,
            "created_at": datetime.utcnow(),
            "frequency": "daily",  # Default frequency
            "active": True
        }
        
        # Save to database
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

# Export the router for use in main FastAPI app
def setup_job_search_routes(app):
    """
    Set up job search routes in the main FastAPI app
    """
    app.include_router(router, tags=["job-search"])