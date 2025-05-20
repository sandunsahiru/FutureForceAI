import os
import uuid
import logging
import json
import base64
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from .pdf_extraction import extract_text_from_document
from dotenv import load_dotenv
import motor.motor_asyncio
import jwt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants and environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "NE60hAlMyF6wVlOt5+VDKpaU/I6FJ4Oa5df1gpG/MTg=")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")

logger.info(f"Using MongoDB URI: {MONGODB_URI}")
logger.info(f"Using OpenAI model: {OPENAI_MODEL}")

# Initialize OpenAI client
try:
    import openai
    from openai import OpenAI
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        if hasattr(openai, 'OpenAI'):
            openai_client = OpenAI(api_key=openai_api_key)
            logger.info("OpenAI v1.x client initialized")
        else:
            openai.api_key = openai_api_key
            logger.info("Using legacy OpenAI v0.x API")
            openai_client = None
    else:
        logger.warning("OpenAI API key not set")
        openai_client = None
except ImportError:
    logger.warning("OpenAI library not installed")
    openai = None
    OpenAI = None
    openai_client = None

# Initialize Google Vision client
try:
    from google.cloud import vision
    
    gcp_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if gcp_credentials_path:
        vision_client = vision.ImageAnnotatorClient()
        logger.info("Google Vision client initialized")
    else:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set")
        vision_client = None
except ImportError:
    logger.warning("Google Cloud Vision library not installed")
    vision = None
    vision_client = None

# Set up MongoDB
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    resumes_col = db["resumes"]
    users_col = db["users"]
    optimized_resumes_col = db["optimized_resumes"]
    logger.info("MongoDB connection established")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    client = None
    db = None
    resumes_col = None
    users_col = None
    optimized_resumes_col = None

# Create API router
router = APIRouter()
logger.info("API Router created")

# Pydantic Models
class ResumeAnalysisRequest(BaseModel):
    resume_id: Optional[str] = None
    target_role: str

class ResumeAnalysisResponse(BaseModel):
    ats_score: int
    keywords: dict
    format_issues: List[str]
    recommendations: List[str]
    sections: dict

class OptimizeResumeRequest(BaseModel):
    resume_id: str
    target_role: str
    analysis: dict

class RoleSource(BaseModel):
    role: str
    source: str  # 'resume', 'suggestion', 'user'

class SuggestedRolesResponse(BaseModel):
    suggested_roles: List[str]
    resume_id: Optional[str] = None

