import os
import uuid
import logging
import random
import motor.motor_asyncio
import jwt
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from .pdf_extraction import extract_text_from_document
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = "NE60hAlMyF6wVlOt5+VDKpaU/I6FJ4Oa5df1gpG/MTg="


try:
    from google.cloud import vision
except ImportError:
    logger.warning("Google Cloud Vision library not installed")
    vision = None

try:
    import openai
    from openai import OpenAI
except ImportError:
    logger.warning("OpenAI library not installed")
    openai = None
    OpenAI = None


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
logger.info(f"Using MongoDB URI: {MONGODB_URI}")

OPENAI_MODEL = "gpt-4.1-mini-2025-04-14"
logger.info(f"Using OpenAI model: {OPENAI_MODEL}")


MAX_INTERVIEW_QUESTIONS = int(os.getenv("MAX_INTERVIEW_QUESTIONS", "5"))
logger.info(f"Maximum interview questions set to: {MAX_INTERVIEW_QUESTIONS}")

openai_client = None
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai is not None:
    if openai_api_key:
        try:
            if hasattr(openai, 'OpenAI'):
                openai_client = OpenAI(api_key=openai_api_key)
                logger.info("OpenAI v1.x client initialized")
            else:
                logger.info("Using legacy OpenAI v0.x API")
                openai.api_key = openai_api_key
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    else:
        logger.warning("OpenAI API key not set")


gcp_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not gcp_credentials_path:
    logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set")

# Set up MongoDB and Google Vision clients
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    conversations_col = db["conversations"]
    users_col = db["users"]
    logger.info("MongoDB connection established")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    client = None
    db = None
    conversations_col = None
    users_col = None

vision_client = None
try:
    if vision is not None and gcp_credentials_path:
        vision_client = vision.ImageAnnotatorClient()
        logger.info("Google Vision client initialized")
except Exception as e:
    logger.warning(f"Could not initialize Vision client: {e}")


router = APIRouter()
logger.info("API Router created with no prefix")


# Pydantic Models
class ChatMessage(BaseModel):
    sender: str 
    text: str

class ChatResponse(BaseModel):
    messages: List[ChatMessage]

class ChatRequest(BaseModel):
    session_id: str
    user_message: str

class ConversationModel(BaseModel):
    _id: Optional[str]
    session_id: str
    user_id: str
    job_role: str
    cv_text: str
    messages: List[ChatMessage]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished: bool = False
    max_questions: int = Field(default=MAX_INTERVIEW_QUESTIONS)


# Helper Functions
async def save_cv_to_disk(cv_file: UploadFile) -> str:
    """
    Save the uploaded CV to the local 'uploads' folder.
    """
    try:
        logger.info(f"Saving CV file: {cv_file.filename}")
        os.makedirs("uploads", exist_ok=True)
        file_ext = os.path.splitext(cv_file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join("uploads", file_name)
        content = await cv_file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"CV saved to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving CV file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving CV file: {str(e)}"
        )

def extract_text_from_cv(file_path: str) -> str:
    """
    Extract text from CV using our improved document extraction module.
    Now includes OpenAI Vision API as a fallback for image-based PDFs.
    """
    logger.info(f"Extracting text from CV: {file_path}")
    
    try:
        extracted_text = extract_text_from_document(file_path, vision_client, openai_client)
        if extracted_text:
            logger.info(f"Successfully extracted {len(extracted_text)} characters from CV")
        else:
            logger.warning("No text extracted from CV")
            extracted_text = f"Failed to extract text from CV file: {os.path.basename(file_path)}"
        
        if len(extracted_text.strip()) < 100 and openai_client is not None:
            logger.warning(f"Extraction produced limited text ({len(extracted_text.strip())} characters), trying direct OpenAI Vision method")
            try:
                file_ext = os.path.splitext(file_path)[1].lower()
                content_type = "application/pdf" if file_ext == '.pdf' else "image/jpeg" if file_ext in ['.jpg', '.jpeg'] else "image/png"

                with open(file_path, "rb") as f:
                    file_content = f.read()
                file_b64 = base64.b64encode(file_content).decode('utf-8')

                response = openai_client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that extracts text from CV/resume documents."},
                        {"role": "user", "content": [
                            {"type": "text", "text": "Extract all the text content from this CV/resume document. Include all sections like personal info, education, experience, skills, etc. Format it clearly and preserve the structure."},
                            {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{file_b64}"}}
                        ]}
                    ],
                    max_tokens=4000
                )
                
                openai_text = response.choices[0].message.content
                if openai_text and len(openai_text.strip()) > len(extracted_text.strip()):
                    logger.info(f"OpenAI Vision extracted {len(openai_text)} characters - using this instead")
                    return openai_text
            except Exception as e:
                logger.error(f"OpenAI Vision direct extraction failed: {e}")
        
        return extracted_text
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return f"Error extracting text: {str(e)}"
        
