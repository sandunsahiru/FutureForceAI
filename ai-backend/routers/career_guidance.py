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

async def get_cv_text(cv_id: str, user_id: str) -> tuple[Optional[str], bool]:
    """
    Get CV text from database with enhanced error handling and text extraction.
    Returns a tuple of (cv_text, is_extractable)
    """
    logger.info(f"Getting CV text for ID: {cv_id}")
    
    try:
        # Find CV document
        cv_collection = db.get_collection("cvs")
        cv_document = await cv_collection.find_one({"_id": ObjectId(cv_id), "userId": user_id})
        
        if not cv_document:
            logger.warning(f"CV not found with ID: {cv_id} for user: {user_id}")
            return None, False
            
        # First try to get extracted text
        if "extractedText" in cv_document and cv_document["extractedText"] and len(cv_document["extractedText"].strip()) > 100:
            logger.info("Using 'extractedText' field from CV document")
            
            # Check if the extracted text contains meaningful content
            cv_text = cv_document["extractedText"]
            career_keywords = ["experience", "education", "skills", "work", "project", "job", "employment", "qualification"]
            contains_career_content = any(keyword in cv_text.lower() for keyword in career_keywords)
            
            if contains_career_content:
                return cv_text, True
            else:
                logger.warning("CV text found but doesn't contain meaningful career content")
                # Try to improve the extracted text using OpenAI
                try:
                    prompt = (
                        "The following text was extracted from a CV/resume but may not contain proper career information. "
                        "If this contains any professional details like education, work experience, skills, or projects, "
                        "please format it properly. If it appears to be metadata or non-career content, indicate that this "
                        "doesn't contain meaningful career information.\n\n"
                        f"{cv_text[:2000]}"  # Limit to 2000 chars to avoid token limits
                    )
                    
                    enhanced_text = call_openai(prompt)
                    
                    if "doesn't contain" in enhanced_text.lower() or "does not contain" in enhanced_text.lower():
                        # OpenAI confirms it's not meaningful CV content
                        return cv_text, False
                    else:
                        # OpenAI was able to extract/enhance some career information
                        # Update the database with the enhanced text
                        await cv_collection.update_one(
                            {"_id": cv_document["_id"]},
                            {"$set": {"extractedText": enhanced_text, "lastUsed": datetime.utcnow()}}
                        )
                        logger.info("Enhanced CV text using OpenAI")
                        return enhanced_text, True
                except Exception as openai_err:
                    logger.error(f"Error enhancing CV text with OpenAI: {openai_err}")
                    return cv_text, False
            
        # Try content field if extractedText not found or too short
        if "content" in cv_document and cv_document["content"] and len(cv_document["content"].strip()) > 100:
            logger.info("Using 'content' field from CV document")
            return cv_document["content"], True
            
        # If still no usable text, try to extract from file
        if "filePath" in cv_document and cv_document["filePath"]:
            file_path = cv_document["filePath"]
            logger.info(f"Attempting to extract text from file: {file_path}")
            
            if os.path.exists(file_path):
                try:
                    # Extract text using the utility function
                    cv_text = extract_text_from_document(file_path, vision_client, openai_client)
                    
                    if cv_text and len(cv_text.strip()) > 100:
                        # Check if the extracted text contains meaningful career content
                        career_keywords = ["experience", "education", "skills", "work", "project", "job", "employment", "qualification"]
                        contains_career_content = any(keyword in cv_text.lower() for keyword in career_keywords)
                        
                        # Update the database with the extracted text
                        await cv_collection.update_one(
                            {"_id": cv_document["_id"]},
                            {"$set": {"extractedText": cv_text, "lastUsed": datetime.utcnow()}}
                        )
                        logger.info(f"Successfully extracted and saved text from file: {len(cv_text)} chars")
                        
                        if not contains_career_content:
                            # Try to improve the extracted text using OpenAI
                            try:
                                prompt = (
                                    "The following text was extracted from a CV/resume but may not contain proper career information. "
                                    "If this contains any professional details like education, work experience, skills, or projects, "
                                    "please format it properly. If it appears to be metadata or non-career content, indicate that this "
                                    "doesn't contain meaningful career information.\n\n"
                                    f"{cv_text[:2000]}"  # Limit to 2000 chars to avoid token limits
                                )
                                
                                enhanced_text = call_openai(prompt)
                                
                                if "doesn't contain" in enhanced_text.lower() or "does not contain" in enhanced_text.lower():
                                    # OpenAI confirms it's not meaningful CV content
                                    return cv_text, False
                                else:
                                    # OpenAI was able to extract/enhance some career information
                                    # Update the database with the enhanced text
                                    await cv_collection.update_one(
                                        {"_id": cv_document["_id"]},
                                        {"$set": {"extractedText": enhanced_text, "lastUsed": datetime.utcnow()}}
                                    )
                                    logger.info("Enhanced CV text using OpenAI")
                                    return enhanced_text, True
                            except Exception as openai_err:
                                logger.error(f"Error enhancing CV text with OpenAI: {openai_err}")
                                return cv_text, contains_career_content
                        
                        return cv_text, contains_career_content
                    else:
                        logger.warning(f"Extracted text too short or empty from file: {file_path}")
                        return f"The text extracted from your CV is too limited for analysis. Please upload a text-based document with career information.", False
                except Exception as e:
                    logger.error(f"Error extracting text from file: {e}")
                    return f"Error extracting text from CV file: {str(e)}", False
        
        # As a final fallback, check for any text fields that might contain CV data
        for field in ["rawText", "text", "data", "parsedContent"]:
            if field in cv_document and cv_document[field] and len(str(cv_document[field]).strip()) > 100:
                logger.info(f"Using '{field}' field from CV document")
                text = str(cv_document[field])
                career_keywords = ["experience", "education", "skills", "work", "project", "job", "employment", "qualification"]
                contains_career_content = any(keyword in text.lower() for keyword in career_keywords)
                return text, contains_career_content
        
        # If we have a PDF or image-based file but couldn't extract meaningful text, try directly with OpenAI Vision API
        if "filePath" in cv_document and cv_document["filePath"] and (
            cv_document.get("contentType", "").lower().startswith("application/pdf") or
            cv_document.get("contentType", "").lower().startswith("image/")
        ):
            try:
                import base64
                
                file_path = cv_document["filePath"]
                logger.info(f"Attempting direct OpenAI Vision analysis for: {file_path}")
                
                if os.path.exists(file_path) and openai_client:
                    # Read the file
                    with open(file_path, "rb") as file:
                        file_data = file.read()
                    
                    # Create a base64 encoded version of the file
                    file_b64 = base64.b64encode(file_data).decode('utf-8')
                    
                    # Determine content type
                    content_type = cv_document.get("contentType", "application/pdf")
                    
                    # Call OpenAI Vision API
                    response = openai_client.chat.completions.create(
                        model="gpt-4-vision-preview",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Please extract all the career information from this CV/resume. Include education, work experience, skills, projects, and any other professional details. Format it as a clean CV. If this isn't a CV or doesn't contain career information, please indicate that."},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{content_type};base64,{file_b64}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=4096
                    )
                    
                    vision_text = response.choices[0].message.content
                    
                    if "isn't a CV" in vision_text.lower() or "doesn't contain" in vision_text.lower() or "does not contain" in vision_text.lower():
                        # OpenAI confirms it's not a CV
                        logger.warning("OpenAI Vision API confirms this isn't a CV or doesn't contain career information")
                        return "The document you uploaded doesn't appear to be a CV or doesn't contain career information. Please upload a document with your professional details.", False
                    
                    # Update the database with the extracted text
                    await cv_collection.update_one(
                        {"_id": cv_document["_id"]},
                        {"$set": {"extractedText": vision_text, "lastUsed": datetime.utcnow()}}
                    )
                    logger.info(f"Successfully extracted CV text using OpenAI Vision API: {len(vision_text)} chars")
                    return vision_text, True
            except Exception as vision_err:
                logger.error(f"Error using OpenAI Vision API for CV: {vision_err}")
                
        logger.error(f"No usable CV text found in document: {cv_id}")
        return "No readable text could be extracted from your CV. Please upload a text-based PDF or Word document with your professional information.", False
        
    except Exception as e:
        logger.error(f"Error retrieving CV text: {e}")
        return f"Error processing CV: {str(e)}", False

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
    
    # Get CV text - might be None or limited text if extraction failed
    cv_text_result = await get_cv_text(data.cv_id, user_id)
    cv_text = cv_text_result[0]  # Extract text from tuple
    cv_extractable = cv_text_result[1]  # Extract extractable flag from tuple
    
    try:
        # Process career goals
        career_goals = data.career_goals.dict() if data.career_goals else {}
        
        # Check if CV text is sufficient for analysis - this additional check is redundant but keeping for safety
        if cv_text and not cv_extractable:
            cv_extractable = len(cv_text.strip()) >= 100 and any(keyword in cv_text.lower() for keyword in 
                ["experience", "education", "skills", "work", "project", "job", "employment", "qualification"])
        
        # Analyze CV and generate career guidance with proper error handling
        try:
            # If CV is not extractable, create a fallback analysis
            if not cv_extractable:
                logger.warning("CV text is insufficient for detailed analysis")
                skills_analysis = {
                    "summary": f"The provided CV content is not extractable as it appears to be an image-based document or doesn't contain readable text related to your qualifications or experience. Therefore, a detailed analysis in relation to your career interests in {', '.join(data.career_interests)} cannot be conducted. Please upload a text-based CV format (such as a Word document or text-based PDF) that contains your professional information.",
                    "currentLevel": "Unknown due to lack of readable CV content",
                    "growthPotential": "Undeterminable without detailed information",
                    "marketDemand": f"Roles in {', '.join(data.career_interests)} generally show moderate to high demand in the job market",
                    "skills": [],
                    "strengths": [],
                    "improvements": [
                        {"name": "Provide extractable CV", "description": "Upload a CV in a format that allows text extraction for better analysis (Word document or text-based PDF)"},
                        {"name": "Ensure career content", "description": "Make sure your CV contains details about your education, work experience, skills, and projects"}
                    ],
                    "future_skills": [
                        {"name": "Core skills for " + data.career_interests[0] if data.career_interests else "your field", 
                         "reason": "Essential foundation for career progression", 
                         "marketDemand": "High demand across the industry"}
                    ]
                }
            else:
                # Normal analysis with extractable CV
                skills_analysis = await analyze_cv_skills(cv_text, data.career_interests, career_goals)
                
            if not skills_analysis:
                logger.error("analyze_cv_skills returned None or empty result")
                skills_analysis = {
                    "summary": f"Based on your stated career interests in {', '.join(data.career_interests)}, we've prepared a general analysis. For a more detailed assessment, try uploading a different CV format.",
                    "currentLevel": "Professional",
                    "growthPotential": "Good",
                    "marketDemand": "Moderate to high",
                    "skills": [],
                    "strengths": [],
                    "improvements": [],
                    "future_skills": []
                }
            logger.info(f"Skills analysis completed successfully. Keys: {list(skills_analysis.keys())}")
        except Exception as e:
            logger.error(f"Error in analyze_cv_skills: {e}")
            skills_analysis = {
                "summary": f"Based on your stated career interests in {', '.join(data.career_interests)}, we've prepared a general analysis. For a more detailed assessment, try uploading a different CV format.",
                "currentLevel": "Professional",
                "growthPotential": "Good",
                "marketDemand": "Moderate to high",
                "skills": [],
                "strengths": [],
                "improvements": [],
                "future_skills": []
            }
        
        try:
            career_paths = await generate_career_paths(cv_text if cv_extractable else "", data.career_interests, career_goals, skills_analysis)
            if not career_paths:
                logger.warning("No career paths generated, using default paths")
                career_paths = []
            logger.info(f"Career paths generated: {len(career_paths)}")
        except Exception as e:
            logger.error(f"Error in generate_career_paths: {e}")
            career_paths = []
        
        try:
            skill_gaps = await identify_skill_gaps(cv_text if cv_extractable else "", data.career_interests, skills_analysis)
            if not skill_gaps:
                logger.warning("No skill gaps identified")
                skill_gaps = []
            logger.info(f"Skill gaps identified: {len(skill_gaps)}")
        except Exception as e:
            logger.error(f"Error in identify_skill_gaps: {e}")
            skill_gaps = []
        
        try:
            learning_resources = await recommend_learning_resources(skill_gaps, data.career_interests)
            if not learning_resources:
                logger.warning("No learning resources recommended")
                learning_resources = {"paths": [], "courses": [], "certifications": []}
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
            action_plan = []
        
        # Save analysis to database
        if career_analyses_col is not None:
            try:
                analysis_record = {
                    "user_id": user_id,
                    "cv_id": data.cv_id,
                    "career_interests": data.career_interests,
                    "career_goals": career_goals,
                    "analysis_summary": skills_analysis.get("summary", "Analysis completed"),
                    "created_at": datetime.utcnow(),
                    "cv_extractable": cv_extractable
                }
                
                await career_analyses_col.insert_one(analysis_record)
                logger.info(f"Saved career analysis to database for user: {user_id}")
            except Exception as db_err:
                logger.error(f"Error saving analysis to database: {db_err}")
        
        # Return comprehensive career guidance
        result = {
            "analysis": {
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
            },
            "career_paths": career_paths,
            "skill_gaps": skill_gaps,
            "learning_resources": learning_resources
        }
        
        # If CV wasn't extractable but we don't have improvements yet, add one about providing an extractable CV
        if not cv_extractable and not result["analysis"]["improvements"]:
            result["analysis"]["improvements"] = [
                {"title": "Provide extractable CV", 
                 "description": "Upload a CV in a format that allows text extraction for better analysis"}
            ]
        
        # Validate the final data structure to ensure no None values
        result = remove_none_values(result)
        
        logger.info(f"Returning career analysis result with {len(result)} top-level keys")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing career path: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error analyzing career path: {str(e)}"}
        )