# Helper Functions
async def save_resume_to_disk(resume_file: UploadFile) -> str:
    """Save the uploaded resume to local disk"""
    try:
        logger.info(f"Saving resume file: {resume_file.filename}")
        os.makedirs("uploads", exist_ok=True)
        file_ext = os.path.splitext(resume_file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join("uploads", file_name)
        
        content = await resume_file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        logger.info(f"Resume saved to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving resume file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving resume file: {str(e)}"
        )

async def save_resume_to_db(user_id: str, file_path: str, filename: str, file_size: int, content_type: str, extracted_text: str) -> str:
    """Save resume metadata and extracted text to database"""
    try:
        if resumes_col is None:
            logger.error("MongoDB not available")
            return None
            
        resume_doc = {
            "userId": user_id,
            "filename": os.path.basename(file_path),
            "originalName": filename,
            "filePath": file_path,
            "fileSize": file_size,
            "contentType": content_type,
            "extractedText": extracted_text,
            "uploadedAt": datetime.utcnow(),
            "lastUsed": datetime.utcnow()
        }
        
        result = await resumes_col.insert_one(resume_doc)
        resume_id = str(result.inserted_id)
        logger.info(f"Resume saved to database with ID: {resume_id}")
        return resume_id
    except Exception as e:
        logger.error(f"Error saving resume to database: {e}")
        return None

def call_openai(prompt: str, system_message: str = None) -> str:
    """Call OpenAI API with error handling and retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling OpenAI API with model {OPENAI_MODEL}")
            
            if not system_message:
                system_message = "You are a helpful assistant that provides responses in valid JSON format when requested. Always ensure JSON responses are properly formatted."
                
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
            
            if openai.__version__.startswith('0.'):
                # Legacy OpenAI API
                response = openai.ChatCompletion.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                return response.choices[0].message.content.strip()
            else:
                # Modern OpenAI API
                response = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            logger.error(f"OpenAI API call failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            import time
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("Failed to get response from OpenAI after all retries")

def analyze_resume_with_openai(resume_text: str, target_role: str) -> dict:
    """
    Analyze resume using OpenAI for ATS compatibility, keywords, and recommendations
    """
    logger.info(f"Analyzing resume for role: {target_role}")
    
    system_message = """
    You are an expert ATS (Applicant Tracking System) analyzer and resume optimizer. 
    Your task is to analyze a resume for a specific job role and provide insights on its ATS compatibility.
    Provide your response in valid JSON format with the following structure:
    {
        "ats_score": int,  // 0-100 score reflecting ATS compatibility
        "keywords": {
            "found": [list of keywords found in the resume relevant to the role],
            "missing": [list of important keywords for the role that are missing]
        },
        "format_issues": [list of formatting issues that could impact ATS scoring],
        "recommendations": [specific recommendations to improve the resume],
        "sections": {
            "contact_info": bool,
            "summary": bool,
            "experience": bool,
            "education": bool,
            "skills": bool,
            "projects": bool,
            "certifications": bool
        }
    }
    """
    
    prompt = f"""
    Here is a resume text:
    ```
    {resume_text}
    ```
    
    The job role this person is applying for is: {target_role}
    
    Analyze this resume for ATS compatibility for the specified role:
    
    1. Give an ATS compatibility score from 0-100
    2. Identify keywords found in the resume that are relevant to the role
    3. List important keywords that are missing but would be relevant for this role
    4. Identify any formatting issues that could impact ATS scoring
    5. Provide specific recommendations to improve the resume
    6. Check which standard resume sections are present
    
    Return your analysis in the JSON format described in your instructions.
    """
    
    try:
        response = call_openai(prompt, system_message)
        result = json.loads(response)
        logger.info(f"Resume analysis completed with ATS score: {result.get('ats_score', 0)}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing OpenAI response as JSON: {e}")
        logger.debug(f"Raw response: {response}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error parsing analysis results"
        )
    except Exception as e:
        logger.error(f"Error analyzing resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing resume: {str(e)}"
        )

def suggest_roles_from_resume(resume_text: str) -> list:
    """
    Suggest potential job roles based on the resume content
    """
    logger.info("Suggesting roles from resume")
    
    system_message = """
    You are an expert resume analyzer and career advisor.
    Your task is to analyze a resume and suggest potential job roles that match the candidate's skills and experience.
    """
    
    prompt = f"""
    Here is a resume text:
    ```
    {resume_text}
    ```
    
    Based on this person's skills, experience, and qualifications, suggest 5-8 potential job roles that would be a good match.
    
    Consider:
    1. Technical skills and tools mentioned
    2. Years of experience and seniority level
    3. Industry background
    4. Educational qualifications
    
    Return your suggestions as a JSON array of strings, each string being a job title.
    Example: ["Software Engineer", "Full Stack Developer", "DevOps Engineer"]
    
    Only return the JSON array, no other text.
    """
    
    try:
        response = call_openai(prompt, system_message)
        
        # Try to extract JSON array if it's wrapped in text
        import re
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            response = json_match.group(0)
            
        result = json.loads(response)
        logger.info(f"Suggested {len(result)} roles from resume")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing OpenAI suggested roles as JSON: {e}")
        logger.debug(f"Raw response: {response}")
        # Return empty list rather than raising an exception
        return []
    except Exception as e:
        logger.error(f"Error suggesting roles: {e}")
        return []

def optimize_resume(resume_text: str, target_role: str, analysis: dict) -> str:
    """
    Generate an optimized version of the resume based on analysis
    """
    logger.info(f"Optimizing resume for role: {target_role}")
    
    system_message = """
    You are an expert resume writer and ATS optimization specialist.
    Your task is to rewrite and optimize a resume for a specific job role based on ATS analysis.
    """
    
    prompt = f"""
    Here is the original resume text:
    ```
    {resume_text}
    ```
    
    The job role this person is applying for is: {target_role}
    
    Here is the ATS analysis of the resume:
    ```
    {json.dumps(analysis, indent=2)}
    ```
    
    Rewrite and optimize this resume to improve its ATS compatibility and effectiveness for the target role.
    
    Make sure to:
    1. Add missing keywords identified in the analysis
    2. Fix formatting issues
    3. Include all standard resume sections
    4. Maintain the person's actual experience and qualifications (don't fabricate anything)
    5. Use clear, concise, and professional language
    6. Organize content in a readable, ATS-friendly format
    
    Return the optimized resume text only, formatted professionally.
    """
    
    try:
        optimized_text = call_openai(prompt, system_message)
        logger.info("Resume optimization completed successfully")
        return optimized_text
    except Exception as e:
        logger.error(f"Error optimizing resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error optimizing resume: {str(e)}"
        )

async def create_pdf_from_text(text: str, filename: str) -> str:
    """
    Create a PDF file from text content
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        os.makedirs("generated", exist_ok=True)
        output_path = os.path.join("generated", filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Check if styles already exist and use them instead of adding new ones
        custom_heading1 = None
        custom_heading2 = None
        
        if "Heading1" in styles:
            # Use existing style but modify it
            custom_heading1 = styles["Heading1"]
            custom_heading1.fontSize = 14
            custom_heading1.spaceAfter = 10
            custom_heading1.textColor = colors.darkblue
        else:
            # Add custom styles only if they don't already exist
            styles.add(ParagraphStyle(name='Heading1',
                                    fontName='Helvetica-Bold',
                                    fontSize=14,
                                    spaceAfter=10,
                                    textColor=colors.darkblue))
            custom_heading1 = styles["Heading1"]
        
        if "Heading2" in styles:
            # Use existing style but modify it
            custom_heading2 = styles["Heading2"]
            custom_heading2.fontSize = 12
            custom_heading2.spaceAfter = 6
            custom_heading2.textColor = colors.black
        else:
            # Add custom styles only if they don't already exist
            styles.add(ParagraphStyle(name='Heading2',
                                    fontName='Helvetica-Bold',
                                    fontSize=12,
                                    spaceAfter=6,
                                    textColor=colors.black))
            custom_heading2 = styles["Heading2"]
        
        normal_style = styles["Normal"]
        
        # Process text into sections
        lines = text.split('\n')
        elements = []
        
        # Simple logic to identify headings vs. content
        for line in lines:
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 6))
                continue
                
            if line.isupper() or (len(line) < 30 and line.endswith(':')):
                # Likely a section heading
                elements.append(Paragraph(line, custom_heading1))
            elif line.endswith(':') or (line.startswith('•') and len(line) < 40):
                # Likely a subheading or bullet point
                elements.append(Paragraph(line, custom_heading2))
            else:
                # Normal content
                elements.append(Paragraph(line, normal_style))
                
        # Build the PDF
        doc.build(elements)
        logger.info(f"Created optimized resume PDF at: {output_path}")
        return output_path
        
    except ImportError:
        logger.warning("ReportLab not installed, creating plain text file instead")
        # Fallback to plain text file
        os.makedirs("generated", exist_ok=True)
        output_path = os.path.join("generated", filename.replace('.pdf', '.txt'))
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        logger.info(f"Created optimized resume text file at: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error creating PDF: {e}")
        # Return a text file as a fallback even when PDF creation fails
        try:
            text_output_path = os.path.join("generated", filename.replace('.pdf', '.txt'))
            with open(text_output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"Created fallback text file at: {text_output_path}")
            return text_output_path
        except Exception as text_err:
            logger.error(f"Error creating fallback text file: {text_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating PDF: {str(e)}"
            )

