import os
import random
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from bson import ObjectId

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
    
    if "filePath" in cv_document and cv_document["filePath"]:
        potential_paths.append(cv_document["filePath"])
    
    if "fileId" in cv_document and cv_document["fileId"]:
        file_id = cv_document["fileId"]
        original_name = cv_document.get('originalName', '')
        clean_original = clean_filename(original_name)
        potential_paths.append(f"/app/uploads/{file_id}_{clean_original}")
        potential_paths.append(f"./uploads/{file_id}_{clean_original}")
    
    if "_id" in cv_document:
        doc_id = str(cv_document["_id"])
        original_name = cv_document.get('originalName', '')
        clean_original = clean_filename(original_name)
        
        potential_paths.append(f"/app/uploads/{doc_id}_{clean_original}")
        potential_paths.append(f"./uploads/{doc_id}_{clean_original}")

    if 'filename' in cv_document:
        filename = cv_document.get('filename')
        potential_paths.append(f"./uploads/{filename}")
        potential_paths.append(f"/app/uploads/{filename}")
    
    if 'originalName' in cv_document:
        original_name = cv_document.get('originalName')
        potential_paths.append(f"./uploads/{original_name}")
        potential_paths.append(f"/app/uploads/{original_name}")
        
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
    if not file_id:
        file_id = generate_timestamp_id()
    
    filename = f"{file_id}_{clean_filename(original_name)}"

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
    
    try:
        result = await collection.insert_one(cv_document)
        logger.info(f"Saved CV to MongoDB with ID: {cv_document['_id']}")
        return cv_document
    except Exception as e:
        logger.error(f"Error saving CV to MongoDB: {e}")
        return None

async def find_cv_by_id(db, cv_id, user_id):
    if db is None:
        logger.error("Database not connected")
        return None
    
    try:

        cv_collection = db.get_collection("cvs")
        if cv_collection is None:
            logger.error("CV collection not available")
            return None

        doc_id = cv_id
        if isinstance(cv_id, str):
            try:
                doc_id = ObjectId(cv_id)
            except:
                query = {"fileId": cv_id, "userId": user_id}
                return await cv_collection.find_one(query)
        
        cv_document = await cv_collection.find_one({"_id": doc_id, "userId": user_id})

        if cv_document is None:
            cv_document = await cv_collection.find_one({"fileId": cv_id, "userId": user_id})
        
        return cv_document
    except Exception as e:
        logger.error(f"Error finding CV document: {e}")
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