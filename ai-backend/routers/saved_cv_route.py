import os
import uuid
import logging
from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Header, Cookie
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Set up logging
logger = logging.getLogger("futureforceai")

# Import MongoDB connection
from .interviewprep import (
    conversations_col, SECRET_KEY, 
    MAX_INTERVIEW_QUESTIONS, call_openai,
    extract_text_from_document, vision_client, openai_client
)

import jwt
import motor.motor_asyncio
import json
from bson import ObjectId

# Create a router for the new endpoint
router = APIRouter()

# Define the request model
class SavedCVInterviewRequest(BaseModel):
    job_role: str
    cv_id: str
    user_id: Optional[str] = None

# Helper function to extract and verify token
async def get_token_from_request(request: Request):
    """Extract token from request cookies, headers, or body"""
    # Try to get token from cookies
    token = request.cookies.get("token")
    
    # Try Authorization header if no cookie
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
    
    # No valid token found
    if not token:
        return None
        
    return token

@router.post("/api/interview/start-with-saved-cv")
async def start_interview_with_saved_cv(
    request: Request,
    data: SavedCVInterviewRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Start a new interview session using a saved CV file.
    """
    logger.info(f"Starting interview for job role: {data.job_role} with CV ID: {data.cv_id}")
    
    try:
        # Get token from various sources
        token = await get_token_from_request(request)
        
        # Also check the Authorization header directly
        if not token and authorization:
            if authorization.startswith("Bearer "):
                token = authorization[7:]
                logger.info("Token found in Authorization header")
                
        # Log all request headers for debugging
        logger.info("Request headers:")
        for header_name, header_value in request.headers.items():
            logger.info(f"  {header_name}: {header_value if header_name.lower() != 'authorization' else '[REDACTED]'}")
            
        # Log cookies
        logger.info(f"Request cookies: {request.cookies}")
        
        # Check if we got a token
        if not token:
            logger.warning("No authentication token found in any source")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
            
        logger.info(f"Using token: {token[:10]}...")
        
        # Verify token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("userId")
            if not user_id:
                logger.warning("Invalid token: missing userId")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid authentication token"}
                )
            logger.info(f"User authenticated: {user_id}")
            
            # Check if the user_id matches the one in the request
            if data.user_id and data.user_id != user_id:
                logger.warning(f"User ID mismatch: token {user_id} vs request {data.user_id}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Unauthorized access"}
                )
        except jwt.PyJWTError as e:
            logger.error(f"JWT decode error: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {str(e)}"}
            )
        
        # Get CV collection
        db = conversations_col.database
        cv_collection = db.get_collection("cvs")
        
        if not cv_collection:
            logger.error("CV collection not found in database")
            return JSONResponse(
                status_code=500,
                content={"detail": "CV storage not available"}
            )
            
        # Try different formats of ObjectId
        try:
            # Try to find CV by ID - consider both string ID and ObjectId
            cv_query = {"$or": [
                {"_id": data.cv_id},
                {"_id": ObjectId(data.cv_id) if len(data.cv_id) == 24 else data.cv_id}
            ]}
            
            # Also filter by user ID
            cv_query["userId"] = user_id
            
            cv_document = await cv_collection.find_one(cv_query)
            
            if not cv_document:
                logger.warning(f"CV not found for ID: {data.cv_id} and user: {user_id}")
                
                # Try fallback to search by document ID
                logger.info(f"Trying fallback search without ObjectId conversion")
                fallback_cv = await cv_collection.find_one({"_id": data.cv_id, "userId": user_id})
                
                if not fallback_cv:
                    return JSONResponse(
                        status_code=404,
                        content={"detail": f"CV not found or unauthorized. ID: {data.cv_id}"}
                    )
                    
                cv_document = fallback_cv
        except Exception as e:
            logger.error(f"Error finding CV: {e}")
            return JSONResponse(
                status_code=500, 
                content={"detail": f"Error finding CV: {str(e)}"}
            )
            
        logger.info(f"Found CV document: {cv_document.get('originalName', 'Unknown')} with keys: {list(cv_document.keys())}")
        
        # Get CV text from document
        cv_text = cv_document.get("content")
        cv_file_path = cv_document.get("filePath")
        
        if not cv_text and cv_file_path and os.path.exists(cv_file_path):
            logger.info(f"Extracting CV text from file: {cv_file_path}")
            cv_text = extract_text_from_document(cv_file_path, vision_client, openai_client)
            
        if not cv_text or len(cv_text.strip()) < 100:
            logger.warning(f"Insufficient CV text extracted: {len(cv_text) if cv_text else 0} chars")
            
            # Use file path as fallback
            if cv_file_path and os.path.exists(cv_file_path):
                logger.info(f"Using file path as fallback for CV: {cv_file_path}")
                try:
                    with open(cv_file_path, 'r', errors='ignore') as f:
                        cv_text = f.read()
                        logger.info(f"Read {len(cv_text)} chars from CV file")
                except Exception as read_err:
                    logger.error(f"Error reading CV file directly: {read_err}")
            
            if not cv_text or len(cv_text.strip()) < 100:
                logger.error("Could not extract sufficient content from CV after fallback")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Could not extract sufficient content from CV"}
                )
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        logger.info(f"Generated session ID: {session_id}")
        
        # Create initial AI message
        initial_ai_text = (
            f"Thank you for selecting your CV for the {data.job_role} position. "
            "Let's begin the interview. Can you tell me about yourself?"
        )
        
        # Create conversation document
        conversation_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "job_role": data.job_role,
            "cv_text": cv_text,
            "messages": [{"sender": "ai", "text": initial_ai_text}],
            "created_at": datetime.utcnow(),
            "finished": False,
            "max_questions": MAX_INTERVIEW_QUESTIONS,
            "cv_id": data.cv_id  # Store reference to the CV
        }
        
        # Save to MongoDB
        if conversations_col is not None:
            try:
                await conversations_col.insert_one(conversation_doc)
                logger.info(f"Saved conversation to MongoDB: {session_id}")
            except Exception as db_err:
                logger.error(f"MongoDB error: {db_err}")
                # Continue anyway - we'll return the session even if DB save fails
        else:
            logger.warning("MongoDB not available, session not saved")
        
        # Prepare response
        response_data = {
            "session_id": session_id,
            "first_ai_message": {"sender": "ai", "text": initial_ai_text}
        }
        
        logger.info(f"Returning response: {response_data}")
        return JSONResponse(content=response_data)
    
    except Exception as e:
        logger.error(f"Unexpected error in start_interview_with_saved_cv: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred: {str(e)}"}
        )