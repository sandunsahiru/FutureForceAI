import os
import uuid
import random
import logging
from typing import Dict, Optional, List
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
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
    
    # No valid token found
    if not token:
        return None
        
    return token

# Make sure uploads directory exists
def ensure_uploads_dir():
    """Ensure the uploads directory exists in the FastAPI container"""
    uploads_dir = "/app/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    logger.info(f"Ensuring uploads directory exists: {uploads_dir}")
    return uploads_dir

# Generate timestamp-based ID for consistent file naming
def generate_timestamp_id() -> str:
    """
    Generate a timestamp-based ID for consistent file naming.
    Format: YYYYMMDD-HHMMSS-random_suffix
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
    return f"{timestamp}-{random_suffix}"

# Clean filename to avoid spaces and special characters
def clean_filename(filename: str) -> str:
    """
    Clean a filename to avoid special characters and spaces.
    """
    return filename.replace(' ', '_').replace('/', '_').replace('\\', '_')

# Generate potential file paths based on CV document
def get_potential_file_paths(cv_document: Dict) -> List[str]:
    """
    Generate a list of potential file paths based on CV document metadata.
    """
    potential_paths = []
    
    # Primary path from database
    if "filePath" in cv_document and cv_document["filePath"]:
        potential_paths.append(cv_document["filePath"])
    
    # Get timestamp-based fileId if available
    if "fileId" in cv_document and cv_document["fileId"]:
        file_id = cv_document["fileId"]
        original_name = cv_document.get('originalName', '')
        clean_original = clean_filename(original_name)
        
        # Add paths with timestamp ID
        potential_paths.append(f"/app/uploads/{file_id}_{clean_original}")
        potential_paths.append(f"./uploads/{file_id}_{clean_original}")
    
    # Try MongoDB ObjectId based paths
    doc_id = str(cv_document["_id"])
    original_name = cv_document.get('originalName', '')
    clean_original = clean_filename(original_name)
    
    # Add ID-based paths in upload directories
    potential_paths.append(f"/app/uploads/{doc_id}_{clean_original}")
    potential_paths.append(f"./uploads/{doc_id}_{clean_original}")
    
    # Try with /app prefix (Docker container path)
    file_path = cv_document.get("filePath")
    if file_path and not file_path.startswith('/app/'):
        potential_paths.append(f"/app{file_path}" if file_path.startswith('/') else f"/app/{file_path}")
    
    # Try without /app prefix
    if file_path and file_path.startswith('/app/'):
        potential_paths.append(file_path[4:])  # Remove /app prefix
    
    # Try filename-based paths
    if 'filename' in cv_document:
        filename = cv_document.get('filename')
        potential_paths.append(f"./uploads/{filename}")
        potential_paths.append(f"/app/uploads/{filename}")
        potential_paths.append(f"/uploads/{filename}")
    
    # Try paths based on original name
    if 'originalName' in cv_document:
        original_name = cv_document.get('originalName')
        # Backend paths
        potential_paths.append(f"./uploads/{original_name}")
        potential_paths.append(f"/app/uploads/{original_name}")
        # Frontend paths
        potential_paths.append(f"../frontend/uploads/{original_name}")
        potential_paths.append(f"/app/frontend/uploads/{original_name}")
    
    return potential_paths

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
        # Ensure uploads directory exists
        ensure_uploads_dir()
        
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
        
        # IMPORTANT: Get database collections
        db = conversations_col.database
        
        # First, let's check in the "cvs" collection
        cv_collection = db.get_collection("cvs")
        
        if cv_collection is None:
            logger.error("CV collection not found in database")
            return JSONResponse(
                status_code=500,
                content={"detail": "CV storage not available"}
            )
        
        # Try different collections and ID formats
        cv_document = None
        collections_to_check = ["cvs", "CV", "cv"]
        current_collection = None
        
        # Log all collections in the database for debugging
        collections = await db.list_collection_names()
        logger.info(f"Available collections in database: {collections}")
        
        # First try: Check if the ID is a fileId (timestamp-based ID)
        for collection_name in collections_to_check:
            if collection_name in collections:
                collection = db.get_collection(collection_name)
                try:
                    logger.info(f"Checking for fileId in collection: {collection_name}")
                    cv_document = await collection.find_one({"fileId": data.cv_id})
                    if cv_document:
                        logger.info(f"Found CV with fileId in collection: {collection_name}")
                        current_collection = collection
                        break
                except Exception as e:
                    logger.error(f"Error searching by fileId: {e}")
        
        # Second try: Check by ObjectId or string ID
        if cv_document is None:
            for collection_name in collections_to_check:
                if collection_name in collections:
                    logger.info(f"Checking collection: {collection_name}")
                    collection = db.get_collection(collection_name)
                    
                    # Try with ObjectId first if possible
                    if len(data.cv_id) == 24:
                        try:
                            logger.info(f"Trying with ObjectId: {data.cv_id}")
                            object_id = ObjectId(data.cv_id)
                            cv_document = await collection.find_one({"_id": object_id})
                            if cv_document:
                                current_collection = collection
                        except Exception as id_err:
                            logger.error(f"Error converting to ObjectId: {id_err}")
                    
                    # Try string ID if ObjectId didn't work
                    if cv_document is None:
                        try:
                            logger.info(f"Trying with string ID: {data.cv_id}")
                            cv_document = await collection.find_one({"_id": data.cv_id})
                            if cv_document:
                                current_collection = collection
                        except Exception as e:
                            logger.error(f"Error searching with string ID: {e}")
                    
                    # If we found a document, break the loop
                    if cv_document is not None:
                        logger.info(f"Found CV in collection: {collection_name}")
                        break
        
        # Third try: Broader search without user filtering
        if cv_document is None:
            logger.warning(f"CV not found with user filter, trying broader search")
            for collection_name in collections_to_check:
                if collection_name in collections:
                    collection = db.get_collection(collection_name)
                    
                    # Try to find ANY document with this ID without user filtering
                    try:
                        if len(data.cv_id) == 24:
                            cv_document = await collection.find_one({"_id": ObjectId(data.cv_id)})
                        else:
                            cv_document = await collection.find_one({"_id": data.cv_id})
                            
                        if cv_document:
                            current_collection = collection
                    except Exception as e:
                        logger.error(f"Error in broader search: {e}")
                    
                    if cv_document is not None:
                        logger.info(f"Found CV in collection {collection_name} without user filtering")
                        break
        
        # Fourth try: Search by filename or original name as fallback
        if cv_document is None:
            logger.warning(f"CV not found by ID, trying filename search")
            for collection_name in collections_to_check:
                if collection_name in collections:
                    collection = db.get_collection(collection_name)
                    
                    # Try to match by filename if it contains the ID
                    try:
                        cv_document = await collection.find_one({"filename": {"$regex": data.cv_id}})
                        if cv_document:
                            logger.info(f"Found CV by filename regex in {collection_name}")
                            current_collection = collection
                            break
                    except Exception as e:
                        logger.error(f"Error in filename search: {e}")
        
        # Log debugging information about CV document
        if cv_document is not None:
            logger.info(f"CV document found with keys: {list(cv_document.keys())}")
            if "userId" in cv_document:
                logger.info(f"CV document userId: {cv_document['userId']}")
            if "_id" in cv_document:
                logger.info(f"CV document _id: {cv_document['_id']}")
            if "fileId" in cv_document:
                logger.info(f"CV document fileId: {cv_document['fileId']}")
            if "filePath" in cv_document:
                logger.info(f"CV document filePath: {cv_document['filePath']}")
        
        # If CV still not found, return error
        if cv_document is None:
            logger.warning(f"CV not found after exhaustive search for ID: {data.cv_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": f"CV not found or unauthorized. ID: {data.cv_id}"}
            )
        
        # Get CV text from document using multiple possible field names
        cv_text = None
        
        # First check 'extractedText' field (matches the MongoDB schema)
        if 'extractedText' in cv_document and cv_document['extractedText']:
            logger.info("Using 'extractedText' field from CV document")
            cv_text = cv_document['extractedText']
            
        # Try 'content' field if extractedText not found
        if not cv_text and 'content' in cv_document and cv_document['content']:
            logger.info("Using 'content' field from CV document")
            cv_text = cv_document['content']
        
        # If still no text, prepare potential file paths for extraction
        if not cv_text:
            # Generate potential file paths
            potential_paths = get_potential_file_paths(cv_document)
            
            # Log all paths we're going to try
            logger.info(f"Trying these potential file paths: {potential_paths}")
            
            # Try each path for text extraction
            extracted = False
            for path in potential_paths:
                if os.path.exists(path):
                    logger.info(f"Found file at path: {path}")
                    try:
                        cv_text = extract_text_from_document(path, vision_client, openai_client)
                        if cv_text and len(cv_text.strip()) >= 100:
                            logger.info(f"Successfully extracted {len(cv_text)} chars from file at {path}")
                            extracted = True
                            
                            # Update the CV document with the correct path and extracted text
                            try:
                                await current_collection.update_one(
                                    {"_id": cv_document["_id"]},
                                    {"$set": {
                                        "extractedText": cv_text,
                                        "filePath": path,  # Update to the correct path
                                        "lastUsed": datetime.utcnow()  # Update last used timestamp
                                    }}
                                )
                                logger.info("Updated CV document with extracted text and correct path")
                            except Exception as update_err:
                                logger.error(f"Failed to update CV document: {update_err}")
                                
                            break
                        else:
                            logger.warning(f"Extraction produced insufficient text from {path}: {len(cv_text) if cv_text else 0} chars")
                    except Exception as e:
                        logger.error(f"Error extracting text from {path}: {e}")
                        
                    # If extraction failed, try simple file read
                    if not extracted:
                        try:
                            with open(path, 'rb') as f:  # Use binary mode to handle both text and binary files
                                file_content = f.read()
                                try:
                                    # Try to decode as text
                                    cv_text = file_content.decode('utf-8', errors='ignore')
                                except:
                                    # If can't decode, use the binary content for OpenAI processing later
                                    pass
                                
                            if cv_text and len(cv_text.strip()) >= 100:
                                logger.info(f"Successfully read {len(cv_text)} chars from file at {path}")
                                extracted = True
                                
                                # Update the CV document with the correct path and extracted text
                                try:
                                    await current_collection.update_one(
                                        {"_id": cv_document["_id"]},
                                        {"$set": {
                                            "extractedText": cv_text,
                                            "filePath": path,  # Update to the correct path
                                            "lastUsed": datetime.utcnow()  # Update last used timestamp
                                        }}
                                    )
                                    logger.info("Updated CV document with extracted text and correct path")
                                except Exception as update_err:
                                    logger.error(f"Failed to update CV document: {update_err}")
                                
                                break
                            else:
                                logger.warning(f"Direct file read produced insufficient text from {path}")
                        except Exception as read_err:
                            logger.error(f"Error reading file from {path}: {read_err}")
            
            # If no path worked, log all attempted paths
            if not extracted:
                logger.error(f"Could not find readable file at any of these paths: {potential_paths}")
                    
            # Try to use OpenAI Vision API as a last resort for extracting text
            # First collect all valid paths that exist
            valid_paths = [path for path in potential_paths if os.path.exists(path)]
            
            if (not cv_text or len(cv_text.strip()) < 100) and valid_paths and openai_client is not None:
                logger.info(f"Attempting OpenAI Vision extraction as last resort")
                try:
                    import base64
                    
                    # Try each valid path
                    for file_path in valid_paths:
                        # Get file extension and determine content type
                        file_ext = os.path.splitext(file_path)[1].lower()
                        content_type = "application/pdf" if file_ext == '.pdf' else "image/jpeg" if file_ext in ['.jpg', '.jpeg'] else "image/png"
                        
                        logger.info(f"Trying OpenAI Vision extraction with file: {file_path} (content type: {content_type})")
                        
                        # Read file and encode to base64
                        try:
                            with open(file_path, "rb") as f:
                                file_content = f.read()
                            file_b64 = base64.b64encode(file_content).decode('utf-8')
                    
                            # Call OpenAI Vision API
                            response = openai_client.chat.completions.create(
                                model="gpt-4.1-mini",
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant that extracts text from CV/resume documents."},
                                    {"role": "user", "content": [
                                        {"type": "text", "text": "Extract all the text content from this CV/resume document. Include all sections like personal info, education, experience, skills, etc."},
                                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{file_b64}"}}
                                    ]}
                                ],
                                max_tokens=4000
                            )
                            
                            openai_text = response.choices[0].message.content
                            if openai_text and len(openai_text.strip()) > 100:
                                logger.info(f"OpenAI Vision extracted {len(openai_text)} characters from {file_path}")
                                cv_text = openai_text
                                
                                # Update the CV document with the extracted text and correct path
                                try:
                                    await current_collection.update_one(
                                        {"_id": cv_document["_id"]},
                                        {"$set": {
                                            "extractedText": cv_text,
                                            "filePath": file_path,
                                            "lastUsed": datetime.utcnow()
                                        }}
                                    )
                                    logger.info("Updated CV document with extracted text and correct path")
                                    break  # Exit the loop if successful
                                except Exception as update_err:
                                    logger.error(f"Failed to update CV document with extracted text: {update_err}")
                            else:
                                logger.warning(f"OpenAI Vision extraction from {file_path} produced insufficient text: {len(openai_text) if openai_text else 0} chars")
                        except Exception as file_err:
                            logger.error(f"Error processing file {file_path} with OpenAI Vision: {file_err}")
                            continue
                except Exception as openai_err:
                    logger.error(f"Error using OpenAI Vision for extraction: {openai_err}")
        
        # Try creating a new file with timestamp-based naming if needed
        if not cv_text or len(cv_text.strip()) < 100:
            logger.warning("Attempting to recover by creating a file with timestamp-based naming in the shared volume")
            try:
                # Find any existing file that might contain the content
                existing_file = None
                for path in potential_paths:
                    if os.path.exists(path):
                        existing_file = path
                        break
                
                if existing_file:
                    # Create a new file with timestamp-based naming
                    timestamp_id = generate_timestamp_id()
                    
                    original_name = cv_document.get('originalName', 'recovered.pdf')
                    clean_original_name = clean_filename(original_name)
                    new_path = f"/app/uploads/{timestamp_id}_{clean_original_name}"
                    
                    # Copy file
                    with open(existing_file, 'rb') as src:
                        with open(new_path, 'wb') as dst:
                            dst.write(src.read())
                    logger.info(f"Created new file with timestamp-based naming at: {new_path}")
                    
                    # Try extracting from new location
                    cv_text = extract_text_from_document(new_path, vision_client, openai_client)
                    
                    if cv_text and len(cv_text.strip()) >= 100:
                        # Update database with new path, extracted text, and timestamp ID
                        await current_collection.update_one(
                            {"_id": cv_document["_id"]},
                            {"$set": {
                                "extractedText": cv_text,
                                "filePath": new_path,
                                "fileId": timestamp_id,
                                "lastUsed": datetime.utcnow()
                            }}
                        )
                        logger.info(f"Updated CV document with new file path, timestamp ID, and extracted text: {new_path}")
                    else:
                        logger.warning(f"Failed to extract sufficient text from newly created file")
            except Exception as recovery_err:
                logger.error(f"Recovery attempt failed: {recovery_err}")
        
        # If we still don't have usable CV text, return error
        if not cv_text or len(cv_text.strip()) < 100:
            logger.error(f"Could not extract sufficient content from CV after all attempts. Length: {len(cv_text) if cv_text else 0} chars")
            return JSONResponse(
                status_code=400,
                content={"detail": "Could not extract sufficient content from CV. Please upload a different file format or ensure the CV contains readable text."}
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
                result = await conversations_col.insert_one(conversation_doc)
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