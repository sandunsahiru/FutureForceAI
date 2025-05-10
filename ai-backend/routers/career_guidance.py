import os
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import jwt
import motor.motor_asyncio
from bson import ObjectId

# Import shared utilities and connections
from .interviewprep import (
    extract_text_from_document, 
    vision_client, 
    openai_client, 
    conversations_col, 
    call_openai,
    SECRET_KEY
)

# Import CV utilities
from .cv_utils import (
    ensure_uploads_dir,
    generate_timestamp_id,
    clean_filename,
    get_potential_file_paths,
    find_cv_by_id
)

# Import career analysis functions
from .career_analysis import (
    analyze_cv_skills,
    generate_career_paths,
    identify_skill_gaps,
    recommend_learning_resources,
    create_action_plan
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure environment variables
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
logger.info(f"Using MongoDB URI for career guidance: {MONGODB_URI}")

# Create router
router = APIRouter()
logger.info("Career Guidance Router created")

# Get database references
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    career_analyses_col = db["career_analyses"]  # Collection for career analysis history
    logger.info("MongoDB connection established for career guidance")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB for career guidance: {e}")
    client = None
    db = None
    career_analyses_col = None

# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------

class CareerGoals(BaseModel):
    shortTerm: Optional[str] = None
    longTerm: Optional[str] = None
    yearsExperience: Optional[str] = None
    desiredRole: Optional[str] = None
    industry: Optional[str] = None
    workStyle: Optional[str] = None
    priorities: List[str] = []

class CareerGuidanceRequest(BaseModel):
    cv_id: str
    career_interests: List[str]
    career_goals: Optional[CareerGoals] = None

class SkillLevel(BaseModel):
    name: str
    level: str

class CareerStrength(BaseModel):
    title: str
    description: str

class SkillGap(BaseModel):
    skill: str
    currentLevel: int
    requiredLevel: int
    priority: str
    importance: str
    learningPath: str

class CareerPathStep(BaseModel):
    role: str
    years: str

class CareerPath(BaseModel):
    title: str
    description: str
    fitScore: int
    reasons: List[str]
    challenges: List[str]
    progression: List[CareerPathStep]
    salary: str
    growth: str
    timeToTransition: str

class LearningPath(BaseModel):
    title: str
    description: str
    duration: str
    topics: List[str]

class Course(BaseModel):
    title: str
    provider: str
    duration: str
    level: str
    price: Optional[str] = None

class Certification(BaseModel):
    name: str
    description: str
    provider: str
    duration: str
    cost: Optional[str] = None

class ActionPlanStep(BaseModel):
    title: str
    description: str
    timeline: str

class FutureSkill(BaseModel):
    name: str
    reason: str
    marketDemand: str

class CareerAnalysis(BaseModel):
    summary: str
    currentLevel: str
    growthPotential: str
    marketDemand: str
    strengths: List[CareerStrength]
    improvements: List[CareerStrength]
    currentSkills: List[SkillLevel]
    futureSkills: List[FutureSkill]
    actionPlan: List[ActionPlanStep]

class CareerGuidanceResponse(BaseModel):
    analysis: CareerAnalysis
    career_paths: List[CareerPath]
    skill_gaps: List[SkillGap]
    learning_resources: Dict[str, Any]

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

async def get_cv_text(cv_id: str, user_id: str) -> Optional[str]:
    """Get CV text from MongoDB by ID with error handling"""
    if db is None:
        logger.error("MongoDB not connected")
        return None
    
    try:
        # Find the CV document
        cv_document = await find_cv_by_id(db, cv_id, user_id)
        
        if not cv_document:
            logger.warning(f"CV not found: {cv_id}")
            return None
        
        # Get CV text from document using different possible field names
        cv_text = None
        
        # First check extracted text field
        if 'extractedText' in cv_document and cv_document['extractedText']:
            logger.info("Using 'extractedText' field from CV document")
            cv_text = cv_document['extractedText']
            
        # Try content field if extractedText not found
        if not cv_text and 'content' in cv_document and cv_document['content']:
            logger.info("Using 'content' field from CV document")
            cv_text = cv_document['content']
        
        # If still no text, try extracting from file
        if not cv_text or len(cv_text.strip()) < 100:
            # Get potential file paths
            potential_paths = get_potential_file_paths(cv_document)
            logger.info(f"Trying potential file paths: {potential_paths}")
            
            # Try each path
            for path in potential_paths:
                if os.path.exists(path):
                    logger.info(f"Found file at path: {path}")
                    try:
                        cv_text = extract_text_from_document(path, vision_client, openai_client)
                        if cv_text and len(cv_text.strip()) >= 100:
                            logger.info(f"Successfully extracted {len(cv_text)} chars from file")
                            
                            # Update database with extracted text
                            cv_collection = db.get_collection("cvs")
                            await cv_collection.update_one(
                                {"_id": cv_document["_id"]},
                                {"$set": {
                                    "extractedText": cv_text,
                                    "lastUsed": datetime.utcnow()
                                }}
                            )
                            logger.info(f"Updated CV document with extracted text")
                            break
                    except Exception as e:
                        logger.error(f"Error extracting text from file: {e}")
                        # Continue trying other paths
        
        # If we still don't have usable CV text, return None
        if not cv_text or len(cv_text.strip()) < 100:
            logger.error(f"Could not extract sufficient content from CV")
            return None
            
        return cv_text
    
    except Exception as e:
        logger.error(f"Error retrieving CV text: {e}")
        return None

# ------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------

@router.post("/upload-cv")
async def upload_cv(
    request: Request,
    cv_file: UploadFile = File(...),
):
    """Upload a CV for career analysis with improved error handling."""
    logger.info(f"Uploading CV: {cv_file.filename}")
    
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
    
    try:
        # Ensure uploads directory exists
        uploads_dir = ensure_uploads_dir()
        
        # Generate a unique filename
        file_id = generate_timestamp_id()
        clean_filename_str = clean_filename(cv_file.filename or "uploaded_cv.pdf")
        filename = f"{file_id}_{clean_filename_str}"
        file_path = os.path.join(uploads_dir, filename)
        
        # Save file to disk with proper error handling
        try:
            content = await cv_file.read()
            if not content or len(content) < 100:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Uploaded file is empty or too small"}
                )
                
            with open(file_path, "wb") as f:
                f.write(content)
                
            # Reset file pointer
            await cv_file.seek(0)
            
            logger.info(f"CV file saved to: {file_path}")
        except Exception as file_err:
            logger.error(f"Error saving file: {file_err}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to save uploaded file"}
            )
        
        # Extract text from CV with timeout protection
        try:
            cv_text = extract_text_from_document(file_path, vision_client, openai_client)
            if not cv_text or len(cv_text.strip()) < 100:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Could not extract sufficient content from CV. Please try a different file."}
                )
        except Exception as extract_err:
            logger.error(f"Error extracting text: {extract_err}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to process CV content. Please try a different file format."}
            )
        
        # Save to database for future use
        try:
            cv_collection = db.get_collection("cvs")
            if cv_collection is not None:
                cv_document = {
                    "userId": user_id,
                    "filename": filename,
                    "originalName": cv_file.filename or "uploaded_cv.pdf",
                    "filePath": file_path,
                    "fileSize": len(content),
                    "contentType": cv_file.content_type or "application/octet-stream",
                    "extractedText": cv_text,
                    "uploadedAt": datetime.utcnow(),
                    "lastUsed": datetime.utcnow(),
                    "fileId": file_id
                }
            
                result = await cv_collection.insert_one(cv_document)
                cv_id = str(result.inserted_id)
                logger.info(f"Saved CV to database with ID: {cv_id}")
            else:
                logger.error("CV collection not available")
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Database error: CV collection not available"}
                )
        except Exception as db_err:
            logger.error(f"Database error: {db_err}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Database error: {str(db_err)}"}
            )
            
        # Return CV ID
        return {
            "cv_id": cv_id,
            "filename": cv_file.filename,
            "message": "CV uploaded successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in upload_cv: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred: {str(e)}"}
        )

