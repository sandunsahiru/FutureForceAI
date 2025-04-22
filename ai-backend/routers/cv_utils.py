import os
import random
import logging
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from bson import ObjectId
from .cv_utils import generate_timestamp_id, save_cv_to_db

# Set up logging
logger = logging.getLogger("futureforceai")

def ensure_uploads_dir() -> str:
    """
    Ensure the uploads directory exists in the FastAPI container.
    """
    uploads_dir = "/app/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    logger.info(f"Ensuring uploads directory exists: {uploads_dir}")
    return uploads_dir

def generate_timestamp_id() -> str:
    """
    Generate a timestamp-based ID for consistent file naming.
    Format: YYYYMMDD-HHMMSS-random_suffix
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
    return f"{timestamp}-{random_suffix}"

def clean_filename(filename: str) -> str:
    """
    Clean a filename to avoid special characters and spaces.
    """
    return filename.replace(' ', '_').replace('/', '_').replace('\\', '_')

def get_potential_file_paths(cv_document: Dict[str, Any]) -> List[str]:
    """
    Generate a list of potential file paths based on the CV document.
    """
    potential_paths = []
    
    # Primary file path from the database
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
    
    # Try based on MongoDB ObjectId
    if "_id" in cv_document:
        doc_id = str(cv_document["_id"])
        original_name = cv_document.get('originalName', '')
        clean_original = clean_filename(original_name)
        
        potential_paths.append(f"/app/uploads/{doc_id}_{clean_original}")
        potential_paths.append(f"./uploads/{doc_id}_{clean_original}")
    
    # Add path based on filename
    if 'filename' in cv_document:
        filename = cv_document.get('filename')
        potential_paths.append(f"./uploads/{filename}")
        potential_paths.append(f"/app/uploads/{filename}")
    
    # Add path based on original name
    if 'originalName' in cv_document:
        original_name = cv_document.get('originalName')
        potential_paths.append(f"./uploads/{original_name}")
        potential_paths.append(f"/app/uploads/{original_name}")
        
        # Also try cleaned version of original name
        clean_original = clean_filename(original_name)
        if clean_original != original_name:
            potential_paths.append(f"./uploads/{clean_original}")
            potential_paths.append(f"/app/uploads/{clean_original}")
    
    return potential_paths

async def save_cv_to_db(
    collection, 
    user_id: str,
    file_path: str, 
    original_name: str,
    extracted_text: str = "",
    file_size: int = 0,
    content_type: str = "application/octet-stream",
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Save CV information to MongoDB.
    """
    # Generate timestamp ID if not provided
    if not file_id:
        file_id = generate_timestamp_id()
    
    # Create filename with timestamp ID
    filename = f"{file_id}_{clean_filename(original_name)}"
    
    # Create CV document
    cv_document = {
        "_id": ObjectId(),
        "userId": user_id,
        "filename": filename,
        "originalName": original_name,
        "filePath": file_path,
        "fileSize": file_size,
        "contentType": content_type,
        "extractedText": extracted_text,
        "uploadedAt": datetime.utcnow(),
        "lastUsed": datetime.utcnow(),
        "fileId": file_id
    }
    
    # Save to MongoDB
    try:
        result = await collection.insert_one(cv_document)
        logger.info(f"Saved CV to MongoDB with ID: {cv_document['_id']}")
        return cv_document
    except Exception as e:
        logger.error(f"Error saving CV to MongoDB: {e}")
        return None

async def find_cv_by_id(db, cv_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Find a CV document by ID with multiple fallback strategies.
    """
    collections_to_check = ["cvs", "CV", "cv"]
    cv_document = None
    
    for collection_name in collections_to_check:
        collection = db.get_collection(collection_name)
        if not collection:
            continue
            
        # Try with ObjectId first if possible
        if len(cv_id) == 24:
            try:
                object_id = ObjectId(cv_id)
                # With user filter if provided
                if user_id:
                    cv_document = await collection.find_one({
                        "_id": object_id,
                        "userId": user_id
                    })
                else:
                    cv_document = await collection.find_one({"_id": object_id})
                    
                if cv_document:
                    logger.info(f"Found CV with ObjectId in {collection_name}")
                    return cv_document
            except Exception as id_err:
                logger.error(f"Error finding CV with ObjectId: {id_err}")
        
        # Try with string ID
        try:
            # With user filter if provided
            if user_id:
                cv_document = await collection.find_one({
                    "_id": cv_id,
                    "userId": user_id
                })
            else:
                cv_document = await collection.find_one({"_id": cv_id})
                
            if cv_document:
                logger.info(f"Found CV with string ID in {collection_name}")
                return cv_document
        except Exception as e:
            logger.error(f"Error finding CV with string ID: {e}")
            
        # Try finding by fileId field
        try:
            # With user filter if provided
            if user_id:
                cv_document = await collection.find_one({
                    "fileId": cv_id,
                    "userId": user_id
                })
            else:
                cv_document = await collection.find_one({"fileId": cv_id})
                
            if cv_document:
                logger.info(f"Found CV with fileId in {collection_name}")
                return cv_document
        except Exception as e:
            logger.error(f"Error finding CV with fileId: {e}")
    
    logger.warning(f"CV not found for ID: {cv_id}")
    return None

async def update_cv_with_extracted_text(collection, cv_id: Union[str, ObjectId], extracted_text: str, file_path: Optional[str] = None) -> bool:
    """
    Update a CV document with extracted text and optionally a corrected file path.
    """
    try:
        update_data = {
            "extractedText": extracted_text,
            "lastUsed": datetime.utcnow()
        }
        
        if file_path:
            update_data["filePath"] = file_path
            
        result = await collection.update_one(
            {"_id": cv_id if isinstance(cv_id, ObjectId) else ObjectId(cv_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated CV {cv_id} with extracted text")
            return True
        else:
            logger.warning(f"Failed to update CV {cv_id}")
            return False
    except Exception as e:
        logger.error(f"Error updating CV with extracted text: {e}")
        return False