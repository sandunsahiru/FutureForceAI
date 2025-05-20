import os
import logging
import base64
from typing import Optional, Tuple
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    logger.warning("PyPDF2 not installed, falling back to other methods")
    PYPDF2_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    logger.warning("pdf2image not installed, PDF to image conversion unavailable")
    PDF2IMAGE_AVAILABLE = False

try:
    import fitz  
    PYMUPDF_AVAILABLE = True
except ImportError:
    logger.warning("PyMuPDF not installed, falling back to other methods")
    PYMUPDF_AVAILABLE = False

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

def extract_text_with_pymupdf(file_path: str) -> str:
    """Extract text from PDF using PyMuPDF (fitz)."""
    if not PYMUPDF_AVAILABLE:
        return ""
        
    try:
        logger.info(f"Extracting text from PDF with PyMuPDF: {file_path}")
        doc = fitz.open(file_path)
        text = ""
        for page_num in range(len(doc)):
            text += doc[page_num].get_text() + "\n"
        
        logger.info(f"Extracted {len(text)} characters with PyMuPDF")
        return text
    except Exception as e:
        logger.error(f"Error extracting text with PyMuPDF: {e}")
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
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_txt_path = temp_file.name
        
        result = subprocess.run(
            ["pdftotext", "-layout", file_path, temp_txt_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        with open(temp_txt_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        
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
        with tempfile.TemporaryDirectory() as temp_dir:
            images = convert_from_path(file_path, dpi=dpi, output_folder=temp_dir)
            logger.info(f"Converted PDF to {len(images)} images")
            
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

        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in ['.pdf']:
            content_type = "application/pdf"
        elif file_ext in ['.jpg', '.jpeg']:
            content_type = "image/jpeg"
        elif file_ext in ['.png']:
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"
        
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4.1-mini", 
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

            if len(extracted_text.strip()) < 100:
                logger.info("Minimal text extracted with gpt-4.1-mini, trying with full gpt-4.1 model")
                raise ValueError("Insufficient text extracted, trying larger model")
                
            logger.info(f"Successfully extracted {len(extracted_text)} characters with OpenAI gpt-4.1-mini")
            return extracted_text
            
        except Exception as mini_err:
            logger.info(f"Trying extraction with full gpt-4.1 model: {str(mini_err)}")
            
            response = openai_client.chat.completions.create(
                model="gpt-4.1", 
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
            logger.info(f"Successfully extracted {len(extracted_text)} characters with OpenAI gpt-4.1")
            return extracted_text
            
    except Exception as e:
        logger.error(f"Error extracting text with OpenAI Vision API: {e}")
        return ""

def extract_text_from_document(file_path: str, vision_client=None, openai_client=None) -> str:
    """
    Extract text from a document file using multiple methods and select the best result.
    Tries various extraction techniques and returns the one with the most content.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return f"File not found: {file_path}"
        
    file_type = get_file_type(file_path)
    logger.info(f"Extracting text from {file_type} file: {file_path}")
    
    extraction_results = []
    
    if file_type == 'pdf':
        # Try PyPDF2
        if PYPDF2_AVAILABLE:
            text = extract_text_from_pdf_with_pypdf2(file_path)
            if text:
                extraction_results.append((text, "PyPDF2", len(text)))
        
        # Try PyMuPDF
        if PYMUPDF_AVAILABLE:
            text = extract_text_with_pymupdf(file_path)
            if text:
                extraction_results.append((text, "PyMuPDF", len(text)))
        
        # Try pdftotext utility
        if check_for_pdftotext():
            text = extract_text_with_pdftotext(file_path)
            if text:
                extraction_results.append((text, "pdftotext", len(text)))
        
        # Try Vision API
        if PDF2IMAGE_AVAILABLE and vision_client:
            logger.info("Attempting to extract text using PDF to image conversion and Vision API")
            image_paths = convert_pdf_to_images(file_path)
            combined_text = ""
            
            for img_path in image_paths:
                try:
                    
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
            
            if combined_text:
                extraction_results.append((combined_text, "Google Vision", len(combined_text)))
        
        # Try OpenAI Vision API
        if openai_client:
            openai_text = extract_text_with_openai(file_path, openai_client)
            if openai_text:
                extraction_results.append((openai_text, "OpenAI Vision", len(openai_text)))
                
    elif file_type == 'image':
        if vision_client:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                
                from google.cloud import vision
                image = vision.Image(content=content)
                response = vision_client.document_text_detection(image=image)
                
                if not response.error.message:
                    extracted_text = response.full_text_annotation.text
                    if extracted_text:
                        extraction_results.append((extracted_text, "Google Vision", len(extracted_text)))
            except Exception as e:
                logger.error(f"Error with Google Vision: {e}")
                
        if openai_client:
            openai_text = extract_text_with_openai(file_path, openai_client)
            if openai_text:
                extraction_results.append((openai_text, "OpenAI Vision", len(openai_text)))

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
            if text and len(text.strip()) > 20:
                extraction_results.append((text, "Direct Text Read", len(text)))
    except Exception as e:
        logger.debug(f"Direct text read failed: {e}")
    
    
    if extraction_results:
        logger.info(f"Text extracted using {len(extraction_results)} methods:")
        for text, method, length in extraction_results:
            logger.info(f"  - {method}: {length} characters")
        
        extraction_results.sort(key=lambda x: x[2], reverse=True)
        best_text, best_method, length = extraction_results[0]
        
        logger.info(f"Selected extraction method: {best_method} with {length} characters")
        return best_text
    
    logger.error(f"All text extraction methods failed for file: {file_path}")
    return f"Failed to extract text from file: {os.path.basename(file_path)}. The file may be corrupt, empty, or in an unsupported format."