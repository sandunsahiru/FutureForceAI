import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from pydantic import BaseModel, Field

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
# Make sure the .env file is in your ai-backend folder.
# By default, load_dotenv() looks in the current working directory.
load_dotenv()

# ------------------------------------------------------------------
# Configure environment variables (example)
# ------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
openai.api_key = os.getenv("OPENAI_API_KEY")

# For Google Cloud Vision:
# The GOOGLE_APPLICATION_CREDENTIALS environment variable should now
# be loaded from your .env. It must point to the JSON key file.
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
    finished: bool = False  # if conversation ended (e.g., after 10 AI messages or user ended)


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

    # Optional: Validate file type, limit file size, etc.

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
    response = vision.ImageAnnotatorClient().document_text_detection(image=image)

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

    The system instructions guide the model to:
      - Act as a professional interviewer
      - Provide constructive feedback
      - Ask up to 10 total AI questions
      - Remain concise, clear, and human-like
    """
    # More thorough instructions can help the model produce better results.
    system_instructions = (
        f"You are a highly knowledgeable AI interviewer, specializing in {job_role} interviews.\n"
        f"You have the candidate's CV:\n\n{cv_text}\n\n"
        "Your goal is to ask questions one by one, evaluate correctness, and give professional yet friendly feedback. "
        "If the candidate's answer is unclear or incomplete, politely ask for more details. "
        "Continue until you've asked 10 questions total or the candidate is done.\n\n"
        "Please keep responses focused, realistic, and supportive."
    )

    # Flatten the conversation into a text block
    conversation_text = ""
    for msg in messages:
        if msg["sender"] == "ai":
            conversation_text += f"Interviewer: {msg['text']}\n"
        else:
            conversation_text += f"Candidate: {msg['text']}\n"

    # Combine instructions and conversation
    # We'll prompt with "Interviewer:" at the end so the model continues as the interviewer.
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
        # NOTE: "o3-mini" is hypothetical. Replace with the correct model name (e.g. "gpt-3.5-turbo", "text-davinci-003") 
        response = openai.Completion.create(
            model="o3-mini",         # or "o3-mini-2025-01-31", etc.
            prompt=prompt,
            max_tokens=300,         # Increased tokens for more thorough answers
            temperature=0.5,        # Lower temperature = more focused, deterministic responses
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            stop=["Candidate:", "Interviewer:"]  # Stop sequences so it doesn't run on
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return (
            "I'm sorry, but I'm having trouble generating a response right now."
        )

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/start")
async def start_interview(
    user_id: str = Form(...),
    cv_file: UploadFile = File(...),
    job_role: str = Form(...),
):
    """
    1) Save CV to disk
    2) Extract text with Google Cloud Vision
    3) Create a conversation record in MongoDB
    4) Return session_id and first AI message
    """
    try:
        # 1) Save CV
        file_path = await save_cv_to_disk(cv_file)

        # 2) Extract text using Google Cloud Vision
        cv_text = extract_text_with_vision(file_path)

        # 3) Generate a unique session_id
        session_id = str(uuid.uuid4())

        # 4) Prepare the initial AI greeting
        initial_ai_text = (
            f"Thank you for uploading your CV for the {job_role} position. "
            "Let's begin the interview. Can you tell me about yourself?"
        )

        # 5) Create a conversation document
        conversation_doc = ConversationModel(
            session_id=session_id,
            user_id=user_id,
            job_role=job_role,
            cv_text=cv_text,
            messages=[ChatMessage(sender="ai", text=initial_ai_text)],
        )

        # 6) Insert conversation into MongoDB
        await conversations_col.insert_one(conversation_doc.dict(exclude={"_id"}))

        # 7) Return the session_id and the first AI message
        #    The frontend must store session_id and use it for further requests.
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
        # 1) Fetch conversation from DB
        convo = await conversations_col.find_one({"session_id": request.session_id})
        if not convo:
            raise HTTPException(status_code=404, detail="Session not found.")

        # If conversation is already finished, let user know
        if convo.get("finished", False):
            final_msg = "This interview session is finished. Please start a new one if you wish to continue."
            return ChatResponse(messages=[ChatMessage(sender="ai", text=final_msg)])

        # 2) Append user's message
        messages = convo["messages"]
        messages.append({"sender": "user", "text": request.user_message})

        # 3) Count how many AI messages have been sent so far
        ai_message_count = sum(1 for m in messages if m["sender"] == "ai")

        # If we've reached or exceeded 10 AI responses, provide final feedback
        if ai_message_count >= 10:
            # Build a special prompt to get a final motivational feedback from OpenAI
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

            # Append final feedback from AI
            messages.append({"sender": "ai", "text": final_feedback})

            # Mark conversation as finished
            await conversations_col.update_one(
                {"session_id": request.session_id},
                {"$set": {"messages": messages, "finished": True}}
            )

            return ChatResponse(
                messages=[ChatMessage(sender=m["sender"], text=m["text"]) for m in messages]
            )

        # 4) Build a prompt for the normal interview flow using the entire conversation so far
        prompt = await build_openai_prompt(
            cv_text=convo["cv_text"],
            job_role=convo["job_role"],
            messages=messages
        )

        # 5) Call OpenAI (or Gemini) for the next interview Q&A
        ai_reply = call_openai(prompt)

        # 6) Append AI's new message
        messages.append({"sender": "ai", "text": ai_reply})

        # 7) Update DB
        await conversations_col.update_one(
            {"session_id": request.session_id},
            {"$set": {"messages": messages}}
        )

        # 8) Return updated conversation
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


# -------------------------------------------------------
# Additional helper for final feedback formatting
# -------------------------------------------------------
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