@router.post("/analyze")
async def analyze_career_path(
    request: Request,
    data: CareerGuidanceRequest
):
    """
    Analyze CV and provide career guidance based on interests and goals.
    """
    logger.info(f"Analyzing career path for interests: {data.career_interests}")
    
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
    
    # Get CV text
    cv_text = await get_cv_text(data.cv_id, user_id)
    if not cv_text:
        return JSONResponse(
            status_code=404,
            content={"detail": "Could not retrieve or extract CV content"}
        )
    
    try:
        # Process career goals
        career_goals = data.career_goals.dict() if data.career_goals else {}
        
        # Analyze CV and generate career guidance with proper error handling
        try:
            skills_analysis = await analyze_cv_skills(cv_text, data.career_interests, career_goals)
            if not skills_analysis:
                logger.error("analyze_cv_skills returned None or empty result")
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Failed to analyze CV skills. Please try again."}
                )
            logger.info(f"Skills analysis completed successfully. Keys: {list(skills_analysis.keys())}")
        except Exception as e:
            logger.error(f"Error in analyze_cv_skills: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Error analyzing CV skills: {str(e)}"}
            )
        
        try:
            career_paths = await generate_career_paths(cv_text, data.career_interests, career_goals, skills_analysis)
            if not career_paths:
                logger.warning("No career paths generated, using default paths")
                career_paths = [
                    {
                        "title": data.career_interests[0] if data.career_interests else "Professional",
                        "description": "A career aligned with your interests and skills",
                        "fitScore": 80,
                        "reasons": ["Based on your career interests", "Matches your current skills"],
                        "challenges": ["May require additional training or certification"],
                        "progression": [
                            {"role": "Entry Level", "years": "1-2 years"},
                            {"role": "Mid-Level", "years": "2-4 years"},
                            {"role": "Senior Level", "years": "4+ years"}
                        ],
                        "salary": "Competitive based on experience and location",
                        "growth": "Varies by industry and region",
                        "timeToTransition": "Dependent on current experience"
                    }
                ]
            logger.info(f"Career paths generation completed successfully. Generated {len(career_paths)} paths.")
        except Exception as e:
            logger.error(f"Error in generate_career_paths: {e}")
            # Create a default career path based on the career interests
            career_paths = [
                {
                    "title": data.career_interests[0] if data.career_interests else "Professional",
                    "description": "A career aligned with your interests and skills",
                    "fitScore": 80,
                    "reasons": ["Based on your career interests", "Matches your current skills"],
                    "challenges": ["May require additional training or certification"],
                    "progression": [
                        {"role": "Entry Level", "years": "1-2 years"},
                        {"role": "Mid-Level", "years": "2-4 years"},
                        {"role": "Senior Level", "years": "4+ years"}
                    ],
                    "salary": "Competitive based on experience and location",
                    "growth": "Varies by industry and region",
                    "timeToTransition": "Dependent on current experience"
                }
            ]
        
        try:
            skill_gaps = await identify_skill_gaps(cv_text, data.career_interests, skills_analysis)
            if not skill_gaps:
                logger.warning("No skill gaps identified")
                skill_gaps = []
            logger.info(f"Skill gaps identification completed. Found {len(skill_gaps)} skill gaps.")
        except Exception as e:
            logger.error(f"Error in identify_skill_gaps: {e}")
            skill_gaps = []
        
        try:
            learning_resources = await recommend_learning_resources(skill_gaps, data.career_interests)
            if not learning_resources:
                logger.warning("No learning resources recommended")
                learning_resources = {"paths": [], "courses": [], "certifications": []}
            
            # Check the structure of learning resources
            if not isinstance(learning_resources, dict):
                logger.error(f"learning_resources has invalid type: {type(learning_resources)}")
                learning_resources = {"paths": [], "courses": [], "certifications": []}
            elif not all(k in learning_resources for k in ["paths", "courses", "certifications"]):
                logger.error(f"learning_resources is missing required keys. Keys: {list(learning_resources.keys())}")
                # Fix the structure if needed
                if "paths" not in learning_resources:
                    learning_resources["paths"] = []
                if "courses" not in learning_resources:
                    learning_resources["courses"] = []
                if "certifications" not in learning_resources:
                    learning_resources["certifications"] = []
            
            logger.info(f"Learning resources: {len(learning_resources.get('paths', []))} paths, {len(learning_resources.get('courses', []))} courses, {len(learning_resources.get('certifications', []))} certifications")
        except Exception as e:
            logger.error(f"Error in recommend_learning_resources: {e}")
            learning_resources = {"paths": [], "courses": [], "certifications": []}
        
        try:
            action_plan = await create_action_plan(career_paths, skill_gaps, learning_resources)
            if not action_plan:
                logger.warning("No action plan created")
                action_plan = []
            logger.info(f"Action plan created with {len(action_plan)} steps")
        except Exception as e:
            logger.error(f"Error in create_action_plan: {e}")
            action_plan = [
                {
                    "title": "Develop Key Skills",
                    "description": "Focus on learning and practicing essential skills for your target career",
                    "timeline": "3-6 months"
                },
                {
                    "title": "Build Portfolio",
                    "description": "Create projects showcasing your skills and expertise",
                    "timeline": "2-4 months"
                },
                {
                    "title": "Job Search",
                    "description": "Apply for relevant positions in your desired field",
                    "timeline": "Ongoing"
                }
            ]
        
        # Create comprehensive analysis
        analysis = {
            "summary": skills_analysis.get("summary", "Based on your CV and career interests, we've analyzed potential career paths for you."),
            "currentLevel": skills_analysis.get("currentLevel", "Professional"),
            "growthPotential": skills_analysis.get("growthPotential", "Good"),
            "marketDemand": skills_analysis.get("marketDemand", "Varies by location"),
            "strengths": [
                {"title": s.get("name", "Skill") if isinstance(s, dict) else str(s), 
                 "description": s.get("description", "A relevant skill for your career path") if isinstance(s, dict) else "Important skill"} 
                for s in skills_analysis.get("strengths", []) if s
            ],
            "improvements": [
                {"title": i.get("name", "Area") if isinstance(i, dict) else str(i), 
                 "description": i.get("description", "An area for potential improvement") if isinstance(i, dict) else "Area to improve"}
                for i in skills_analysis.get("improvements", []) if i
            ],
            "currentSkills": [
                {"name": s.get("name", "Skill") if isinstance(s, dict) else str(s), 
                 "level": s.get("level", "Intermediate") if isinstance(s, dict) else "Intermediate"}
                for s in skills_analysis.get("skills", []) if s
            ],
            "futureSkills": [
                {"name": s.get("name", "Skill") if isinstance(s, dict) else str(s), 
                 "reason": s.get("reason", "Important for career advancement") if isinstance(s, dict) else "Important for career growth", 
                 "marketDemand": s.get("marketDemand", "Growing") if isinstance(s, dict) else "In demand"}
                for s in skills_analysis.get("future_skills", []) if s
            ],
            "actionPlan": action_plan
        }
        
        # Validate the final data structure to ensure no None values
        analysis = remove_none_values(analysis)
        career_paths = remove_none_values(career_paths)
        skill_gaps = remove_none_values(skill_gaps)
        learning_resources = remove_none_values(learning_resources)
        
        # Save analysis results to database
        if career_analyses_col is not None:
            try:
                analysis_record = {
                    "user_id": user_id,
                    "cv_id": data.cv_id,
                    "career_interests": data.career_interests,
                    "career_goals": career_goals,
                    "analysis_summary": analysis["summary"],
                    "created_at": datetime.utcnow()
                }
                
                await career_analyses_col.insert_one(analysis_record)
                logger.info(f"Saved career analysis to database for user: {user_id}")
            except Exception as db_err:
                logger.error(f"Error saving analysis to database: {db_err}")
                # Continue even if DB save fails
        
        # Return comprehensive career guidance
        result = {
            "analysis": analysis,
            "career_paths": career_paths,
            "skill_gaps": skill_gaps,
            "learning_resources": learning_resources
        }
        
        logger.info(f"Returning career analysis result with {len(result)} top-level keys")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing career path: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error analyzing career path: {str(e)}"}
        )

def remove_none_values(data):
    """Recursively remove None values from dictionaries and lists"""
    if isinstance(data, dict):
        return {k: remove_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_none_values(item) for item in data if item is not None]
    else:
        return data