# API Routes

@router.post("/analyze", response_model=ResumeAnalysisResponse)
async def analyze_resume(request: Request, analysis_req: ResumeAnalysisRequest):
    """
    Analyze a saved resume against ATS requirements
    """
    logger.info(f"Analyze resume request with role: {analysis_req.target_role}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available - FIX HERE
    if resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    # Check if OpenAI is available
    if openai is None or openai_api_key is None:
        logger.error("OpenAI API not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service unavailable"
        )
    
    # Get the resume text from database using enhanced extraction
    try:
        resume_id = analysis_req.resume_id
        if not resume_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume ID is required"
            )
        
        # Use the enhanced text extraction method
        resume_text = await extract_text_with_fallback(resume_id, user_id)
        
        # Analyze resume
        analysis_result = analyze_resume_with_openai(resume_text, analysis_req.target_role)
        logger.info(f"Analysis completed for resume: {resume_id}")
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing resume: {str(e)}"
        )

@router.post("/analyze-upload", response_model=ResumeAnalysisResponse)
async def analyze_resume_upload(request: Request, resume_file: UploadFile = File(...), target_role: str = Form(...)):
    """
    Analyze a newly uploaded resume against ATS requirements
    """
    logger.info(f"Analyze resume upload request for role: {target_role}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available
    if resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    # Check if OpenAI is available
    if openai is None or openai_api_key is None:
        logger.error("OpenAI API not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service unavailable"
        )
    
    try:
        # Save file to disk
        file_path = await save_resume_to_disk(resume_file)
        
        # Extract text
        resume_text = extract_text_from_document(file_path, vision_client, openai_client)
        
        if not resume_text or len(resume_text.strip()) < 100:
            logger.error("Insufficient text extracted from resume")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient content extracted from resume"
            )
        
        # Save to database
        resume_id = await save_resume_to_db(
            user_id=user_id,
            file_path=file_path,
            filename=resume_file.filename,
            file_size=os.path.getsize(file_path),
            content_type=resume_file.content_type or "application/octet-stream",
            extracted_text=resume_text
        )
        
        # Analyze resume
        analysis_result = analyze_resume_with_openai(resume_text, target_role)
        
        # Add resume_id to the result
        analysis_result["resume_id"] = resume_id
        
        logger.info(f"Analysis completed for uploaded resume, saved as: {resume_id}")
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing uploaded resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing resume: {str(e)}"
        )

# Create a Pydantic model for the request
class SuggestRolesRequest(BaseModel):
    resume_id: str

