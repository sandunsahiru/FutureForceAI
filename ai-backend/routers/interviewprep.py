import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request  # <-- Added Request here
from pydantic import BaseModel, Field
import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "somefallback")

# MongoDB (async) via Motor
import motor.motor_asyncio

# Google Cloud Vision
from google.cloud import vision

# OpenAI (or Gemini)
import openai

# For environment variables
from dotenv import load_dotenv

# ------------------------------------------------------------------
# Load environment variables from .env
# ------------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------------
# Configure environment variables (example)
# ------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
openai.api_key = os.getenv("OPENAI_API_KEY")

# For Google Cloud Vision:
gcp_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not gcp_credentials_path:
    raise Exception(
        "Please set GOOGLE_APPLICATION_CREDENTIALS in your .env file to your GCP credentials JSON path."
    )

# ------------------------------------------------------------------
# Set up MongoDB and Google Vision clients
# ------------------------------------------------------------------
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client["futureforceai"]  # or your DB name
conversations_col = db["conversations"]
users_col = db["users"]

vision_client = vision.ImageAnnotatorClient()

# ------------------------------------------------------------------
# Create a FastAPI APIRouter instead of a full app
# ------------------------------------------------------------------
router = APIRouter()

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
    Save the uploaded CV to the local 'uploads' folder (create if it doesn't exist).
    Returns the file path for further processing.
    """
    os.makedirs("uploads", exist_ok=True)
    file_ext = os.path.splitext(cv_file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join("uploads", file_name)
    with open(file_path, "wb") as f:
        f.write(await cv_file.read())
    return file_path

def extract_text_with_vision(file_path: str) -> str:
    """
    Use Google Cloud Vision to extract text from a CV file (image/PDF).
    For DOC/DOCX, you typically convert to PDF or an image first.
    Raises an HTTPException if Cloud Vision encounters an error.
    """
    with open(file_path, "rb") as f:
        content = f.read()
    image = vision.Image(content=content)
    # Use the existing vision_client instance instead of creating a new one
    response = vision_client.document_text_detection(image=image)
    if response.error.message:
        raise HTTPException(
            status_code=500,
            detail=f"Google Cloud Vision Error: {response.error.message}",
        )
    extracted_text = response.full_text_annotation.text
    return extracted_text

async def build_openai_prompt(
    cv_text: str,
    job_role: str,
    messages: List[Dict[str, str]]
) -> str:
    """
    Build a prompt for the o3-mini model using:
    1) The candidate's CV text
    2) The target job role
    3) The conversation so far (both user and AI messages)
    """
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

def call_openai(prompt: str) -> str:
    """
    Call OpenAI's o3-mini model with a carefully crafted prompt.
    Adjust parameters like 'temperature' or 'max_tokens' to control style & length.
    Use 'stop' to prevent AI from continuing the candidate's lines.
    """
    try:
        response = openai.Completion.create(
            model="o3-mini",  # Replace with your actual model if necessary
            prompt=prompt,
            max_tokens=300,
            temperature=0.5,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            stop=["Candidate:", "Interviewer:"]
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "I'm sorry, but I'm having trouble generating a response right now."

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/start")
async def start_interview(
    request: Request,
    cv_file: UploadFile = File(...),
    job_role: str = Form(...),
):
    """
    1) Decode the user ID from the JWT cookie
    2) Save CV to disk
    3) Extract text with Google Cloud Vision
    4) Create a conversation record in MongoDB
    5) Return session_id and first AI message
    """
    try:
        # 1) Read and decode JWT from the cookie
        token = request.cookies.get("token")
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("userId")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        # 2) Save CV
        file_path = await save_cv_to_disk(cv_file)

        # 3) Extract text using Google Cloud Vision
        cv_text = extract_text_with_vision(file_path)

        # 4) Generate a unique session_id
        session_id = str(uuid.uuid4())

        # 5) Prepare the initial AI greeting
        initial_ai_text = (
            f"Thank you for uploading your CV for the {job_role} position. "
            "Let's begin the interview. Can you tell me about yourself?"
        )

        # 6) Create a conversation document
        conversation_doc = ConversationModel(
            session_id=session_id,
            user_id=user_id,
            job_role=job_role,
            cv_text=cv_text,
            messages=[ChatMessage(sender="ai", text=initial_ai_text)],
        )

        # 7) Insert conversation into MongoDB
        await conversations_col.insert_one(conversation_doc.dict(exclude={"_id"}))

        # 8) Return the session_id and the first AI message
        return {
            "session_id": session_id,
            "first_ai_message": {"sender": "ai", "text": initial_ai_text}
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"Unexpected error in start_interview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while starting the interview."
        )


@router.post("/chat", response_model=ChatResponse)
async def interview_chat(request: ChatRequest):
    """
    Receives user's message, fetches conversation from DB, calls OpenAI for next question/feedback,
    updates conversation in DB, returns updated messages.
    """
    try:
        convo = await conversations_col.find_one({"session_id": request.session_id})
        if not convo:
            raise HTTPException(status_code=404, detail="Session not found.")

        if convo.get("finished", False):
            final_msg = "This interview session is finished. Please start a new one if you wish to continue."
            return ChatResponse(messages=[ChatMessage(sender="ai", text=final_msg)])

        messages = convo["messages"]
        messages.append({"sender": "user", "text": request.user_message})

        ai_message_count = sum(1 for m in messages if m["sender"] == "ai")
        if ai_message_count >= 10:
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
            return ChatResponse(
                messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
            )

        prompt = await build_openai_prompt(
            cv_text=convo["cv_text"],
            job_role=convo["job_role"],
            messages=messages
        )
        ai_reply = call_openai(prompt)
        messages.append({"sender": "ai", "text": ai_reply})
        await conversations_col.update_one(
            {"session_id": request.session_id},
            {"$set": {"messages": messages}}
        )
        return ChatResponse(
            messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
        )
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"Unexpected error in interview_chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during the interview."
        )

# ------------------------------------------------------------------
# Additional helper for final feedback formatting
# ------------------------------------------------------------------
def format_conversation(messages: List[Dict[str, str]]) -> str:
    """
    Convert the conversation (list of messages) into a readable text block
    for the final feedback prompt.
    """
    lines = []
    for msg in messages:
        if msg["sender"] == "ai":
            lines.append(f"Interviewer: {msg['text']}")
        else:
            lines.append(f"Candidate: {msg['text']}")
    return "\n".join(lines)