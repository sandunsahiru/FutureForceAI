import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import jwt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = "NE60hAlMyF6wVlOt5+VDKpaU/I6FJ4Oa5df1gpG/MTg="

# MongoDB (async) via Motor
import motor.motor_asyncio

# Google Cloud Vision
try:
    from google.cloud import vision
except ImportError:
    logger.warning("Google Cloud Vision library not installed")
    vision = None

# OpenAI (or Gemini)
try:
    import openai
    from openai import OpenAI
except ImportError:
    logger.warning("OpenAI library not installed")
    openai = None
    OpenAI = None

# For environment variables
from dotenv import load_dotenv

# ------------------------------------------------------------------
# Load environment variables from .env
# ------------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------------
# Configure environment variables
# ------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
logger.info(f"Using MongoDB URI: {MONGODB_URI}")

# Define the OpenAI model to use
OPENAI_MODEL = "gpt-4.1-mini-2025-04-14"
logger.info(f"Using OpenAI model: {OPENAI_MODEL}")

# Initialize OpenAI client (for v1.x)
openai_client = None
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai is not None:
    if openai_api_key:
        try:
            # Check for v1.x API
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

# For Google Cloud Vision:
gcp_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not gcp_credentials_path:
    logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set")

# ------------------------------------------------------------------
# Set up MongoDB and Google Vision clients
# ------------------------------------------------------------------
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

# Initialize Vision client if credentials are available
vision_client = None
try:
    if vision is not None and gcp_credentials_path:
        vision_client = vision.ImageAnnotatorClient()
        logger.info("Google Vision client initialized")
except Exception as e:
    logger.warning(f"Could not initialize Vision client: {e}")

# ------------------------------------------------------------------
# Create a FastAPI APIRouter without a prefix
# ------------------------------------------------------------------
router = APIRouter()
logger.info("API Router created with no prefix")

# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------

class ChatMessage(BaseModel):
    sender: str  # "user" or "ai"
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

# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------

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

def extract_text_with_vision(file_path: str) -> str:
    """
    Extract text from CV using Google Vision or fallback to placeholder.
    """
    logger.info(f"Extracting text from CV: {file_path}")
    
    # Use placeholder text if Vision client is not available
    if vision_client is None:
        logger.warning("Vision client not available, using placeholder text")
        return f"Sample CV content for testing. File: {os.path.basename(file_path)}"
        
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        image = vision.Image(content=content)
        response = vision_client.document_text_detection(image=image)
        
        if response.error.message:
            logger.error(f"Vision API error: {response.error.message}")
            return f"Error extracting text: {response.error.message}"
            
        extracted_text = response.full_text_annotation.text
        logger.info(f"Extracted {len(extracted_text)} characters")
        return extracted_text
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return f"Error extracting text: {str(e)}"

def call_openai(prompt: str) -> str:
    """
    Call OpenAI API or return fallback response.
    Compatible with both v0.x and v1.x OpenAI APIs.
    Uses the gpt-4.1-mini-2025-04-14 model.
    """
    logger.info(f"Calling OpenAI API with model {OPENAI_MODEL}")
    
    # Fallback if OpenAI is not configured
    if (openai_client is None) and (openai is None or not openai_api_key):
        logger.warning("OpenAI not configured, using fallback")
        return "This is a fallback response since OpenAI is not configured. In a real scenario, this would be an AI-generated response based on the conversation context."
    
    try:
        # First try with new v1.x client
        if openai_client is not None:
            logger.info("Using OpenAI v1.x API")
            
            # For chat models like gpt-4.1-mini-2025-04-14, we need to use the chat completion API
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional interviewer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        
        # Fallback to legacy v0.x API
        elif hasattr(openai, 'ChatCompletion'):
            logger.info("Using OpenAI v0.x legacy API")
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional interviewer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message["content"].strip()
        
        # If we can't determine the API version
        else:
            logger.error("Unsupported OpenAI API version")
            return "Error: Unsupported OpenAI API version. Please check your installation."
            
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return f"Error generating response: {str(e)}"