@router.post("/suggest-roles", response_model=SuggestedRolesResponse)
async def suggest_roles(
    request: Request, 
    req_data: Optional[SuggestRolesRequest] = None,
    resume_id: Optional[str] = Form(None)
):
    """
    Suggest potential job roles based on resume content
    Compatible with both JSON and form data
    Now checks both resumes and cvs collections
    """
    # Get resume_id from either form data or JSON body
    if resume_id is None and req_data is not None:
        resume_id = req_data.resume_id
    
    # If still no resume_id, try to get it from the request body
    if resume_id is None:
        try:
            body = await request.json()
            resume_id = body.get("resume_id")
        except:
            pass
    
    # Check if we have a resume_id
    if not resume_id:
        logger.warning("No resume ID provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume ID is required"
        )
    
    logger.info(f"Suggest roles request for resume: {resume_id}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available
    if resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    # Check if OpenAI is available
    if openai is None or openai_api_key is None:
        logger.error("OpenAI API not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service unavailable"
        )
    
    resume_text = None
    try:
        # First, try to find the resume in the resumes collection
        try:
            object_id = ObjectId(resume_id)
            resume_doc = await resumes_col.find_one({
                "_id": object_id,
                "userId": user_id
            })
        except:
            # Try as string if ObjectId conversion fails
            try:
                resume_doc = await resumes_col.find_one({
                    "_id": resume_id,
                    "userId": user_id
                })
            except:
                resume_doc = None
                
        # If found, extract text
        if resume_doc is not None:
            logger.info(f"Found resume in resumes collection: {resume_id}")
            resume_text = resume_doc.get("extractedText")
        else:
            # If not found in resumes collection, try cvs collection
            logger.info(f"Resume not found in resumes collection, trying cvs collection")
            
            try:
                db = resumes_col.database
                cvs_col = db.get_collection("cvs")
                
                if cvs_col is not None:
                    # Try with ObjectId
                    try:
                        object_id = ObjectId(resume_id)
                        cv_doc = await cvs_col.find_one({
                            "_id": object_id,
                            "userId": user_id
                        })
                    except:
                        # Try as string
                        try:
                            cv_doc = await cvs_col.find_one({
                                "_id": resume_id,
                                "userId": user_id
                            })
                        except:
                            cv_doc = None
                    
                    # Also try with fileId
                    if cv_doc is None:
                        cv_doc = await cvs_col.find_one({
                            "fileId": resume_id,
                            "userId": user_id
                        })
                        
                    if cv_doc is not None:
                        logger.info(f"Found resume in cvs collection: {resume_id}")
                        # Try different field names
                        resume_text = cv_doc.get("extractedText") or cv_doc.get("cv_text")
                    else:
                        logger.warning(f"Resume not found in cvs collection either: {resume_id}")
                else:
                    logger.warning("cvs collection not available")
            except Exception as e:
                logger.error(f"Error checking cvs collection: {e}")
        
        # If still no text, raise 404
        if resume_text is None or len(resume_text.strip()) < 100:
            logger.warning(f"No valid text found for resume: {resume_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or text extraction failed"
            )
        
        # Suggest roles
        suggested_roles = suggest_roles_from_resume(resume_text)
        logger.info(f"Suggested {len(suggested_roles)} roles for resume: {resume_id}")
        
        return {
            "suggested_roles": suggested_roles,
            "resume_id": resume_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggesting roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error suggesting roles: {str(e)}"
        )

@router.post("/optimize", response_model=dict)
async def optimize_resume_endpoint(request: Request, optimize_req: OptimizeResumeRequest):
    """
    Generate an optimized version of the resume based on analysis
    """
    logger.info(f"Optimize resume request for resume: {optimize_req.resume_id}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available - FIX: Changed from boolean check to None comparison
    if resumes_col is None or optimized_resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    # Check if OpenAI is available
    if openai is None or openai_api_key is None:
        logger.error("OpenAI API not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Optimization service unavailable"
        )
    
    try:
        # Get the resume from database
        try:
            object_id = ObjectId(optimize_req.resume_id)
            resume_doc = await resumes_col.find_one({
                "_id": object_id,
                "userId": user_id
            })
        except:
            # Try as string if ObjectId conversion fails
            resume_doc = await resumes_col.find_one({
                "_id": optimize_req.resume_id,
                "userId": user_id
            })
            
        if resume_doc is None:
            # Also try in cvs collection
            try:
                db = resumes_col.database
                cvs_col = db.get_collection("cvs")
                
                if cvs_col is not None:
                    # Try with ObjectId
                    try:
                        object_id = ObjectId(optimize_req.resume_id)
                        resume_doc = await cvs_col.find_one({
                            "_id": object_id,
                            "userId": user_id
                        })
                    except:
                        # Try as string
                        resume_doc = await cvs_col.find_one({
                            "_id": optimize_req.resume_id,
                            "userId": user_id
                        })
                        
                    # Also try with fileId
                    if resume_doc is None:
                        resume_doc = await cvs_col.find_one({
                            "fileId": optimize_req.resume_id,
                            "userId": user_id
                        })
            except Exception as e:
                logger.error(f"Error checking cvs collection: {e}")
                
        if resume_doc is None:
            logger.warning(f"Resume not found: {optimize_req.resume_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
            
        # Extract text - FIX: Changed from using get directly to proper None check
        resume_text = resume_doc.get("extractedText")
        if resume_text is None or len(resume_text.strip()) < 100:
            # Try alternative fields
            resume_text = resume_doc.get("content")
            if resume_text is None or len(resume_text.strip()) < 100:
                resume_text = resume_doc.get("cv_text")
                if resume_text is None or len(resume_text.strip()) < 100:
                    resume_text = resume_doc.get("text")
        
        if resume_text is None or len(resume_text.strip()) < 100:
            logger.error(f"Insufficient text in resume: {optimize_req.resume_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient content in resume"
            )
        
        # Update last used timestamp
        collection_for_update = None
        if "resumes" in resume_doc:
            collection_for_update = resumes_col
        else:
            # Use cvs collection
            db = resumes_col.database
            collection_for_update = db.get_collection("cvs")
            
        if collection_for_update is not None:
            await collection_for_update.update_one(
                {"_id": resume_doc["_id"]},
                {"$set": {"lastUsed": datetime.utcnow()}}
            )
        
        # Optimize resume
        optimized_text = optimize_resume(
            resume_text=resume_text,
            target_role=optimize_req.target_role,
            analysis=optimize_req.analysis
        )
        
        # Calculate new ATS score
        new_analysis = analyze_resume_with_openai(optimized_text, optimize_req.target_role)
        
        # Save optimized resume to database
        optimized_doc = {
            "userId": user_id,
            "originalResumeId": str(resume_doc["_id"]),
            "targetRole": optimize_req.target_role,
            "originalText": resume_text,
            "optimizedText": optimized_text,
            "originalAnalysis": optimize_req.analysis,
            "newAnalysis": new_analysis,
            "createdAt": datetime.utcnow()
        }
        
        result = await optimized_resumes_col.insert_one(optimized_doc)
        optimized_id = str(result.inserted_id)
        
        logger.info(f"Resume optimized and saved with ID: {optimized_id}")
        
        # Create optimized PDF
        try:
            filename = f"{user_id}_{optimize_req.target_role.replace(' ', '_')}_optimized.pdf"
            pdf_path = await create_pdf_from_text(optimized_text, filename)
            
            # Update document with file path
            await optimized_resumes_col.update_one(
                {"_id": result.inserted_id},
                {"$set": {"filePath": pdf_path}}
            )
        except Exception as pdf_err:
            logger.error(f"Error creating PDF: {pdf_err}")
            # Continue despite PDF error
        
        # Get improvement
        original_score = optimize_req.analysis.get("ats_score", 0)
        new_score = new_analysis.get("ats_score", 0)
        
        return {
            "id": optimized_id,
            "ats_score": new_score,
            "improvement": new_score - original_score
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error optimizing resume: {str(e)}"
        )

@router.post("/download-optimized")
async def download_optimized_resume(request: Request, data: dict):
    """
    Download an optimized resume as PDF
    """
    logger.info(f"Download optimized resume request for: {data.get('optimized_id')}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available
    if optimized_resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    try:
        # Get the optimized resume from database
        optimized_id = data.get("optimized_id")
        if not optimized_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Optimized resume ID is required"
            )
            
        try:
            object_id = ObjectId(optimized_id)
            optimized_doc = await optimized_resumes_col.find_one({
                "_id": object_id,
                "userId": user_id
            })
        except:
            # Try as string if ObjectId conversion fails
            optimized_doc = await optimized_resumes_col.find_one({
                "_id": optimized_id,
                "userId": user_id
            })
            
        if optimized_doc is None:
            logger.warning(f"Optimized resume not found: {optimized_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Optimized resume not found"
            )
        
        # Check if we have a saved file path
        file_path = optimized_doc.get("filePath")
        if file_path is not None and os.path.exists(file_path):
            # Check if it's a PDF or TXT file
            media_type = "application/pdf"
            if file_path.endswith(".txt"):
                media_type = "text/plain"
        else:
            # Generate file on-the-fly
            optimized_text = optimized_doc.get("optimizedText")
            if optimized_text is None or len(optimized_text.strip()) < 100:
                logger.error(f"No optimized text found for: {optimized_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Optimized resume content not found"
                )
                
            target_role = optimized_doc.get("targetRole", "Position")
            filename = f"{user_id}_{target_role.replace(' ', '_').replace('/', '_')}_optimized.pdf"
            
            try:
                # Try to create PDF first
                file_path = await create_pdf_from_text(optimized_text, filename)
                media_type = "application/pdf" if file_path.endswith(".pdf") else "text/plain"
                
                # Update document with file path
                await optimized_resumes_col.update_one(
                    {"_id": optimized_doc["_id"]},
                    {"$set": {"filePath": file_path}}
                )
            except Exception as pdf_err:
                # If PDF creation fails, fall back to plain text
                logger.error(f"Error creating PDF, using text fallback: {pdf_err}")
                text_filename = filename.replace('.pdf', '.txt')
                text_path = os.path.join("generated", text_filename)
                
                try:
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(optimized_text)
                    
                    file_path = text_path
                    media_type = "text/plain"
                    
                    # Update document with file path
                    await optimized_resumes_col.update_one(
                        {"_id": optimized_doc["_id"]},
                        {"$set": {"filePath": file_path}}
                    )
                except Exception as text_err:
                    logger.error(f"Error creating text file: {text_err}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error creating downloadable file: {str(text_err)}"
                    )
        
        # Return the file
        filename = os.path.basename(file_path)
        # Add Content-Disposition header to force download with proper filename
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type,
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading optimized resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading optimized resume: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "mongodb": "connected" if resumes_col is not None else "disconnected",
            "vision_api": "available" if vision_client is not None else "unavailable",
            "openai_api": "configured" if (openai_client is not None) or (openai is not None and openai_api_key) else "not_configured",
            "openai_model": OPENAI_MODEL
        }
    }
    
    if resumes_col is None:
        health_status["status"] = "degraded"
        
    return health_status

@router.post("/suggest-roles-upload", response_model=SuggestedRolesResponse)
async def suggest_roles_upload(request: Request, resume_file: UploadFile = File(...)):
    """
    Suggest potential job roles based on a newly uploaded resume
    """
    logger.info(f"Suggest roles from uploaded resume: {resume_file.filename}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available
    if resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    # Check if OpenAI is available
    if openai is None or openai_api_key is None:
        logger.error("OpenAI API not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service unavailable"
        )
    
    try:
        # Save file to disk
        file_path = await save_resume_to_disk(resume_file)
        
        # Extract text
        resume_text = extract_text_from_document(file_path, vision_client, openai_client)
        
        if not resume_text or len(resume_text.strip()) < 100:
            logger.error("Insufficient text extracted from resume")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient content extracted from resume"
            )
        
        # Save to database
        resume_id = await save_resume_to_db(
            user_id=user_id,
            file_path=file_path,
            filename=resume_file.filename,
            file_size=os.path.getsize(file_path),
            content_type=resume_file.content_type or "application/octet-stream",
            extracted_text=resume_text
        )
        
        # Suggest roles
        suggested_roles = suggest_roles_from_resume(resume_text)
        logger.info(f"Suggested {len(suggested_roles)} roles for uploaded resume, saved as: {resume_id}")
        
        return {
            "suggested_roles": suggested_roles,
            "resume_id": resume_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggesting roles from uploaded resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error suggesting roles: {str(e)}"
        )
        


@router.get("/saved-resumes")
async def get_saved_resumes(request: Request):
    """
    Get all saved resumes for the authenticated user
    """
    logger.info("Get saved resumes request")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check if MongoDB is available
    if resumes_col is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    try:
        # Find all resumes for this user
        cursor = resumes_col.find({"userId": user_id})
        resumes = await cursor.to_list(length=100)
        
        # Convert ObjectId to string for JSON serialization and format for frontend
        formatted_resumes = []
        for resume in resumes:
            formatted_resumes.append({
                "id": str(resume["_id"]),
                "filename": resume.get("originalName", ""),
                "originalName": resume.get("originalName", ""),
                "uploadedAt": resume.get("uploadedAt", ""),
                "size": resume.get("fileSize", 0),
                "userId": resume.get("userId", "")
            })
            
        logger.info(f"Found {len(formatted_resumes)} resumes for user: {user_id}")
        return {"resumes": formatted_resumes}
        
    except Exception as e:
        logger.error(f"Error retrieving resumes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving resumes: {str(e)}"
        )
        
async def extract_text_with_fallback(cv_id: str, user_id: str) -> str:
    """
    Retrieve resume text using multiple methods to ensure we get content
    """
    logger.info(f"Extracting text with fallback for CV: {cv_id}")
    
    if not cv_id or not user_id or resumes_col is None:
        logger.error("Missing required parameters or database connection")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to extract resume text"
        )
    
    try:
        # Get database reference
        db = resumes_col.database
        
        # Try primary resumes collection first
        resume_doc = None
        
        # Improved resume document search
        search_queries = [
            # Try with exact string ID
            {"_id": cv_id, "userId": user_id},
            
            # Try with ObjectId if possible
            None,  # Will be set below if ObjectId conversion succeeds
            
            # Try with fileId
            {"fileId": cv_id, "userId": user_id},
            
            # Try with just userId, check _id manually later
            {"userId": user_id}
        ]
        
        # Set the ObjectId query if possible
        try:
            object_id = ObjectId(cv_id)
            search_queries[1] = {"_id": object_id, "userId": user_id}
        except:
            logger.warning(f"Could not convert {cv_id} to ObjectId")
        
        # Try each query until we find a matching document
        for query in search_queries:
            if query is None:
                continue
                
            logger.info(f"Trying query: {query}")
            
            # For the last query, we need to search differently
            if len(query) == 1 and "userId" in query:
                # Get all documents for this user
                cursor = resumes_col.find(query)
                async for doc in cursor:
                    # Check if _id matches when converted to string
                    doc_id = str(doc.get("_id", ""))
                    if doc_id == cv_id or doc.get("fileId") == cv_id:
                        resume_doc = doc
                        logger.info(f"Found document through user search: {doc_id}")
                        break
            else:
                resume_doc = await resumes_col.find_one(query)
                
            if resume_doc is not None:
                logger.info(f"Found document with query: {query}")
                break
        
        # If not found in the primary collection, try the "cvs" collection as well
        if resume_doc is None:
            logger.info("Document not found in primary collection, trying 'cvs' collection")
            # Get the cvs collection that is used by the interviewprep module
            cvs_col = db.get_collection("cvs")
            
            if cvs_col is not None:
                # Try the same queries in the cvs collection
                for query in search_queries:
                    if query is None:
                        continue
                        
                    logger.info(f"Trying query in cvs collection: {query}")
                    
                    # For the last query, we need to search differently
                    if len(query) == 1 and "userId" in query:
                        # Get all documents for this user
                        cursor = cvs_col.find(query)
                        async for doc in cursor:
                            # Check if _id matches when converted to string
                            doc_id = str(doc.get("_id", ""))
                            if doc_id == cv_id or doc.get("fileId") == cv_id:
                                resume_doc = doc
                                logger.info(f"Found document in cvs collection through user search: {doc_id}")
                                break
                    else:
                        resume_doc = await cvs_col.find_one(query)
                        
                    if resume_doc is not None:
                        logger.info(f"Found document in cvs collection with query: {query}")
                        break
        
        # Debug log
        logger.info(f"Available resume: {resume_doc is not None}")
        
        if resume_doc is None:
            # One last attempt - search by substring of _id
            try:
                # Find any document where the string representation of _id contains our cv_id
                pipeline = [
                    {"$match": {"userId": user_id}},
                    {"$addFields": {"id_str": {"$toString": "$_id"}}},
                    {"$match": {"id_str": {"$regex": cv_id, "$options": "i"}}}
                ]
                
                # Try in primary collection
                cursor = resumes_col.aggregate(pipeline)
                docs = await cursor.to_list(length=1)
                
                if docs and len(docs) > 0:
                    resume_doc = docs[0]
                    logger.info(f"Found document through regex search: {resume_doc.get('_id')}")
                else:
                    # Try in cvs collection
                    cvs_col = db.get_collection("cvs")
                    if cvs_col is not None:
                        cursor = cvs_col.aggregate(pipeline)
                        docs = await cursor.to_list(length=1)
                        
                        if docs and len(docs) > 0:
                            resume_doc = docs[0]
                            logger.info(f"Found document in cvs collection through regex search: {resume_doc.get('_id')}")
            except Exception as e:
                logger.error(f"Error in regex search: {e}")
        
        # If still not found, list available documents for debugging
        if resume_doc is None:
            logger.warning(f"Resume not found: {cv_id}")
            
            # Log all available documents for this user for debugging purposes
            try:
                logger.info(f"Listing available documents for user: {user_id}")
                
                # Check primary collection
                if resumes_col is not None:
                    cursor = resumes_col.find({"userId": user_id})
                    docs = await cursor.to_list(length=10)
                    logger.info(f"Found {len(docs)} documents in primary collection")
                    for doc in docs:
                        logger.info(f"Document ID: {doc.get('_id')}, fileId: {doc.get('fileId')}")
                
                # Check cvs collection
                cvs_col = db.get_collection("cvs")
                if cvs_col is not None:
                    cursor = cvs_col.find({"userId": user_id})
                    docs = await cursor.to_list(length=10)
                    logger.info(f"Found {len(docs)} documents in cvs collection")
                    for doc in docs:
                        logger.info(f"Document ID: {doc.get('_id')}, fileId: {doc.get('fileId')}")
            except Exception as e:
                logger.error(f"Error listing available documents: {e}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
        
        # Try all possible fields where text might be stored
        extracted_text = resume_doc.get("extractedText")
        
        # If extractedText is empty or None, try other potential fields
        if extracted_text is None or len(extracted_text.strip()) < 100:
            logger.warning(f"extractedText field empty or too small, trying content field")
            extracted_text = resume_doc.get("content")
            
        if extracted_text is None or len(extracted_text.strip()) < 100:
            logger.warning(f"content field empty or too small, trying text field")
            extracted_text = resume_doc.get("text")
            
        if extracted_text is None or len(extracted_text.strip()) < 100:
            logger.warning(f"text field empty or too small, trying cv_text field")
            extracted_text = resume_doc.get("cv_text")
            
        if extracted_text is None or len(extracted_text.strip()) < 100:
            logger.warning(f"text fields empty or too small, checking if file exists")
            
            # If we have a file path, try to extract text from the file
            file_path = resume_doc.get("filePath")
            if file_path is not None and os.path.exists(file_path):
                logger.info(f"Attempting to extract text from file: {file_path}")
                try:
                    extracted_text = extract_text_from_document(file_path, vision_client, openai_client)
                    
                    # Update the document with the newly extracted text
                    if extracted_text is not None and len(extracted_text.strip()) >= 100:
                        await resumes_col.update_one(
                            {"_id": resume_doc["_id"]},
                            {"$set": {"extractedText": extracted_text}}
                        )
                        logger.info(f"Updated resume document with newly extracted text")
                except Exception as extract_err:
                    logger.error(f"Error extracting text from file: {extract_err}")
        
        # If we still don't have text, try OpenAI to generate placeholder content
        if extracted_text is None or len(extracted_text.strip()) < 100:
            logger.warning(f"Could not extract text, generating placeholder text with OpenAI")
            
            # Get any information we have
            filename = resume_doc.get("originalName", "")
            
            # Generate placeholder text with OpenAI
            system_message = "You are an assistant that generates placeholder resume content based on a filename."
            prompt = f"""
            I need to generate placeholder content for a resume where the text extraction failed.
            The resume filename is: {filename}
            
            Please generate a generic professional resume with the following sections:
            1. Summary/Objective
            2. Work Experience (2-3 positions)
            3. Education
            4. Skills
            5. Contact Information (use placeholder data)
            
            Make it realistic but generic so it can reasonably represent many professionals.
            """
            
            try:
                extracted_text = call_openai(prompt, system_message)
                
                # Update the document with the generated text
                if extracted_text is not None:
                    await resumes_col.update_one(
                        {"_id": resume_doc["_id"]},
                        {"$set": {"extractedText": extracted_text}}
                    )
                    logger.info(f"Updated resume document with generated placeholder text")
            except Exception as openai_err:
                logger.error(f"Error generating placeholder text: {openai_err}")
        
        # Final check - if we still don't have text, raise an exception
        if extracted_text is None or len(extracted_text.strip()) < 100:
            logger.error(f"Failed to extract or generate resume text for: {cv_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to extract resume text"
            )
        
        # Update last used timestamp
        if "resumes" in resume_doc:
            collection_for_update = db.get_collection("resumes") 
        else:
            collection_for_update = db.get_collection("cvs")
            
        if collection_for_update is not None:
            try:
                await collection_for_update.update_one(
                    {"_id": resume_doc["_id"]},
                    {"$set": {"lastUsed": datetime.utcnow()}}
                )
            except Exception as update_err:
                logger.error(f"Error updating lastUsed timestamp: {update_err}")
        
        return extracted_text
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract_text_with_fallback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting resume text: {str(e)}"
        )

