# Create a new file in your ai-backend/routers directory
# Save as cv_model.py

import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import jwt
import motor.motor_asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = "NE60hAlMyF6wVlOt5+VDKpaU/I6FJ4Oa5df1gpG/MTg="

# ------------------------------------------------------------------
# Configure environment variables
# ------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
logger.info(f"Using MongoDB URI: {MONGODB_URI}")

# ------------------------------------------------------------------
# Set up MongoDB client
# ------------------------------------------------------------------
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    cvs_col = db["cvs"]  # New collection for CVs
    logger.info("MongoDB connection established for CV collection")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    client = None
    db = None
    cvs_col = None

# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# Create a FastAPI APIRouter
# ------------------------------------------------------------------
router = APIRouter()
logger.info("CV API Router created")

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@router.post("/save-cv")
async def save_cv(request: Request, cv_file: UploadFile = File(...)):
    """
    Save a CV to the database.
    """
    logger.info(f"Saving CV: {cv_file.filename}")
    try:
        # Verify authentication
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
            logger.info(f"User authenticated: {user_id}")
        except jwt.PyJWTError as e:
            logger.error(f"JWT decode error: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {str(e)}"}
            )

        # Save CV file
        os.makedirs("uploads", exist_ok=True)
        file_ext = os.path.splitext(cv_file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join("uploads", file_name)
        content = await cv_file.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"CV saved to: {file_path}")
        
        # Save CV to MongoDB
        if cvs_col is not None:
            cv_data = {
                "user_id": user_id,
                "filename": file_name,
                "original_name": cv_file.filename,
                "file_size": len(content),
                "file_path": file_path,
                "content_type": cv_file.content_type or "application/octet-stream",
                "uploaded_at": datetime.utcnow(),
                "last_used": datetime.utcnow()
            }
            
            result = await cvs_col.insert_one(cv_data)
            cv_id = str(result.inserted_id)
            logger.info(f"CV saved to MongoDB with ID: {cv_id}")
            
            # Return success response
            return JSONResponse(content={
                "status": "success",
                "cv": {
                    "id": cv_id,
                    "filename": cv_file.filename,
                    "size": len(content),
                    "uploaded_at": cv_data["uploaded_at"].isoformat(),
                    "last_used": cv_data["last_used"].isoformat()
                }
            })
        else:
            logger.warning("MongoDB not available, CV metadata not saved")
            return JSONResponse(
                status_code=500,
                content={"detail": "Database unavailable"}
            )
    
    except Exception as e:
        logger.error(f"Error saving CV: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error saving CV: {str(e)}"}
        )

@router.get("/cvs/{user_id}")
async def get_user_cvs(user_id: str, request: Request):
    """
    Get all CVs for a user.
    """
    logger.info(f"Getting CVs for user: {user_id}")
    
    # Verify authentication
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
        
        # Only allow users to access their own CVs
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
    
    # Check if MongoDB is available
    if cvs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        
    # Retrieve CVs
    try:
        cursor = cvs_col.find({"user_id": user_id}).sort("last_used", -1)  # Newest first
        cvs = await cursor.to_list(length=100)  # Limit to 100 CVs
        
        # Format the response
        formatted_cvs = []
        for cv in cvs:
            formatted_cvs.append({
                "id": str(cv["_id"]),
                "filename": cv["original_name"],
                "size": cv["file_size"],
                "uploaded_at": cv["uploaded_at"].isoformat(),
                "last_used": cv["last_used"].isoformat(),
                "content_type": cv["content_type"]
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
    
    # Verify authentication
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
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token"}
        )
    
    # Check if MongoDB is available
    if cvs_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
        
    # Find CV
    try:
        from bson.objectid import ObjectId
        cv = await cvs_col.find_one({"_id": ObjectId(cv_id)})
        if not cv:
            logger.warning(f"CV not found: {cv_id}")
            return JSONResponse(
                status_code=404,
                content={"detail": "CV not found"}
            )
        
        # Check if user owns the CV
        if cv["user_id"] != user_id:
            logger.warning(f"Unauthorized delete attempt: {user_id} trying to delete CV {cv_id}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Unauthorized access"}
            )
        
        # Delete file from disk if it exists
        try:
            if os.path.exists(cv["file_path"]):
                os.remove(cv["file_path"])
                logger.info(f"Deleted CV file from disk: {cv['file_path']}")
        except Exception as file_error:
            logger.error(f"Error deleting CV file: {file_error}")
            # Continue with deleting the database record even if file deletion fails
        
        # Delete from database
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