def extract_text_from_document(file_path: str, vision_client=None, openai_client=None) -> str:
    """
    Extract text from a document using multiple methods for better extraction.
    """
    extracted_text = ""
    
    # Method 1: Try PyPDF2
    try:
        import PyPDF2
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            pdf_text = ""
            for page_num in range(len(reader.pages)):
                page_text = reader.pages[page_num].extract_text() or ""
                pdf_text += page_text
            
            if pdf_text and len(pdf_text.strip()) >= 100:
                return pdf_text
            
            # If we didn't get good text, store what we have
            extracted_text = pdf_text
    except Exception as e:
        logging.error(f"PyPDF2 extraction error: {e}")
    
    # Method 2: Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            plumber_text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                plumber_text += page_text
            
            if plumber_text and len(plumber_text.strip()) >= 100:
                return plumber_text
            
            # If better than what we have, update
            if len(plumber_text) > len(extracted_text):
                extracted_text = plumber_text
    except Exception as e:
        logging.error(f"pdfplumber extraction error: {e}")
    
    # Method 3: Try pytesseract for OCR if it's installed
    try:
        from PIL import Image
        import pytesseract
        import pdf2image
        
        ocr_text = ""
        # Convert PDF to images
        images = pdf2image.convert_from_path(file_path)
        
        # Process each image with OCR
        for image in images:
            page_text = pytesseract.image_to_string(image)
            ocr_text += page_text
        
        if ocr_text and len(ocr_text.strip()) >= 100:
            return ocr_text
        
        # If better than what we have, update
        if len(ocr_text) > len(extracted_text):
            extracted_text = ocr_text
    except Exception as e:
        logging.error(f"OCR extraction error: {e}")
    
    # Method 4: Use Google Vision API if available
    if vision_client:
        try:
            # Open the file and convert to bytes
            with open(file_path, "rb") as file:
                content = file.read()
            
            # Create an image object
            image = vision_client.types.Image(content=content)
            
            # Perform text detection
            response = vision_client.text_detection(image=image)
            
            # Extract text from response
            vision_text = response.text_annotations[0].description if response.text_annotations else ""
            
            if vision_text and len(vision_text.strip()) >= 100:
                return vision_text
            
            # If better than what we have, update
            if len(vision_text) > len(extracted_text):
                extracted_text = vision_text
        except Exception as e:
            logging.error(f"Vision API extraction error: {e}")
    
    # Method 5: Use OpenAI if available (as a last resort due to cost)
    if openai_client and len(extracted_text.strip()) < 100:
        try:
            # Prepare the file for OpenAI
            with open(file_path, "rb") as file:
                # Create a form to send to OpenAI
                response = openai_client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user", 
                            "content": [
                                {"type": "text", "text": "Please extract all the text from this document. Return only the extracted text, no comments or descriptions."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:application/pdf;base64,{base64.b64encode(file.read()).decode('utf-8')}",
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=4096,
                )
                
                openai_text = response.choices[0].message.content
                
                if openai_text and len(openai_text.strip()) >= 100:
                    return openai_text
                
                # If better than what we have, update
                if len(openai_text) > len(extracted_text):
                    extracted_text = openai_text
        except Exception as e:
            logging.error(f"OpenAI extraction error: {e}")
    
    # Return whatever text we managed to extract, even if it's not great
    return extracted_text

def remove_none_values(data):
    """Recursively remove None values from dictionaries and lists"""
    if isinstance(data, dict):
        return {k: remove_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_none_values(item) for item in data if item is not None]
    else:
        return data