async def build_openai_prompt(
    cv_text: str,
    job_role: str,
    messages: List[Dict[str, str]]
) -> str:
    """
    Build a prompt for the AI model.
    """
    logger.info(f"Building prompt for {job_role} interview")
    system_instructions = (
        f"You are a highly knowledgeable AI interviewer, specializing in {job_role} interviews.\n"
        f"You have the candidate's CV:\n\n{cv_text}\n\n"
        "Your goal is to ask questions one by one, evaluate correctness, and give professional yet friendly feedback. "
        "If the candidate's answer is unclear or incomplete, politely ask for more details. "
        "Continue until you've asked 10 questions total or the candidate is done.\n\n"
        "Please keep responses focused, realistic, and supportive."
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

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/start")
async def start_interview(
    request: Request,
    cv_file: UploadFile = File(...),
    job_role: str = Form(...),
    auth_token: str = Form(None),  # Add this parameter to receive token from form data
):
    """
    Start a new interview session.
    """
    logger.info(f"Starting interview for job role: {job_role}")
    try:
        # 1) Check for auth token in multiple places
        # First try cookies
        token = request.cookies.get("token")
        logger.info(f"Token from cookies: {token is not None}")
        
        # If not in cookies, try form data
        if not token and auth_token:
            token = auth_token
            logger.info(f"Token from form data: {token is not None}")
            
        # If still not found, try Authorization header
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove 'Bearer ' prefix
                logger.info(f"Token from Authorization header: {token is not None}")
        
        if not token:
            logger.warning("No authentication token found")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
            
        # 2) Verify token
        try:
            logger.info(f"Verifying token: {token[:10]}...")
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

        # 3) Save CV file
        try:
            file_path = await save_cv_to_disk(cv_file)
            logger.info(f"CV file saved: {file_path}")
        except Exception as e:
            logger.error(f"Error saving CV: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Error saving CV: {str(e)}"}
            )

        # 4) Extract text (or use fallback)
        cv_text = extract_text_with_vision(file_path)

        # 5) Generate session ID
        session_id = str(uuid.uuid4())
        logger.info(f"Generated session ID: {session_id}")

        # 6) Create initial AI message
        initial_ai_text = (
            f"Thank you for uploading your CV for the {job_role} position. "
            "Let's begin the interview. Can you tell me about yourself?"
        )

        # 7) Create conversation document
        conversation_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "job_role": job_role,
            "cv_text": cv_text,
            "messages": [{"sender": "ai", "text": initial_ai_text}],
            "created_at": datetime.utcnow(),
            "finished": False
        }

        # 8) Save to MongoDB (if available)
        if conversations_col is not None:
            try:
                await conversations_col.insert_one(conversation_doc)
                logger.info(f"Saved conversation to MongoDB: {session_id}")
            except Exception as db_err:
                logger.error(f"MongoDB error: {db_err}")
                # Continue anyway - we'll return the session even if DB save fails
        else:
            logger.warning("MongoDB not available, session not saved")

        # 9) Prepare response
        response_data = {
            "session_id": session_id,
            "first_ai_message": {"sender": "ai", "text": initial_ai_text}
        }
        
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
        # 1) Retrieve conversation from MongoDB
        if conversations_col is None:
            logger.warning("MongoDB not available")
            # Fallback to a stateless response
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
            
        # 2) Find the conversation
        convo = await conversations_col.find_one({"session_id": request.session_id})
        if not convo:
            logger.warning(f"Session not found: {request.session_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Session not found"}
            )

        # 3) Check if conversation is finished
        if convo.get("finished", False):
            logger.info(f"Session already finished: {request.session_id}")
            return ChatResponse(
                messages=[ChatMessage(
                    sender="ai", 
                    text="This interview session is finished. Please start a new one if you wish to continue."
                )]
            )

        # 4) Add user message to conversation
        messages = convo["messages"]
        messages.append({"sender": "user", "text": request.user_message})
        logger.info(f"Added user message to session {request.session_id}")

        # 5) Check if we should provide final feedback
        ai_message_count = sum(1 for m in messages if m["sender"] == "ai")
        if ai_message_count >= 10:
            logger.info(f"Session {request.session_id} reached max questions, generating final feedback")
            
            # Generate final feedback
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
            
            # Mark conversation as finished
            await conversations_col.update_one(
                {"session_id": request.session_id},
                {"$set": {"messages": messages, "finished": True}}
            )
            logger.info(f"Session {request.session_id} completed with final feedback")
            
            return ChatResponse(
                messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
            )

        # 6) Generate AI response for normal conversation flow
        logger.info(f"Generating AI response for session {request.session_id}")
        prompt = await build_openai_prompt(
            cv_text=convo["cv_text"],
            job_role=convo["job_role"],
            messages=messages
        )
        ai_reply = call_openai(prompt)
        messages.append({"sender": "ai", "text": ai_reply})
        
        # 7) Update conversation in database
        try:
            await conversations_col.update_one(
                {"session_id": request.session_id},
                {"$set": {"messages": messages}}
            )
            logger.info(f"Updated conversation in database for session {request.session_id}")
        except Exception as db_err:
            logger.error(f"Error updating MongoDB: {db_err}")
            # Continue anyway - we'll return the messages even if DB update fails
        
        # 8) Return the response
        return ChatResponse(
            messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in interview_chat: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred: {str(e)}"}
        )