def extract_text_with_openai(file_path: str, openai_client=None) -> str:
    """Extract text from document using OpenAI's Vision API."""
    if not openai_client:
        logger.warning("OpenAI client not provided, can't use OpenAI Vision API")
        return ""
    
    try:
        logger.info(f"Extracting text with OpenAI Vision API: {file_path}")
        file_ext = os.path.splitext(file_path)[1].lower()
        
        #  convert pdf to images
        if file_ext == '.pdf':
            logger.info("Converting PDF to image for OpenAI Vision processing")
            
            # Try using pdf2image
            if PDF2IMAGE_AVAILABLE:
                try:
               
                    with tempfile.TemporaryDirectory() as temp_dir:
                        images = convert_from_path(file_path, dpi=300, first_page=1, last_page=1, output_folder=temp_dir)
                        if images:
                            temp_img_path = os.path.join(temp_dir, "page_1.png")
                            images[0].save(temp_img_path, "PNG")
                            
                      
                            with open(temp_img_path, "rb") as f:
                                file_content = f.read()
                            file_b64 = base64.b64encode(file_content).decode('utf-8')
                            content_type = "image/png"
                        else:
                            logger.error("Failed to convert PDF to image")
                            return ""
                except Exception as e:
                    logger.error(f"Error converting PDF to image: {e}")
                    return f"Error converting PDF: {str(e)}"
            else:
                logger.error("pdf2image not available, cannot convert PDF for OpenAI Vision")
                return "Cannot process PDF without pdf2image library"
        else:
            with open(file_path, "rb") as f:
                file_content = f.read()
            file_b64 = base64.b64encode(file_content).decode('utf-8')
            
            if file_ext in ['.jpg', '.jpeg']:
                content_type = "image/jpeg"
            elif file_ext in ['.png']:
                content_type = "image/png"
            else:
                content_type = "image/jpeg"  
        
        # Call OpenAI vision model
        response = openai_client.chat.completions.create(
            model="gpt-4.1-vision-preview",  
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts text content from resume/CV documents."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract and organize all text content from this CV/resume document. Include all sections like personal info, education, experience, skills, etc. in a clean, structured format."},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{file_b64}"}}
                ]}
            ],
            max_tokens=4000
        )
        
        extracted_text = response.choices[0].message.content
        logger.info(f"Successfully extracted {len(extracted_text)} characters with OpenAI Vision API")
        return extracted_text
        
    except Exception as e:
        logger.error(f"Error extracting text with OpenAI Vision API: {e}")
        return f"Error extracting text with OpenAI: {str(e)}"