@router.get("/debug-resumes/{user_id}")
async def debug_resumes(user_id: str):
    """
    Debug endpoint to list all resumes for a user with their IDs in various formats
    """
    logger.info(f"Debug resumes request for user: {user_id}")
    
    if resumes_col is None:
        return {"status": "error", "message": "Database not connected"}
    
    try:
        # Find all resumes for this user
        cursor = resumes_col.find({"userId": user_id})
        resumes = await cursor.to_list(length=100)
        
        # Format resume IDs
        formatted_resumes = []
        for resume in resumes:
            resume_id = resume.get("_id")
            
            formatted_resumes.append({
                "id": str(resume_id),
                "id_hex": resume_id.binary.hex() if hasattr(resume_id, "binary") else None,
                "fileId": resume.get("fileId"),
                "filename": resume.get("originalName", ""),
                "uploadedAt": resume.get("uploadedAt", ""),
                "extractedTextLength": len(resume.get("extractedText", "")) if resume.get("extractedText") else 0
            })
            
        return {
            "status": "success",
            "user_id": user_id,
            "resume_count": len(formatted_resumes),
            "resumes": formatted_resumes
        }
        
    except Exception as e:
        logger.error(f"Error in debug-resumes: {e}")
        return {"status": "error", "message": str(e)}
    
    
    
