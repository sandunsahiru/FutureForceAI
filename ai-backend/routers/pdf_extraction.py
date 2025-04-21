import os
import logging
import base64
from typing import Optional, Tuple
import subprocess
import tempfile
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Try importing PyPDF2 for PDF handling
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    logger.warning("PyPDF2 not installed, falling back to other methods")
    PYPDF2_AVAILABLE = False

# Try importing pdf2image for PDF to image conversion
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    logger.warning("pdf2image not installed, PDF to image conversion unavailable")
    PDF2IMAGE_AVAILABLE = False

def extract_text_from_pdf_with_pypdf2(file_path: str) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        logger.info(f"Extracting text from PDF with PyPDF2: {file_path}")
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            
            logger.info(f"Extracted {len(text)} characters with PyPDF2")
            return text
    except Exception as e:
        logger.error(f"Error extracting text with PyPDF2: {e}")
        return ""

def check_for_pdftotext() -> bool:
    """Check if pdftotext (from poppler-utils) is installed."""
    try:
        subprocess.run(["pdftotext", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False

def extract_text_with_pdftotext(file_path: str) -> str:
    """Extract text from PDF using pdftotext utility."""
    try:
        logger.info(f"Extracting text from PDF with pdftotext: {file_path}")
        # Create a temporary file to store the extracted text
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_txt_path = temp_file.name
        
        # Run pdftotext to extract text
        result = subprocess.run(
            ["pdftotext", "-layout", file_path, temp_txt_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Read the extracted text
        with open(temp_txt_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        
        # Clean up the temporary file
        os.unlink(temp_txt_path)
        
        logger.info(f"Extracted {len(text)} characters with pdftotext")
        return text
    except Exception as e:
        logger.error(f"Error extracting text with pdftotext: {e}")
        return ""

def convert_pdf_to_images(file_path: str, dpi: int = 300) -> list:
    """Convert PDF to a list of images."""
    try:
        logger.info(f"Converting PDF to images: {file_path}")
        # Create a temp directory for images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert PDF to images
            images = convert_from_path(file_path, dpi=dpi, output_folder=temp_dir)
            logger.info(f"Converted PDF to {len(images)} images")
            
            # Save images to temp files
            image_paths = []
            for i, img in enumerate(images):
                img_path = os.path.join(temp_dir, f"page_{i+1}.png")
                img.save(img_path, "PNG")
                image_paths.append(img_path)
            
            return image_paths
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        return []

def get_file_type(file_path: str) -> str:
    """Determine file type by extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.pdf']:
        return 'pdf'
    elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']:
        return 'image'
    elif ext in ['.doc', '.docx']:
        return 'word'
    else:
        return 'unknown'

def extract_text_with_openai(file_path: str, openai_client=None) -> str:
    """Extract text from document using OpenAI's Vision API."""
    if not openai_client:
        logger.warning("OpenAI client not provided, can't use OpenAI Vision API")
        return ""
    
    try:
        logger.info(f"Extracting text with OpenAI Vision API: {file_path}")
        
        # Determine file type
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Set content type
        if file_ext in ['.pdf']:
            content_type = "application/pdf"
        elif file_ext in ['.jpg', '.jpeg']:
            content_type = "image/jpeg"
        elif file_ext in ['.png']:
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"
        
        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        # Encode as base64
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        
        # Call OpenAI vision model
        response = openai_client.chat.completions.create(
            model="gpt-4.1",  # Use vision-capable model
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

def extract_text_from_document(file_path: str, vision_client=None, openai_client=None) -> str:
    """Extract text from document based on file type."""
    file_type = get_file_type(file_path)
    logger.info(f"Extracting text from {file_type} file: {file_path}")
    
    if file_type == 'pdf':
        # Try multiple methods in order of preference
        text = ""
        
        # 1. Try PyPDF2 first (pure Python, no dependencies)
        if PYPDF2_AVAILABLE:
            text = extract_text_from_pdf_with_pypdf2(file_path)
            if text and len(text.strip()) > 100:  # If we got meaningful text
                return text
        
        # 2. Try pdftotext if available (better extraction)
        if check_for_pdftotext():
            text = extract_text_with_pdftotext(file_path)
            if text and len(text.strip()) > 100:  # If we got meaningful text
                return text
        
        # 3. If the previous methods failed, try Vision API on converted images
        if PDF2IMAGE_AVAILABLE and vision_client:
            logger.info("Attempting to extract text using PDF to image conversion and Vision API")
            image_paths = convert_pdf_to_images(file_path)
            combined_text = ""
            
            for img_path in image_paths:
                try:
                    # Use Vision API to extract text from each image
                    with open(img_path, "rb") as f:
                        content = f.read()
                    
                    from google.cloud import vision
                    image = vision.Image(content=content)
                    response = vision_client.document_text_detection(image=image)
                    
                    if response.error.message:
                        logger.error(f"Vision API error: {response.error.message}")
                        continue
                        
                    page_text = response.full_text_annotation.text
                    combined_text += page_text + "\n\n"
                    
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}")
            
            if combined_text and len(combined_text.strip()) > 100:
                logger.info(f"Extracted {len(combined_text)} characters using Vision API on images")
                return combined_text
        
        # 4. Try OpenAI Vision API as a last resort (best for image-based PDFs)
        if openai_client:
            logger.info("Attempting to extract text using OpenAI Vision API")
            openai_text = extract_text_with_openai(file_path, openai_client)
            if openai_text and len(openai_text.strip()) > 100:
                return openai_text
        
        # If we got any text from previous methods but it was too short
        if text:
            return text
            
        # Fallback message if all methods failed
        return f"Failed to extract text from PDF file: {os.path.basename(file_path)}. The PDF may be scanned, image-based, or secured."
        
    elif file_type == 'image':
        # First try Google Vision API
        if vision_client:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                
                from google.cloud import vision
                image = vision.Image(content=content)
                response = vision_client.document_text_detection(image=image)
                
                if response.error.message:
                    logger.error(f"Vision API error: {response.error.message}")
                    # Fall back to OpenAI if Vision API fails
                    if openai_client:
                        logger.info("Falling back to OpenAI Vision API for image")
                        return extract_text_with_openai(file_path, openai_client)
                    return f"Error extracting text: {response.error.message}"
                    
                extracted_text = response.full_text_annotation.text
                # If Vision API returns limited text, try OpenAI
                if len(extracted_text.strip()) < 100 and openai_client:
                    logger.info("Vision API returned limited text, trying OpenAI Vision API")
                    openai_text = extract_text_with_openai(file_path, openai_client)
                    if openai_text and len(openai_text.strip()) > len(extracted_text.strip()):
                        return openai_text
                
                logger.info(f"Extracted {len(extracted_text)} characters from image")
                return extracted_text
            except Exception as e:
                logger.error(f"Error extracting text from image: {e}")
                # Fall back to OpenAI if Vision API fails
                if openai_client:
                    logger.info("Falling back to OpenAI Vision API after Vision API error")
                    return extract_text_with_openai(file_path, openai_client)
                return f"Error extracting text from image: {str(e)}"
        # If Vision client not available, try OpenAI
        elif openai_client:
            logger.info("Vision API not available, using OpenAI Vision API for image")
            return extract_text_with_openai(file_path, openai_client)
        else:
            return "No text extraction services available for image"
    
    # Fallback for unsupported file types
    return f"Unsupported file type: {file_type}. Please upload a PDF or image file."