def call_openai(prompt: str) -> str:
    """
    Call OpenAI API with improved error handling and retry logic.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling OpenAI API with model {OPENAI_MODEL}")
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant that provides responses in valid JSON format when requested. Always ensure JSON responses are properly formatted."},
                {"role": "user", "content": prompt}
            ]
            
            if openai.__version__.startswith('0.'):
               
                response = openai.ChatCompletion.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                return response.choices[0].message.content.strip()
            else:
              
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
            time.sleep(2 ** attempt) 
    
    raise Exception("Failed to get response from OpenAI after all retries")

async def build_openai_prompt(
    cv_text: str,
    job_role: str,
    messages: List[Dict[str, str]],
    max_questions: int = MAX_INTERVIEW_QUESTIONS
) -> str:
    """
    Build a prompt for the AI model.
    """
    logger.info(f"Building prompt for {job_role} interview")
    system_instructions = (
        f"You are a highly knowledgeable AI interviewer, specializing in {job_role} interviews.\n"
        f"You have the candidate's CV:\n\n{cv_text}\n\n"
        f"Your goal is to ask questions one by one, evaluate correctness, and give professional yet friendly feedback. "
        f"If the candidate's answer is unclear or incomplete, politely ask for more details. "
        f"Continue until you've asked {max_questions} questions total or the candidate is done.\n\n"
        f"Please keep responses focused, realistic, and supportive. Ask questions that are personalized to the candidate's CV."
    )
    conversation_text = ""
    for msg in messages:
        if msg["sender"] == "ai":
            conversation_text += f"Interviewer: {msg['text']}\n"
        else:
            conversation_text += f"Candidate: {msg['text']}\n"
    prompt = (
        f"{system_instructions}\n\n"
        "Conversation so far:\n"
        f"{conversation_text}\n"
        "Interviewer:"
    )
    return prompt

def format_conversation(messages: List[Dict[str, str]]) -> str:
    """
    Format the conversation for the final feedback prompt.
    """
    lines = []
    for msg in messages:
        if msg["sender"] == "ai":
            lines.append(f"Interviewer: {msg['text']}")
        else:
            lines.append(f"Candidate: {msg['text']}")
    return "\n".join(lines)


# Routes
@router.post("/start")
async def start_interview(
    request: Request,
    background_tasks: BackgroundTasks,
    job_role: Optional[str] = Form(None),
    cv_file: Optional[UploadFile] = None,
    cv_id: Optional[str] = Form(None),
    auth_token: Optional[str] = Form(None),
    max_questions: Optional[int] = Form(MAX_INTERVIEW_QUESTIONS),
):
    """
    Start a new interview session with either a CV file upload or CV ID reference.
    """
    logger.info(f"Starting interview with job_role: {job_role}, cv_id: {cv_id}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    try:
        token = None

        token = request.cookies.get("token")
        logger.info(f"Token from cookies: {token is not None}")
        
        if not token and auth_token:
            token = auth_token
            logger.info(f"Token from form data: {token is not None}")

        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:] 
                logger.info(f"Token from Authorization header: {token is not None}")
        
        if not token:
            logger.warning("No authentication token found in any source")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
            
       
        try:
            logger.info(f"Verifying token")
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("userId")
            if not user_id:
                logger.warning("Invalid token: missing userId")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid authentication token"}
                )
            logger.info(f"User authenticated: {user_id}")
        except jwt.PyJWTError as e:
            logger.error(f"JWT decode error: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {str(e)}"}
            )

        
        if not job_role:
            logger.error("Missing job_role parameter")
            return JSONResponse(
                status_code=400,
                content={"detail": "Job role is required"}
            )
            
        if not cv_file and not cv_id:
            logger.error("Neither cv_file nor cv_id provided")
            return JSONResponse(
                status_code=400, 
                content={"detail": "Either CV file or CV ID must be provided"}
            )

       
        cv_text = None
        stored_cv_id = None
        
       
        try:
            from .cv_utils import (
                ensure_uploads_dir, generate_timestamp_id, clean_filename,
                get_potential_file_paths, save_cv_to_db, find_cv_by_id
            )
        except ImportError:
            logger.warning("cv_utils module not found, using built-in functions")
           
            ensure_uploads_dir = lambda: os.makedirs("/app/uploads", exist_ok=True) or "/app/uploads"
            generate_timestamp_id = lambda: f"{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))}"
            clean_filename = lambda f: f.replace(' ', '_').replace('/', '_').replace('\\', '_')
        
        
        if cv_file:
            logger.info(f"Processing uploaded CV file: {cv_file.filename}")
            try:
               
                uploads_dir = ensure_uploads_dir()
                timestamp_id = generate_timestamp_id()
                clean_filename_str = clean_filename(cv_file.filename)
                filename = f"{timestamp_id}_{clean_filename_str}"
                file_path = os.path.join(uploads_dir, filename)
                

                content = await cv_file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                await cv_file.seek(0) 
                
                logger.info(f"CV file saved: {file_path}")

                cv_text = extract_text_from_cv(file_path)
                
                if cv_text:
                    logger.info(f"Successfully extracted {len(cv_text)} characters from CV")
                    db = conversations_col.database
                    cv_collection = db.get_collection("cvs")
                    
                    if cv_collection is not None:
                        try:
                            cv_document = {
                                "_id": ObjectId(),
                                "userId": user_id,
                                "filename": filename,
                                "originalName": cv_file.filename,
                                "filePath": file_path,
                                "fileSize": len(content),
                                "contentType": cv_file.content_type or "application/octet-stream",
                                "extractedText": cv_text,
                                "uploadedAt": datetime.utcnow(),
                                "lastUsed": datetime.utcnow(),
                                "fileId": timestamp_id
                            }
                            
                            result = await cv_collection.insert_one(cv_document)
                            stored_cv_id = str(cv_document["_id"])
                            logger.info(f"Saved CV to MongoDB with ID: {stored_cv_id}")
                        except Exception as db_err:
                            logger.error(f"Error saving CV to MongoDB: {db_err}")
                    else:
                        logger.warning("CV collection not found in database")
                else:
                    logger.error("Failed to extract text from CV")
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Could not extract text from CV"}
                    )
            except Exception as e:
                logger.error(f"Error processing CV file: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"detail": f"Error processing CV file: {str(e)}"}
                )
        elif cv_id:
            logger.info(f"Looking up CV by ID: {cv_id}")
            db = conversations_col.database
            cv_collection = db.get_collection("cvs")
            
            if not cv_collection:
                logger.error("CV collection not found in database")
                return JSONResponse(
                    status_code=500,
                    content={"detail": "CV storage not available"}
                )
                

            try:
                if 'find_cv_by_id' in locals():
                    cv_document = await find_cv_by_id(db, cv_id, user_id)
                else:
           
                    try:
                        object_id = ObjectId(cv_id) if len(cv_id) == 24 else cv_id
                        cv_document = await cv_collection.find_one({
                            "_id": object_id,
                            "userId": user_id
                        })
                    except:
                        cv_document = await cv_collection.find_one({
                            "_id": cv_id,
                            "userId": user_id
                        })
                
                if not cv_document:
                    logger.warning(f"CV not found for ID: {cv_id}")
                    return JSONResponse(
                        status_code=404,
                        content={"detail": f"CV not found: {cv_id}"}
                    )
                    
                stored_cv_id = cv_id
                cv_text = cv_document.get("extractedText")

                if not cv_text or len(cv_text.strip()) < 100:
                    logger.info(f"No valid extracted text found, attempting to extract from file")
                    
                    if 'get_potential_file_paths' in locals():
                        potential_paths = get_potential_file_paths(cv_document)
                    else:
                        potential_paths = []
                        if "filePath" in cv_document:
                            potential_paths.append(cv_document["filePath"])
                        if "filename" in cv_document:
                            potential_paths.append(f"/app/uploads/{cv_document['filename']}")
                    
                    for path in potential_paths:
                        if os.path.exists(path):
                            logger.info(f"Found file at path: {path}")
                            try:
                                cv_text = extract_text_from_document(path, vision_client, openai_client)
                                if cv_text and len(cv_text.strip()) >= 100:
                                    logger.info(f"Successfully extracted {len(cv_text)} chars from file")

                                    try:
                                        await cv_collection.update_one(
                                            {"_id": cv_document["_id"]},
                                            {"$set": {
                                                "extractedText": cv_text,
                                                "lastUsed": datetime.utcnow()
                                            }}
                                        )
                                        logger.info(f"Updated CV document with extracted text")
                                    except Exception as update_err:
                                        logger.error(f"Failed to update CV document with extracted text: {update_err}")
                                        
                                    break
                            except Exception as extract_err:
                                logger.error(f"Error extracting text from file: {extract_err}")
                    
                    if not cv_text or len(cv_text.strip()) < 100:
                        logger.error("Could not extract sufficient text from CV file")
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Could not extract sufficient content from CV"}
                        )
                else:
                    try:
                        await cv_collection.update_one(
                            {"_id": cv_document["_id"]},
                            {"$set": {"lastUsed": datetime.utcnow()}}
                        )
                    except Exception as update_err:
                        logger.error(f"Failed to update CV last used timestamp: {update_err}")
                        
            except Exception as e:
                logger.error(f"Error retrieving CV: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"detail": f"Error retrieving CV: {str(e)}"}
                )

        if not cv_text or len(cv_text.strip()) < 100:
            logger.warning(f"Insufficient CV text: {len(cv_text) if cv_text else 0} chars")
            return JSONResponse(
                status_code=400,
                content={"detail": "Could not extract sufficient content from CV"}
            )
        session_id = str(uuid.uuid4())
        logger.info(f"Generated session ID: {session_id}")

        initial_ai_text = (
            f"Thank you for your CV for the {job_role} position. "
            "Let's begin the interview. Can you tell me about yourself?"
        )

        conversation_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "job_role": job_role,
            "cv_text": cv_text,
            "messages": [{"sender": "ai", "text": initial_ai_text}],
            "created_at": datetime.utcnow(),
            "finished": False,
            "max_questions": max_questions,
            "cv_id": stored_cv_id  
        }


        if conversations_col is not None:
            try:
                await conversations_col.insert_one(conversation_doc)
                logger.info(f"Saved conversation to MongoDB: {session_id}")
            except Exception as db_err:
                logger.error(f"MongoDB error: {db_err}")
               
        else:
            logger.warning("MongoDB not available, session not saved")

        
        response_data = {
            "session_id": session_id,
            "first_ai_message": {"sender": "ai", "text": initial_ai_text}
        }
        
  
        if stored_cv_id:
            response_data["cv_id"] = stored_cv_id
        
        logger.info(f"Returning response: {response_data}")
        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Unexpected error in start_interview: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred: {str(e)}"}
        )


@router.post("/chat", response_model=ChatResponse)
async def interview_chat(request: ChatRequest):
    """
    Continue an existing interview chat.
    """
    logger.info(f"Chat request for session: {request.session_id}")
    try:
        # Retrieve conversation from MongoDB
        if conversations_col is None:
            logger.warning("MongoDB not available")
            fallback_response = ChatResponse(
                messages=[
                    ChatMessage(sender="user", text=request.user_message),
                    ChatMessage(
                        sender="ai", 
                        text="I'm sorry, but the database is currently unavailable. Your message was received but we cannot access your interview history."
                    )
                ]
            )
            return fallback_response
            
        # Find the conversation
        convo = await conversations_col.find_one({"session_id": request.session_id})
        if not convo:
            logger.warning(f"Session not found: {request.session_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Session not found"}
            )

        # Check if conversation is finished
        if convo.get("finished", False):
            logger.info(f"Session already finished: {request.session_id}")
            return ChatResponse(
                messages=[ChatMessage(
                    sender="ai", 
                    text="This interview session is finished. Please start a new one if you wish to continue."
                )]
            )

        # Add user message to conversation
        messages = convo["messages"]
        messages.append({"sender": "user", "text": request.user_message})
        logger.info(f"Added user message to session {request.session_id}")

        max_questions = convo.get("max_questions", MAX_INTERVIEW_QUESTIONS)
        logger.info(f"Using max_questions={max_questions} for this session")

        # Check if we should provide final feedback
        ai_message_count = sum(1 for m in messages if m["sender"] == "ai")
        if ai_message_count >= max_questions:
            logger.info(f"Session {request.session_id} reached max questions ({max_questions}), generating final feedback")
            conversation_text = format_conversation(messages)
            feedback_prompt = (
                "You are a professional interviewer who just finished interviewing a candidate. "
                "Below is the entire conversation:\n\n"
                f"{conversation_text}\n\n"
                "Now, please provide a final, motivational, and human-like feedback summary for the candidate. "
                "Focus on strengths, areas to improve, and encouraging advice. "
                "End your feedback with a short, positive note of encouragement."
            )
            final_feedback = call_openai(feedback_prompt)
            messages.append({"sender": "ai", "text": final_feedback})
            
   
            await conversations_col.update_one(
                {"session_id": request.session_id},
                {"$set": {"messages": messages, "finished": True}}
            )
            logger.info(f"Session {request.session_id} completed with final feedback")
            
            return ChatResponse(
                messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
            )

        # Generate AI response for normal conversation flow
        logger.info(f"Generating AI response for session {request.session_id}")
        prompt = await build_openai_prompt(
            cv_text=convo["cv_text"],
            job_role=convo["job_role"],
            messages=messages,
            max_questions=max_questions
        )
        ai_reply = call_openai(prompt)
        messages.append({"sender": "ai", "text": ai_reply})
        
        # Update conversation in database
        try:
            await conversations_col.update_one(
                {"session_id": request.session_id},
                {"$set": {"messages": messages}}
            )
            logger.info(f"Updated conversation in database for session {request.session_id}")
        except Exception as db_err:
            logger.error(f"Error updating MongoDB: {db_err}")
        # Return the response
        return ChatResponse(
            messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in interview_chat: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred: {str(e)}"}
        )


@router.get("/sessions")
async def get_sessions(request: Request):
    """
    Get all interview sessions for the authenticated user.
    """
    logger.info("GET /sessions endpoint called")
    
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication token"}
            )
        logger.info(f"Token verified for user: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    

    if conversations_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        

    try:
        cursor = conversations_col.find(
            {"user_id": user_id},
            {
                "session_id": 1,
                "job_role": 1,
                "created_at": 1,
                "finished": 1,
                "messages": 1, 
            }
        ).sort("created_at", -1) 
        
        sessions = await cursor.to_list(length=100)  
        
        formatted_sessions = []
        for session in sessions:
            session_id = session.get("session_id", "")
            created_at = session.get("created_at", datetime.utcnow())

            formatted_session = {
                "id": session_id,
                "job_role": session.get("job_role", "Unknown"),
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
                "finished": session.get("finished", False),
                "message_count": len(session.get("messages", []))
            }
            formatted_sessions.append(formatted_session)
            
        logger.info(f"Retrieved {len(formatted_sessions)} sessions for user {user_id}")
        return JSONResponse(content={"sessions": formatted_sessions})
        
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error retrieving sessions: {str(e)}"}
        )

@router.get("/session/{session_id}")
async def get_session(session_id: str, request: Request):
    """
    Get a specific interview session by ID.
    """
    logger.info(f"GET /session/{session_id} endpoint called")
    
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication token"}
            )
        logger.info(f"Token verified for user: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )

    if conversations_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )

    try:
        session = await conversations_col.find_one({"session_id": session_id})
        
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Session not found"}
            )

        if session.get("user_id") != user_id:
            logger.warning(f"Unauthorized access attempt: user {user_id} trying to access session {session_id}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Unauthorized"}
            )
            
        response_data = {
            "session_id": session.get("session_id"),
            "job_role": session.get("job_role"),
            "created_at": session.get("created_at").isoformat() if isinstance(session.get("created_at"), datetime) else session.get("created_at"),
            "finished": session.get("finished", False),
            "messages": session.get("messages", []),
            "max_questions": session.get("max_questions", MAX_INTERVIEW_QUESTIONS)
        }
        
        logger.info(f"Retrieved session {session_id} for user {user_id}")
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error retrieving session: {str(e)}"}
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "mongodb": "connected" if conversations_col is not None else "disconnected",
            "vision_api": "available" if vision_client is not None else "unavailable",
            "openai_api": "configured" if (openai_client is not None) or (openai is not None and openai_api_key) else "not_configured",
            "openai_model": OPENAI_MODEL
        },
        "config": {
            "max_interview_questions": MAX_INTERVIEW_QUESTIONS
        }
    }
    
    if conversations_col is None:
        health_status["status"] = "degraded"
        
    return health_status



@router.get("/sessions/{user_id}")
async def get_user_sessions(user_id: str, request: Request):
    """
    Get all interview sessions for a user.
    """
    logger.info(f"Getting sessions for user: {user_id}")

    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        token_user_id = payload.get("userId")
        is_admin = payload.get("isAdmin", False)
        if token_user_id != user_id and not is_admin:
            logger.warning(f"Unauthorized access attempt: {token_user_id} trying to access {user_id}'s data")
            return JSONResponse(
                status_code=403,
                content={"detail": "Unauthorized access"}
            )
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )

    if conversations_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        
    try:
        cursor = conversations_col.find(
            {"user_id": user_id},
            {
                "session_id": 1,
                "job_role": 1,
                "created_at": 1,
                "finished": 1,
                "max_questions": 1,
               
            }
        ).sort("created_at", -1) 
        
        sessions = await cursor.to_list(length=100) 
        
        formatted_sessions = []
        for session in sessions:
            session["_id"] = str(session.get("_id", ""))
            if "created_at" in session:
                session["created_at"] = session["created_at"].isoformat()
            formatted_sessions.append(session)
            
        logger.info(f"Retrieved {len(formatted_sessions)} sessions for user {user_id}")
        return formatted_sessions
        
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error retrieving sessions: {str(e)}"}
        )

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """
    Delete an interview session.
    """
    logger.info(f"Deleting session: {session_id}")
    
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        is_admin = payload.get("isAdmin", False)
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    
    if conversations_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        
    session = await conversations_col.find_one({"session_id": session_id})
    if not session:
        logger.warning(f"Session not found: {session_id}")
        return JSONResponse(
            status_code=404,
            content={"detail": "Session not found"}
        )
        
    if session["user_id"] != user_id and not is_admin:
        logger.warning(f"Unauthorized delete attempt: {user_id} trying to delete session {session_id}")
        return JSONResponse(
            status_code=403,
            content={"detail": "Unauthorized access"}
        )
    result = await conversations_col.delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        logger.warning(f"Session not deleted: {session_id}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete session"}
        )
        
    logger.info(f"Successfully deleted session {session_id}")
    return JSONResponse(content={"detail": "Session deleted successfully"})


@router.get("/openai-version")
async def openai_version_check():
    """
    Check which version of OpenAI API is being used.
    """
    if openai is None:
        return {"status": "OpenAI not installed"}
    
    try:
        version_info = {
            "installed": True,
            "api_key_configured": bool(openai_api_key),
            "client_initialized": openai_client is not None,
            "model": OPENAI_MODEL
        }
        
        
        if hasattr(openai, "OpenAI"):
            version_info["version"] = "v1.x"
            version_info["client_type"] = "Modern client-based API"
        elif hasattr(openai, "ChatCompletion"):
            version_info["version"] = "v0.x (Legacy)"
            version_info["models_available"] = ["gpt-3.5-turbo", "gpt-4", OPENAI_MODEL]
        else:
            version_info["version"] = "Unknown"
            
        return version_info
    except Exception as e:
        return {
            "status": "Error checking OpenAI version",
            "error": str(e)
        }


@router.post("/process-cv")
async def process_cv(cv_file: UploadFile = File(...)):
    """
    Process a CV file and return extracted text.
    """
    try:
        file_path = await save_cv_to_disk(cv_file)
        cv_text = extract_text_from_cv(file_path)
        
        return {
            "status": "success",
            "filename": cv_file.filename,
            "file_size": os.path.getsize(file_path),
            "extracted_text_length": len(cv_text),
            "text_sample": cv_text[:500] + "..." if len(cv_text) > 500 else cv_text,
            "vision_api_available": vision_client is not None
        }
    except Exception as e:
        logger.error(f"Error processing CV: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error processing CV: {str(e)}"}
        )



@router.get("/api-status")
async def api_status():
    """
    Return the status of all dependent APIs.
    """
    status = {
        "mongodb": {
            "connected": conversations_col is not None,
            "uri": MONGODB_URI.replace(MONGODB_URI.split("@")[-1] if "@" in MONGODB_URI else MONGODB_URI, "***")
        },
        "openai": {
            "installed": openai is not None,
            "api_key_configured": bool(openai_api_key),
            "version": "v1.x" if hasattr(openai, "OpenAI") else "v0.x" if hasattr(openai, "Completion") else "unknown",
            "client_initialized": openai_client is not None,
            "model": OPENAI_MODEL
        },
        "google_vision": {
            "installed": vision is not None,
            "client_available": vision_client is not None,
            "credentials_path": gcp_credentials_path
        },
        "config": {
            "max_interview_questions": MAX_INTERVIEW_QUESTIONS
        }
    }
    
    if conversations_col is not None:
        try:
            await db.command({"ping": 1})
            status["mongodb"]["ping"] = "successful"
        except Exception as e:
            status["mongodb"]["ping"] = "failed"
            status["mongodb"]["error"] = str(e)

    if openai is not None and openai_api_key:
        try:
            test_response = call_openai("Hello, this is a test.")
            status["openai"]["test_call"] = "successful" if test_response else "failed"
            status["openai"]["response_length"] = len(test_response) if test_response else 0
        except Exception as e:
            status["openai"]["test_call"] = "failed"
            status["openai"]["error"] = str(e)
    
    return status


class ConfigUpdateRequest(BaseModel):
    max_interview_questions: int = Field(..., ge=1, le=20)
    api_key: Optional[str] = Field(None)

@router.post("/config/update")
async def update_config(request: Request, config_update: ConfigUpdateRequest):
    """
    Update global configuration settings for the interview system.
    Requires admin authentication.
    """
    global MAX_INTERVIEW_QUESTIONS, openai_api_key, openai_client

    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        is_admin = payload.get("isAdmin", False)
        
        if not is_admin:
            logger.warning(f"Non-admin user attempted to update config: {payload.get('userId')}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Admin access required"}
            )
            
        if config_update.max_interview_questions != MAX_INTERVIEW_QUESTIONS:
            old_value = MAX_INTERVIEW_QUESTIONS
            MAX_INTERVIEW_QUESTIONS = config_update.max_interview_questions
            logger.info(f"Updated MAX_INTERVIEW_QUESTIONS from {old_value} to {MAX_INTERVIEW_QUESTIONS}")
            
        if config_update.api_key:
            openai_api_key = config_update.api_key
            if openai is not None and hasattr(openai, 'OpenAI'):
                openai_client = OpenAI(api_key=openai_api_key)
                logger.info("Reinitialized OpenAI client with new API key")
            elif openai is not None:
                openai.api_key = openai_api_key
                logger.info("Updated OpenAI API key for legacy client")
                
        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "config": {
                "max_interview_questions": MAX_INTERVIEW_QUESTIONS,
                "openai_model": OPENAI_MODEL,
                "api_key_configured": bool(openai_api_key)
            }
        }
    
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error updating configuration: {str(e)}"}
        )


class SessionConfigUpdate(BaseModel):
    max_questions: int = Field(..., ge=1, le=20)

@router.patch("/sessions/{session_id}/config")
async def update_session_config(session_id: str, config: SessionConfigUpdate, request: Request):
    """
    Update configuration for a specific interview session.
    """
    logger.info(f"Updating config for session: {session_id}")
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        is_admin = payload.get("isAdmin", False)

        if conversations_col is None:
            logger.error("MongoDB not connected")
            return JSONResponse(
                status_code=503,
                content={"detail": "Database unavailable"}
            )
            
        session = await conversations_col.find_one({"session_id": session_id})
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Session not found"}
            )

        if session["user_id"] != user_id and not is_admin:
            logger.warning(f"Unauthorized config update attempt: {user_id} for session {session_id}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Unauthorized access"}
            )

        if session.get("finished", False):
            logger.warning(f"Attempted to update config for finished session: {session_id}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Cannot update finished session"}
            )
            
        result = await conversations_col.update_one(
            {"session_id": session_id},
            {"$set": {"max_questions": config.max_questions}}
        )
        
        if result.modified_count == 0:
            logger.warning(f"Session config not updated: {session_id}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update session configuration"}
            )
            
        logger.info(f"Updated max_questions to {config.max_questions} for session {session_id}")
        return JSONResponse(
            content={
                "detail": "Session configuration updated successfully",
                "session_id": session_id,
                "max_questions": config.max_questions
            }
        )
            
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    except Exception as e:
        logger.error(f"Error updating session config: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error updating session configuration: {str(e)}"}
        )


@router.post("/sessions/{session_id}/reset")
async def reset_session(session_id: str, request: Request):
    """
    Reset an interview session to start over while keeping the same CV and job role.
    """
    logger.info(f"Resetting session: {session_id}")
    
    token = request.cookies.get("token")
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        is_admin = payload.get("isAdmin", False)
        if conversations_col is None:
            logger.error("MongoDB not connected")
            return JSONResponse(
                status_code=503,
                content={"detail": "Database unavailable"}
            )
            
        session = await conversations_col.find_one({"session_id": session_id})
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Session not found"}
            )
            
        if session["user_id"] != user_id and not is_admin:
            logger.warning(f"Unauthorized reset attempt: {user_id} for session {session_id}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Unauthorized access"}
            )
            
        job_role = session["job_role"]
        initial_ai_text = (
            f"Thank you for uploading your CV for the {job_role} position. "
            "Let's begin the interview. Can you tell me about yourself?"
        )
        
        result = await conversations_col.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "messages": [{"sender": "ai", "text": initial_ai_text}],
                    "finished": False,
                    "created_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            logger.warning(f"Session not reset: {session_id}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to reset session"}
            )
            
        logger.info(f"Successfully reset session {session_id}")
        return JSONResponse(
            content={
                "detail": "Session reset successfully",
                "session_id": session_id,
                "first_ai_message": {"sender": "ai", "text": initial_ai_text}
            }
        )
            
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error resetting session: {str(e)}"}
        )


@router.post("/process-cv-with-ai")
async def process_cv_with_ai(cv_file: UploadFile = File(...)):
    """
    Process a CV file directly with OpenAI's vision model.
    Use this as a fallback when other extraction methods fail.
    """
    if openai_client is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "OpenAI client not configured"}
        )
    
    try:
        file_path = await save_cv_to_disk(cv_file)
        logger.info(f"CV saved for AI processing: {file_path}")
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in ['.pdf']:
            content_type = "application/pdf"
        elif file_ext in ['.jpg', '.jpeg']:
            content_type = "image/jpeg"
        elif file_ext in ['.png']:
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"
        
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4.1", 
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts text content from resume/CV documents."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Extract and organize all text content from this CV/resume document. Include all sections like personal info, education, experience, skills, etc. in a clean, structured format."},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{file_b64}"}}
                    ]}
                ],
                max_tokens=4000
            )
            
            extracted_text = response.choices[0].message.content
            logger.info(f"Successfully extracted {len(extracted_text)} characters with OpenAI")
            
            return {
                "status": "success",
                "filename": cv_file.filename,
                "file_size": len(file_content),
                "extracted_text_length": len(extracted_text),
                "text_sample": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
                "method": "openai_vision"
            }
            
        except Exception as e:
            logger.error(f"OpenAI processing error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"OpenAI processing error: {str(e)}"}
            )
    
    except Exception as e:
        logger.error(f"Error processing CV with AI: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error processing CV with AI: {str(e)}"}
        )