# ------------------------------------------------------------------
# Health check endpoint
# ------------------------------------------------------------------

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
        }
    }
    
    # Overall status depends on critical services
    if conversations_col is None:
        health_status["status"] = "degraded"
        
    return health_status

# ------------------------------------------------------------------
# Session management endpoints
# ------------------------------------------------------------------

@router.get("/sessions/{user_id}")
async def get_user_sessions(user_id: str, request: Request):
    """
    Get all interview sessions for a user.
    """
    logger.info(f"Getting sessions for user: {user_id}")
    
    # 1) Verify authentication
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
        
        # Only allow users to access their own sessions (or admin users)
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
    
    # 2) Check if MongoDB is available
    if conversations_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        
    # 3) Retrieve sessions
    try:
        cursor = conversations_col.find(
            {"user_id": user_id},
            {
                "session_id": 1,
                "job_role": 1,
                "created_at": 1,
                "finished": 1,
                # Exclude large fields like cv_text and full messages
            }
        ).sort("created_at", -1)  # Newest first
        
        sessions = await cursor.to_list(length=100)  # Limit to 100 sessions
        
        # Format the response
        formatted_sessions = []
        for session in sessions:
            # Convert ObjectId to string and format dates
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
    
    # 1) Verify authentication
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
    
    # 2) Check if MongoDB is available
    if conversations_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        
    # 3) Find the session
    session = await conversations_col.find_one({"session_id": session_id})
    if not session:
        logger.warning(f"Session not found: {session_id}")
        return JSONResponse(
            status_code=404,
            content={"detail": "Session not found"}
        )
        
    # 4) Check authorization
    if session["user_id"] != user_id and not is_admin:
        logger.warning(f"Unauthorized delete attempt: {user_id} trying to delete session {session_id}")
        return JSONResponse(
            status_code=403,
            content={"detail": "Unauthorized access"}
        )
        
    # 5) Delete the session
    result = await conversations_col.delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        logger.warning(f"Session not deleted: {session_id}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete session"}
        )
        
    logger.info(f"Successfully deleted session {session_id}")
    return JSONResponse(content={"detail": "Session deleted successfully"})

# ------------------------------------------------------------------
# OpenAI Client Version Check and Adaptation
# ------------------------------------------------------------------

@router.get("/openai-version")
async def openai_version_check():
    """
    Check which version of OpenAI API is being used.
    """
    if openai is None:
        return {"status": "OpenAI not installed"}
    
    try:
        # Try to detect which version of the OpenAI library is installed
        version_info = {
            "installed": True,
            "api_key_configured": bool(openai_api_key),
            "client_initialized": openai_client is not None,
            "model": OPENAI_MODEL
        }
        
        # Check for attributes specific to different versions
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

# ------------------------------------------------------------------
# Vision Processing Endpoint
# ------------------------------------------------------------------

@router.post("/process-cv")
async def process_cv(cv_file: UploadFile = File(...)):
    """
    Process a CV file and return extracted text.
    """
    try:
        # Save file
        file_path = await save_cv_to_disk(cv_file)
        
        # Extract text
        cv_text = extract_text_with_vision(file_path)
        
        # Return results
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

# ------------------------------------------------------------------
# Debug Endpoint for API-Dependent Features
# ------------------------------------------------------------------

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
        }
    }
    
    # Test MongoDB connection
    if conversations_col is not None:
        try:
            # Just check if we can run a simple command
            await db.command({"ping": 1})
            status["mongodb"]["ping"] = "successful"
        except Exception as e:
            status["mongodb"]["ping"] = "failed"
            status["mongodb"]["error"] = str(e)
    
    # Test OpenAI connection
    if openai is not None and openai_api_key:
        try:
            # Use a minimal API call to test connectivity
            test_response = call_openai("Hello, this is a test.")
            status["openai"]["test_call"] = "successful" if test_response else "failed"
            status["openai"]["response_length"] = len(test_response) if test_response else 0
        except Exception as e:
            status["openai"]["test_call"] = "failed"
            status["openai"]["error"] = str(e)
    
    return status