import os
import uuid
import logging
import jwt
import motor.motor_asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .interviewprep import extract_text_from_document, vision_client, openai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = "NE60hAlMyF6wVlOt5+VDKpaU/I6FJ4Oa5df1gpG/MTg="
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
logger.info(f"Using MongoDB URI: {MONGODB_URI}")

try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    cvs_col = db["cvs"] 
    logger.info("MongoDB connection established for CV collection")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    client = None
    db = None
    cvs_col = None


# Pydantic Models
class CV(BaseModel):
    user_id: str
    filename: str
    original_name: str
    file_size: int
    file_path: str
    content_type: str
    extracted_text: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: datetime = Field(default_factory=datetime.utcnow)


router = APIRouter()
logger.info("CV API Router created")


# Helper Functions
def ensure_uploads_dir():
    """Ensure the uploads directory exists in the FastAPI container"""
    uploads_dir = "/app/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    logger.info(f"Ensuring uploads directory exists: {uploads_dir}")
    return uploads_dir

async def get_token_from_request(request: Request):
    """Extract token from request cookies, headers, or body"""
    token = request.cookies.get("token")
    
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  
    
    if not token:
        return None
        
    return token

def clean_filename(filename):
    """Clean the filename to avoid spaces and special characters"""
    return ''.join(c if c.isalnum() or c in '.-_' else '_' for c in filename)