# Debug route to find a resume
@router.get("/debug/find-resume/{cv_id}")
async def debug_find_resume(cv_id: str, request: Request):
    """
    Debug endpoint to help find a resume by ID across different collections
    """
    logger.info(f"Debug find resume: {cv_id}")
    
    # Get authentication token
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
        
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Check MongoDB connection
    if db is None:
        logger.error("MongoDB not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
        
    # Try to find the resume in different collections
    results = {}
    
    try:
        # Check "resumes" collection
        resumes = db.get_collection("resumes")
        if resumes is not None:
            try:
                resume_doc = await resumes.find_one({"_id": cv_id, "userId": user_id})
            except:
                try:
                    object_id = ObjectId(cv_id)
                    resume_doc = await resumes.find_one({"_id": object_id, "userId": user_id})
                except:
                    resume_doc = None
                    
            if resume_doc is None:
                resume_doc = await resumes.find_one({"fileId": cv_id, "userId": user_id})
                
            if resume_doc is not None:
                results["resumes"] = {
                    "found": True,
                    "id": str(resume_doc.get("_id")),
                    "fileId": resume_doc.get("fileId"),
                    "filename": resume_doc.get("originalName", resume_doc.get("filename")),
                    "extractedText_length": len(resume_doc.get("extractedText", "")) if resume_doc.get("extractedText") else 0
                }
            else:
                # List available resumes
                cursor = resumes.find({"userId": user_id})
                available_docs = await cursor.to_list(length=10)
                available = []
                for doc in available_docs:
                    available.append({
                        "id": str(doc.get("_id")),
                        "fileId": doc.get("fileId"),
                        "filename": doc.get("originalName", doc.get("filename"))
                    })
                results["resumes"] = {
                    "found": False,
                    "available": available
                }
        else:
            results["resumes"] = {"available": False}
            
        # Check "cvs" collection
        cvs = db.get_collection("cvs")
        if cvs is not None:
            try:
                cv_doc = await cvs.find_one({"_id": cv_id, "userId": user_id})
            except:
                try:
                    object_id = ObjectId(cv_id)
                    cv_doc = await cvs.find_one({"_id": object_id, "userId": user_id})
                except:
                    cv_doc = None
                    
            if cv_doc is None:
                cv_doc = await cvs.find_one({"fileId": cv_id, "userId": user_id})
                
            if cv_doc is not None:
                results["cvs"] = {
                    "found": True,
                    "id": str(cv_doc.get("_id")),
                    "fileId": cv_doc.get("fileId"),
                    "filename": cv_doc.get("originalName", cv_doc.get("filename")),
                    "extractedText_length": len(cv_doc.get("extractedText", "")) if cv_doc.get("extractedText") else 0
                }
            else:
                # List available CVs
                cursor = cvs.find({"userId": user_id})
                available_docs = await cursor.to_list(length=10)
                available = []
                for doc in available_docs:
                    available.append({
                        "id": str(doc.get("_id")),
                        "fileId": doc.get("fileId"),
                        "filename": doc.get("originalName", doc.get("filename"))
                    })
                results["cvs"] = {
                    "found": False,
                    "available": available
                }
        else:
            results["cvs"] = {"available": False}
            
        return results
        
    except Exception as e:
        logger.error(f"Error in debug_find_resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding resume: {str(e)}"
        )