# Routes
@router.post("/save-cv")
async def save_cv(
    request: Request,
    cv_file: UploadFile = File(...),
    cv_id: Optional[str] = Form(None),
    file_path: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    Save a CV file and extract text from it.
    This endpoint can handle both new CVs and existing CVs being updated.
    """
    logger.info(f"Received CV file: {cv_file.filename}, ID: {cv_id}, Path: {file_path}")
    
    token = await get_token_from_request(request)
    if not token and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
    
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
        logger.info(f"User authenticated: {user_id}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )

    ensure_uploads_dir()

    from bson.objectid import ObjectId
    existing_cv = None
    
    if cv_id:
        try:
            cv_object_id = ObjectId(cv_id)
            existing_cv = await cvs_col.find_one({"_id": cv_object_id})
            
            if existing_cv and str(existing_cv.get("userId", "")) != user_id:
                logger.warning(f"CV belongs to user {existing_cv.get('userId')}, not {user_id}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Unauthorized access to CV"}
                )
                
            if existing_cv:
                logger.info(f"Found existing CV record with ID: {cv_id}")
        except Exception as e:
            logger.error(f"Error finding CV document: {e}")
         
    

    if file_path and file_path.startswith('/app/uploads/'):
       
        actual_file_path = file_path
        logger.info(f"Using provided file path: {actual_file_path}")
    else:
        file_id = cv_id if cv_id else str(ObjectId())
        clean_filename_str = clean_filename(cv_file.filename)
        actual_file_path = f"/app/uploads/{file_id}_{clean_filename_str}"
        logger.info(f"Generated new file path: {actual_file_path}")
    

    try:
        file_content = await cv_file.read()
        with open(actual_file_path, "wb") as f:
            f.write(file_content)
            
        logger.info(f"CV file saved to: {actual_file_path}")

        await cv_file.seek(0)
    except Exception as e:
        logger.error(f"Error saving CV file: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error saving CV file: {str(e)}"}
        )

    extracted_text = ""
    try:
        logger.info(f"Attempting to extract text from file at: {actual_file_path}")

        if not os.path.exists(actual_file_path):
            logger.error(f"File does not exist at path: {actual_file_path}")
            file_content = await cv_file.read()
            
            temp_path = f"/tmp/{uuid.uuid4()}.tmp"
            with open(temp_path, "wb") as f:
                f.write(file_content)
                
            logger.info(f"Created temporary file at: {temp_path}")
            actual_file_path = temp_path

        extracted_text = extract_text_from_document(actual_file_path, vision_client, openai_client)
        logger.info(f"Successfully extracted {len(extracted_text)} characters from CV")
    except Exception as e:
        logger.error(f"Error extracting text from CV: {e}")
    

    if existing_cv:
        try:
            update_result = await cvs_col.update_one(
                {"_id": ObjectId(cv_id)},
                {"$set": {
                    "filename": os.path.basename(actual_file_path),
                    "originalName": cv_file.filename,
                    "fileSize": len(file_content),
                    "filePath": actual_file_path,
                    "contentType": cv_file.content_type or "application/octet-stream",
                    "extractedText": extracted_text,
                    "lastUsed": datetime.utcnow()
                }}
            )
            
            if update_result.modified_count > 0:
                logger.info(f"Updated CV document with ID: {cv_id}")
            else:
                logger.warning(f"CV document not updated: {cv_id}")
                
            return JSONResponse(content={
                "status": "success",
                "detail": "CV updated successfully",
                "cv_id": cv_id,
                "file_path": actual_file_path,
                "extracted_text": extracted_text,
                "text_length": len(extracted_text)
            })
        except Exception as e:
            logger.error(f"Error updating CV document: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Error updating CV document: {str(e)}"}
            )
    else:

        try:
            cv_data = {
                "userId": user_id,
                "filename": os.path.basename(actual_file_path),
                "originalName": cv_file.filename,
                "fileSize": len(file_content),
                "filePath": actual_file_path,
                "contentType": cv_file.content_type or "application/octet-stream",
                "extractedText": extracted_text,
                "uploadedAt": datetime.utcnow(),
                "lastUsed": datetime.utcnow()
            }
            
            result = await cvs_col.insert_one(cv_data)
            new_cv_id = str(result.inserted_id)
            logger.info(f"New CV saved to MongoDB with ID: {new_cv_id}")
            
            return JSONResponse(content={
                "status": "success",
                "detail": "CV saved successfully",
                "cv_id": new_cv_id,
                "file_path": actual_file_path,
                "extracted_text": extracted_text,
                "text_length": len(extracted_text)
            })
        except Exception as e:
            logger.error(f"Error creating CV document: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Error saving CV metadata: {str(e)}"}
            )

@router.get("/cvs/{user_id}")
async def get_user_cvs(user_id: str, request: Request):
    """
    Get all CVs for a user.
    """
    logger.info(f"Getting CVs for user: {user_id}")
    
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        token_user_id = payload.get("userId")

        if token_user_id != user_id:
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
    
    if cvs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        

    try:
        cursor = cvs_col.find({"$or": [{"userId": user_id}, {"user_id": user_id}]}).sort("lastUsed", -1) 
        cvs = await cursor.to_list(length=100)
        
        formatted_cvs = []
        for cv in cvs:
            original_name = cv.get("originalName", cv.get("original_name", "Unknown"))
            file_size = cv.get("fileSize", cv.get("file_size", 0))
            uploaded_at = cv.get("uploadedAt", cv.get("uploaded_at", datetime.utcnow()))
            last_used = cv.get("lastUsed", cv.get("last_used", datetime.utcnow()))
            content_type = cv.get("contentType", cv.get("content_type", "application/octet-stream"))
            
            formatted_cvs.append({
                "id": str(cv["_id"]),
                "filename": original_name,
                "size": file_size,
                "uploaded_at": uploaded_at.isoformat() if isinstance(uploaded_at, datetime) else uploaded_at,
                "last_used": last_used.isoformat() if isinstance(last_used, datetime) else last_used,
                "content_type": content_type
            })
            
        logger.info(f"Retrieved {len(formatted_cvs)} CVs for user {user_id}")
        return JSONResponse(content={"cvs": formatted_cvs})
        
    except Exception as e:
        logger.error(f"Error retrieving CVs: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error retrieving CVs: {str(e)}"}
        )

@router.delete("/cv/{cv_id}")
async def delete_cv(cv_id: str, request: Request):
    """
    Delete a CV.
    """
    logger.info(f"Deleting CV: {cv_id}")

    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    
    if cvs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
 
    try:
        from bson.objectid import ObjectId
        cv = await cvs_col.find_one({"_id": ObjectId(cv_id)})
        if not cv:
            logger.warning(f"CV not found: {cv_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "CV not found"}
            )

        cv_owner = cv.get("userId", cv.get("user_id", ""))
        if str(cv_owner) != user_id:
            logger.warning(f"Unauthorized delete attempt: {user_id} trying to delete CV {cv_id}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Unauthorized access"}
            )
        
        file_path = cv.get("filePath", cv.get("file_path", ""))
        
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted CV file from disk: {file_path}")
        except Exception as file_error:
            logger.error(f"Error deleting CV file: {file_error}")

        result = await cvs_col.delete_one({"_id": ObjectId(cv_id)})
        if result.deleted_count == 0:
            logger.warning(f"Failed to delete CV from database: {cv_id}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete CV"}
            )
        
        logger.info(f"Successfully deleted CV: {cv_id}")
        return JSONResponse(content={"detail": "CV deleted successfully"})
    
    except Exception as e:
        logger.error(f"Error deleting CV: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error deleting CV: {str(e)}"}
        )