import os
import logging
import uuid
import random
import time  
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json
import re

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Request, Body, Header, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
import jwt
import motor.motor_asyncio
from bson import ObjectId

# Import shared utilities and connections
from .interviewprep import (
    extract_text_from_document, 
    vision_client, 
    openai_client, 
    conversations_col, 
    call_openai,
    SECRET_KEY
)

# Import CV utilities
from .cv_utils import (
    ensure_uploads_dir,
    generate_timestamp_id,
    clean_filename,
    get_potential_file_paths,
    find_cv_by_id
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure environment variables
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://host.docker.internal:27017")
logger.info(f"Using MongoDB URI for job description research: {MONGODB_URI}")

# Try to import web scraping libraries
try:
    import requests
    import bs4
    from bs4 import BeautifulSoup
    SCRAPING_AVAILABLE = True
except ImportError:
    logger.warning("Web scraping libraries (requests, BeautifulSoup) not installed")
    SCRAPING_AVAILABLE = False

# Try to import PDF generation libraries
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    PDF_GEN_AVAILABLE = True
except ImportError:
    logger.warning("PDF generation libraries (reportlab) not installed")
    PDF_GEN_AVAILABLE = False

# Create router
router = APIRouter()
logger.info("Job Description Research Router created")

# Get database references
try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client["futureforceai"]
    job_searches_col = db["job_searches"]  # Collection for job search history
    logger.info("MongoDB connection established for job description research")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB for job description: {e}")
    client = None
    db = None
    job_searches_col = None

# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------

class SuggestRolesRequest(BaseModel):
    cv_id: str

class JobResearchRequest(BaseModel):
    job_role: str
    cv_id: Optional[str] = None

class SkillsGap(BaseModel):
    matching_skills: List[str]
    missing_skills: List[str]
    recommendations: Optional[str] = None

class JobDescriptionData(BaseModel):
    job_role: str
    summary: str
    responsibilities: List[str]
    qualifications: List[str]
    salary: Optional[str] = None
    benefits: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    skills_gap: Optional[SkillsGap] = None
    additional_info: Optional[str] = None
    sources: Optional[List[str]] = None

class PDFGenerationRequest(BaseModel):
    job_role: str
    job_data: JobDescriptionData

# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------

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

async def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return user_id if valid"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("userId")
        if not user_id:
            logger.warning("Invalid token: missing userId")
            return None
        return user_id
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None

async def get_cv_text(cv_id: str, user_id: str) -> Optional[str]:
    """Get CV text from MongoDB by ID with improved error handling"""
    if db is None:  # Changed from "if db:"
        logger.error("MongoDB not connected")
        return None
    
    try:
        # Try to find the CV document
        cv_document = await find_cv_by_id(db, cv_id, user_id)
        
        if not cv_document:
            logger.warning(f"CV not found: {cv_id}")
            return None
        
        # Get CV text from document using different possible field names
        cv_text = None
        
        # First check extracted text field
        if 'extractedText' in cv_document and cv_document['extractedText']:
            logger.info("Using 'extractedText' field from CV document")
            cv_text = cv_document['extractedText']
            
        # Try content field if extractedText not found
        if not cv_text and 'content' in cv_document and cv_document['content']:
            logger.info("Using 'content' field from CV document")
            cv_text = cv_document['content']
        
        # If still no text, try extracting from file
        if not cv_text or len(cv_text.strip()) < 100:
            # Get potential file paths
            potential_paths = get_potential_file_paths(cv_document)
            logger.info(f"Trying potential file paths: {potential_paths}")
            
            # Try each path
            for path in potential_paths:
                if os.path.exists(path):
                    logger.info(f"Found file at path: {path}")
                    try:
                        cv_text = extract_text_from_document(path, vision_client, openai_client)
                        if cv_text and len(cv_text.strip()) >= 100:
                            logger.info(f"Successfully extracted {len(cv_text)} chars from file")
                            
                            # Update database with extracted text
                            cv_collection = db.get_collection("cvs")
                            await cv_collection.update_one(
                                {"_id": cv_document["_id"]},
                                {"$set": {
                                    "extractedText": cv_text,
                                    "lastUsed": datetime.utcnow()
                                }}
                            )
                            logger.info(f"Updated CV document with extracted text")
                            break
                    except Exception as e:
                        logger.error(f"Error extracting text from file: {e}")
                        # Continue trying other paths instead of failing completely
        
        # If we still don't have usable CV text, return None
        if not cv_text or len(cv_text.strip()) < 100:
            logger.error(f"Could not extract sufficient content from CV")
            return None
            
        return cv_text
    
    except Exception as e:
        logger.error(f"Error retrieving CV text: {e}")
        return None

def scrape_job_listings(job_role: str, num_listings: int = 5) -> List[str]:
    """
    Scrape job listings from Indeed and Glassdoor with improved error handling.
    """
    if not SCRAPING_AVAILABLE:
        logger.warning("Web scraping libraries not available")
        return []
    
    job_descriptions = []
    
    try:
        # Setup user agents for realistic browsing
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ]
        
        logger.info(f"Starting job scraping for role: {job_role}")
        
        # Scrape from Indeed with enhanced error handling
        try:
            indeed_descriptions = scrape_indeed_jobs(job_role, num_listings, user_agents)
            if indeed_descriptions:
                job_descriptions.extend(indeed_descriptions)
                logger.info(f"Scraped {len(indeed_descriptions)} descriptions from Indeed")
            else:
                logger.warning("No descriptions scraped from Indeed")
        except Exception as indeed_err:
            logger.error(f"Indeed scraping failed: {indeed_err}")
        
        # Scrape from Glassdoor with enhanced error handling
        try:
            glassdoor_descriptions = scrape_glassdoor_jobs(job_role, num_listings, user_agents)
            if glassdoor_descriptions:
                job_descriptions.extend(glassdoor_descriptions)
                logger.info(f"Scraped {len(glassdoor_descriptions)} descriptions from Glassdoor")
            else:
                logger.warning("No descriptions scraped from Glassdoor")
        except Exception as glassdoor_err:
            logger.error(f"Glassdoor scraping failed: {glassdoor_err}")
        
        logger.info(f"Scraped {len(job_descriptions)} job descriptions total")
        
    except Exception as e:
        logger.error(f"Error during job scraping: {e}")
    
    # If no data from scraping, generate with AI
    if not job_descriptions:
        logger.info(f"No job descriptions found through scraping. Generating with AI for: {job_role}")
        try:
            fallback_prompt = (
                f"Create a comprehensive job description for the role of {job_role}. "
                f"Include typical responsibilities, required qualifications, and technologies used. "
                f"Make it detailed and realistic, as if it were posted by a real company."
            )
            
            simulated_description = call_openai(fallback_prompt)
            job_descriptions = [simulated_description]
            logger.info(f"Successfully generated AI job description for {job_role}")
        except Exception as ai_err:
            logger.error(f"Error generating AI job description: {ai_err}")
    
    return job_descriptions


def scrape_indeed_jobs(job_role: str, num_listings: int, user_agents: List[str]) -> List[str]:
    """
    Scrape job listings from Indeed with enhanced error handling and CAPTCHA detection.
    """
    job_descriptions = []
    
    try:
        # Prepare search URL
        search_term = job_role.lower().replace(" ", "+")
        url = f"https://www.indeed.com/jobs?q={search_term}"
        
        logger.info(f"Attempting to scrape Indeed at: {url}")
        
        # Setup headers
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Session for maintaining cookies
        session = requests.Session()
        
        # Make request
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        logger.info(f"Indeed response status: {response.status_code}")
        logger.info(f"Response URL: {response.url}")
        
        if response.status_code == 403:
            logger.warning("Indeed returned 403 Forbidden - checking for CAPTCHA or blocks")
            
            # Save the response for debugging
            with open('/tmp/indeed_403_response.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info("Saved 403 response to /tmp/indeed_403_response.html for debugging")
            
            # More comprehensive CAPTCHA detection
            captcha_indicators = [
                "captcha",
                "recaptcha",
                "challenge",
                "verify",
                "bot",
                "human",
                "security check",
                "automated",
                "unusual traffic",
                "blocked"
            ]
            
            response_text_lower = response.text.lower()
            captcha_detected = any(indicator in response_text_lower for indicator in captcha_indicators)
            
            # Log what we found in the response
            logger.info(f"Response preview (first 500 chars): {response.text[:500]}")
            
            if captcha_detected:
                logger.info("CAPTCHA or security check detected on Indeed")
                
                # Try to find reCAPTCHA site key
                site_key = extract_captcha_site_key(response.text)
                if not site_key:
                    # Indeed's known reCAPTCHA site key
                    site_key = "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"
                    logger.info(f"Using Indeed's known site key: {site_key}")
                
                # Attempt to solve CAPTCHA
                try:
                    captcha_token = handle_captcha_challenge(response.url, headers, site_key=site_key)
                    if captcha_token:
                        logger.info("CAPTCHA solved successfully, retrying request")
                        
                        # Submit the CAPTCHA solution
                        # First, try to find the form action URL
                        soup = BeautifulSoup(response.text, 'html.parser')
                        form = soup.find('form', {'id': 'challenge-form'}) or soup.find('form')
                        
                        if form and form.get('action'):
                            action_url = form['action']
                            if not action_url.startswith('http'):
                                action_url = f"https://www.indeed.com{action_url}"
                        else:
                            action_url = response.url
                        
                        # Submit CAPTCHA solution
                        captcha_data = {
                            'g-recaptcha-response': captcha_token,
                            'h-captcha-response': captcha_token,  # In case it's hCaptcha
                        }
                        
                        captcha_response = session.post(action_url, data=captcha_data, headers=headers, allow_redirects=True)
                        
                        if captcha_response.status_code == 200:
                            logger.info("CAPTCHA submission successful, retrying original request")
                            response = session.get(url, headers=headers, timeout=15)
                        else:
                            logger.warning(f"CAPTCHA submission failed with status: {captcha_response.status_code}")
                            return job_descriptions
                    else:
                        logger.warning("Failed to solve CAPTCHA, skipping Indeed")
                        return job_descriptions
                except Exception as captcha_error:
                    logger.error(f"Error handling CAPTCHA: {captcha_error}")
                    return job_descriptions
            else:
                logger.warning("Access denied without detectable CAPTCHA, Indeed may be blocking the IP")
                logger.info("Consider using proxy rotation or waiting before retrying")
                return job_descriptions
        
        elif response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if we're on a CAPTCHA page even with 200 status
            if any(indicator in response.text.lower() for indicator in ["captcha", "recaptcha", "challenge"]):
                logger.info("CAPTCHA page detected despite 200 status")
                site_key = extract_captcha_site_key(response.text) or "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"
                captcha_token = handle_captcha_challenge(response.url, headers, site_key=site_key)
                if captcha_token:
                    # Handle CAPTCHA submission similar to above
                    soup_form = soup.find('form', {'id': 'challenge-form'}) or soup.find('form')
                    if soup_form and soup_form.get('action'):
                        action_url = soup_form['action']
                        if not action_url.startswith('http'):
                            action_url = f"https://www.indeed.com{action_url}"
                        
                        captcha_data = {'g-recaptcha-response': captcha_token}
                        captcha_response = session.post(action_url, data=captcha_data, headers=headers)
                        
                        if captcha_response.status_code == 200:
                            response = session.get(url, headers=headers, timeout=15)
                            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple selectors for job cards (Indeed frequently changes these)
            selectors = [
                {'name': 'div', 'attrs': {'class': 'cardOutline'}},
                {'name': 'div', 'attrs': {'class': 'job_seen_beacon'}},
                {'name': 'div', 'attrs': {'class': 'jobsearch-SerpJobCard'}},
                {'name': 'td', 'attrs': {'class': 'resultContent'}},
                {'name': 'div', 'attrs': {'class': 'jobCard_mainContent'}}
            ]
            
            job_cards = []
            for selector in selectors:
                job_cards = soup.find_all(**selector)
                if job_cards:
                    logger.info(f"Found {len(job_cards)} job cards using selector: {selector}")
                    break
            
            if not job_cards:
                logger.warning("No job cards found on Indeed - page structure may have changed")
                # Log a sample of the page content for debugging
                logger.debug(f"Page content sample: {response.text[:500]}")
                return job_descriptions
            
            # Limit to requested number of listings
            job_cards = job_cards[:num_listings]
            
            for i, card in enumerate(job_cards):
                try:
                    # Try multiple selectors for job links
                    link_selectors = [
                        {'name': 'a', 'attrs': {'class': 'jcs-JobTitle'}},
                        {'name': 'h2', 'attrs': {'class': 'jobTitle'}},
                        {'name': 'a', 'attrs': {'data-jk': True}},
                        {'name': 'a', 'attrs': {'id': lambda x: x and x.startswith('job_')}},
                    ]
                    
                    job_link = None
                    for link_selector in link_selectors:
                        job_link = card.find(**link_selector)
                        if job_link:
                            if job_link.name == 'h2':
                                job_link = job_link.find('a')
                            break
                    
                    if job_link and 'href' in job_link.attrs:
                        job_url = job_link['href']
                        if not job_url.startswith('http'):
                            job_url = 'https://www.indeed.com' + job_url
                        
                        logger.info(f"Processing job {i+1}/{len(job_cards)}: {job_url}")
                        
                        # Get detailed job description
                        job_description = fetch_indeed_job_details(job_url, headers, session)
                        if job_description:
                            job_descriptions.append(job_description)
                            logger.info(f"Successfully scraped job {i+1}")
                        
                        # Add delay to avoid rate limiting
                        time.sleep(random.uniform(2, 5))
                    else:
                        logger.warning(f"No valid link found in job card {i+1}")
                        
                except Exception as card_err:
                    logger.error(f"Error processing Indeed job card {i+1}: {card_err}")
                    continue
                    
        else:
            logger.warning(f"Indeed responded with unexpected status code: {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.error("Indeed request timed out")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error when accessing Indeed")
    except Exception as e:
        logger.error(f"Error scraping Indeed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return job_descriptions


def fetch_indeed_job_details(job_url: str, headers: dict, session: requests.Session = None) -> Optional[str]:
    """
    Fetch detailed job description from an Indeed job posting.
    """
    try:
        if session is None:
            session = requests.Session()
            
        # Add random delay
        time.sleep(random.uniform(1, 3))
        
        logger.info(f"Fetching job details from: {job_url}")
        
        response = session.get(job_url, headers=headers, timeout=15)
        
        if response.status_code == 403:
            logger.warning(f"Access denied for job details: {job_url}")
            # Try CAPTCHA handling if needed
            if "captcha" in response.text.lower():
                captcha_token = handle_captcha_challenge(job_url, headers)
                if captcha_token:
                    headers['g-recaptcha-response'] = captcha_token
                    response = session.get(job_url, headers=headers, timeout=15)
                else:
                    return None
            else:
                return None
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple selectors for job description
            description_selectors = [
                {'name': 'div', 'attrs': {'id': 'jobDescriptionText'}},
                {'name': 'div', 'attrs': {'class': 'jobsearch-jobDescriptionText'}},
                {'name': 'div', 'attrs': {'class': 'jobDescription'}},
                {'name': 'div', 'attrs': {'class': 'description'}}
            ]
            
            job_desc_element = None
            for selector in description_selectors:
                job_desc_element = soup.find(**selector)
                if job_desc_element:
                    break
            
            if job_desc_element:
                # Extract text and clean
                job_description = job_desc_element.get_text(separator='\n', strip=True)
                
                # Add metadata if available
                metadata_selectors = {
                    'company': [
                        {'name': 'div', 'attrs': {'data-testid': 'inlineHeader-companyName'}},
                        {'name': 'span', 'attrs': {'class': 'companyName'}},
                        {'name': 'div', 'attrs': {'class': 'companyName'}}
                    ],
                    'location': [
                        {'name': 'div', 'attrs': {'data-testid': 'job-location'}},
                        {'name': 'div', 'attrs': {'class': 'companyLocation'}},
                        {'name': 'span', 'attrs': {'class': 'location'}}
                    ]
                }
                
                full_description = ""
                
                # Extract company
                for selector in metadata_selectors['company']:
                    company_element = soup.find(**selector)
                    if company_element:
                        full_description += f"Company: {company_element.get_text(strip=True)}\n"
                        break
                
                # Extract location
                for selector in metadata_selectors['location']:
                    location_element = soup.find(**selector)
                    if location_element:
                        full_description += f"Location: {location_element.get_text(strip=True)}\n"
                        break
                
                full_description += f"\n{job_description}"
                
                logger.info(f"Successfully extracted job description ({len(full_description)} chars)")
                return full_description
            else:
                logger.warning("Could not find job description element")
                
        else:
            logger.warning(f"Failed to fetch Indeed job details: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error fetching Indeed job details: {e}")
    
    return None

def scrape_glassdoor_jobs(job_role: str, num_listings: int, user_agents: List[str]) -> List[str]:
    """
    Scrape job listings from Glassdoor with enhanced error handling.
    """
    job_descriptions = []
    
    try:
        # Prepare search URL
        search_term = job_role.lower().replace(" ", "-")
        url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={search_term}"
        
        logger.info(f"Attempting to scrape Glassdoor at: {url}")
        
        # Setup headers
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1"
        }
        
        # Session for maintaining cookies
        session = requests.Session()
        
        # Add delay
        time.sleep(random.uniform(2, 4))
        
        # Make request
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        logger.info(f"Glassdoor response status: {response.status_code}")
        
        if response.status_code == 403:
            logger.warning("Glassdoor returned 403 Forbidden - likely blocked by anti-bot measures")
            
            # Check if it's a CAPTCHA page
            if "captcha" in response.text.lower() or "recaptcha" in response.text.lower():
                logger.info("CAPTCHA detected on Glassdoor")
                captcha_token = handle_captcha_challenge(url, headers)
                if captcha_token:
                    logger.info("CAPTCHA solved, retrying request")
                    headers['g-recaptcha-response'] = captcha_token
                    response = session.get(url, headers=headers, timeout=15)
                else:
                    logger.warning("Failed to solve CAPTCHA, skipping Glassdoor")
                    return job_descriptions
            else:
                logger.warning("Access denied without CAPTCHA, skipping Glassdoor")
                return job_descriptions
        
        elif response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check for CAPTCHA page
            if "captcha" in response.text.lower() or "verify you are human" in response.text.lower():
                logger.info("CAPTCHA page detected despite 200 status")
                captcha_token = handle_captcha_challenge(url, headers)
                if captcha_token:
                    response = session.get(url, headers=headers, timeout=15)
                    soup = BeautifulSoup(response.content, 'html.parser')
                else:
                    return job_descriptions
            
            # Try multiple selectors for job listings
            selectors = [
                {'name': 'li', 'attrs': {'class': 'JobsList_jobListItem__wjTHv'}},
                {'name': 'li', 'attrs': {'class': 'react-job-listing'}},
                {'name': 'article', 'attrs': {'data-test': 'jobListing'}},
                {'name': 'div', 'attrs': {'data-test': 'job-results-list'}}
            ]
            
            job_cards = []
            for selector in selectors:
                job_cards = soup.find_all(**selector)
                if job_cards:
                    logger.info(f"Found {len(job_cards)} job cards using selector: {selector}")
                    break
            
            if not job_cards:
                logger.warning("No job cards found on Glassdoor - page structure may have changed")
                logger.debug(f"Page content sample: {response.text[:500]}")
                return job_descriptions
            
            # Limit to requested number
            job_cards = job_cards[:num_listings]
            
            for i, card in enumerate(job_cards):
                try:
                    # Try multiple selectors for job links
                    link_selectors = [
                        {'name': 'a', 'attrs': {'class': 'JobCard_jobTitle__GLyJ1'}},
                        {'name': 'a', 'attrs': {'data-test': 'job-link'}},
                        {'name': 'a', 'attrs': {'class': 'jobLink'}},
                        {'name': 'a', 'attrs': {'data-job-id': True}}
                    ]
                    
                    job_link = None
                    for link_selector in link_selectors:
                        job_link = card.find(**link_selector)
                        if job_link:
                            break
                    
                    if job_link and 'href' in job_link.attrs:
                        job_url = job_link['href']
                        if not job_url.startswith('http'):
                            job_url = 'https://www.glassdoor.com' + job_url
                        
                        logger.info(f"Processing job {i+1}/{len(job_cards)}: {job_url}")
                        
                        # Get detailed job description
                        job_description = fetch_glassdoor_job_details(job_url, headers, session)
                        if job_description:
                            job_descriptions.append(job_description)
                            logger.info(f"Successfully scraped job {i+1}")
                        
                        # Add delay to avoid rate limiting
                        time.sleep(random.uniform(3, 6))
                    else:
                        logger.warning(f"No valid link found in job card {i+1}")
                        
                except Exception as card_err:
                    logger.error(f"Error processing Glassdoor job card {i+1}: {card_err}")
                    continue
                    
        else:
            logger.warning(f"Glassdoor responded with unexpected status code: {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.error("Glassdoor request timed out")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error when accessing Glassdoor")
    except Exception as e:
        logger.error(f"Error scraping Glassdoor: {e}")
    
    return job_descriptions


def fetch_glassdoor_job_details(job_url: str, headers: dict) -> Optional[str]:
    """
    Fetch detailed job description from a Glassdoor job posting.
    """
    try:
        response = requests.get(job_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job description container
            job_desc_element = soup.find('div', {'class': 'JobDetails_jobDescription__uW_fK'})
            
            if job_desc_element:
                # Extract text and clean
                job_description = job_desc_element.get_text(separator='\n', strip=True)
                
                # Add metadata if available
                company_element = soup.find('div', {'class': 'EmployerProfile_employerName__9MGcV'})
                location_element = soup.find('div', {'class': 'JobDetails_location__Ds1fM'})
                salary_element = soup.find('div', {'class': 'JobCard_salaryEstimate__QpbTW'})
                
                full_description = ""
                if company_element:
                    full_description += f"Company: {company_element.get_text(strip=True)}\n"
                if location_element:
                    full_description += f"Location: {location_element.get_text(strip=True)}\n"
                if salary_element:
                    full_description += f"Salary: {salary_element.get_text(strip=True)}\n"
                full_description += f"\n{job_description}"
                
                return full_description
                
        else:
            logger.warning(f"Failed to fetch Glassdoor job details: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error fetching Glassdoor job details: {e}")
    
    return None


def extract_job_data_from_description(job_description: str) -> Dict[str, Any]:
    """
    Extract structured data from job description text using AI.
    """
    try:
        prompt = (
            f"Extract the following information from this job description:\n"
            f"1. Job title\n"
            f"2. Company name\n"
            f"3. Location\n"
            f"4. Required skills\n"
            f"5. Required experience\n"
            f"6. Education requirements\n"
            f"7. Salary range (if mentioned)\n"
            f"8. Key responsibilities\n\n"
            f"Job description:\n{job_description}\n\n"
            f"Format the response as JSON with the keys: title, company, location, skills, experience, education, salary, responsibilities."
        )
        
        response = call_openai(prompt)
        job_data = json.loads(response)
        return job_data
    except Exception as e:
        logger.error(f"Error extracting job data: {e}")
        return {}


def handle_captcha_challenge(site_url: str, headers: dict, site_key: str = None) -> Optional[str]:
    """
    Handle CAPTCHA challenges using 2Captcha service.
    """
    try:
        api_key = os.getenv("TWOCAPTCHA_API_KEY")
        if not api_key:
            logger.error("2Captcha API key not set - cannot solve CAPTCHA")
            logger.info("To use CAPTCHA solving, set TWOCAPTCHA_API_KEY environment variable")
            return None
        
        logger.info(f"Attempting to solve CAPTCHA for: {site_url}")
        
        # If site_key not provided, try to extract it
        if not site_key:
            response = requests.get(site_url, headers=headers, timeout=10)
            site_key = extract_captcha_site_key(response.text)
            
            if not site_key:
                logger.error(f"Could not extract CAPTCHA site key for {site_url}")
                # Use a default test key as fallback
                if "indeed.com" in site_url:
                    site_key = "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"  # Indeed's key
                elif "glassdoor.com" in site_url:
                    site_key = "6LdKlZEpAAAAAOFgFOtx4g1XgPakC3RvjKjVm5Jj"  # Glassdoor's key
                else:
                    site_key = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"  # Google's test key
                logger.info(f"Using default site key: {site_key}")
        
        # Solve CAPTCHA using 2Captcha
        try:
            from twocaptcha import TwoCaptcha
            solver = TwoCaptcha(api_key)
            
            logger.info(f"Sending CAPTCHA to 2Captcha service...")
            logger.info(f"Site key: {site_key}")
            logger.info(f"Page URL: {site_url}")
            
            result = solver.recaptcha(
                sitekey=site_key,
                url=site_url,
                version='v2'
            )
            
            if isinstance(result, dict) and 'code' in result:
                captcha_token = result['code']
            else:
                captcha_token = result
                
            logger.info(f"CAPTCHA solved successfully. Token received.")
            return captcha_token
            
        except ImportError:
            logger.error("2Captcha library not installed. Install with: pip install 2captcha-python")
            return None
        except Exception as solver_err:
            logger.error(f"2Captcha error: {solver_err}")
            return None
        
    except Exception as e:
        logger.error(f"Error handling CAPTCHA: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def extract_captcha_site_key(html_content: str) -> Optional[str]:
    """Extract reCAPTCHA site key from HTML content."""
    try:
        # Common patterns for reCAPTCHA site keys
        patterns = [
            r'data-sitekey=["\']([0-9A-Za-z_-]{40})["\']',
            r'sitekey["\']?\s*:\s*["\']([0-9A-Za-z_-]{40})["\']',
            r'render=["\']([0-9A-Za-z_-]{40})["\']'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            if matches:
                return matches[0]
        
        # Default test key if nothing found and we know there's a CAPTCHA
        return "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"  # Google's test key
    except Exception as e:
        logger.error(f"Error extracting CAPTCHA site key: {e}")
        return None
    
    

async def suggest_roles_from_cv(cv_text: str) -> List[str]:
    """Use OpenAI to suggest job roles based on CV text with enhanced error handling"""
    try:
        # Create prompt for OpenAI
        prompt = (
            "Based on the following CV/resume, suggest 5-7 relevant job roles that this person would be qualified for. "
            "Consider their education, skills, experience, and projects. "
            "ONLY return a simple comma-separated list of job roles, nothing else.\n\n"
            f"CV/Resume text:\n{cv_text[:2000]}..."  # Limit text length to avoid token limits
        )
        
        # Call OpenAI with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = call_openai(prompt)
                break
            except Exception as e:
                logger.error(f"OpenAI API call failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:  # Last attempt
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
        # Process the response to extract roles
        roles = []
        if response:
            # Split by commas and clean up
            roles = [role.strip() for role in response.split(',')]
            # Remove any empty strings or very short roles
            roles = [role for role in roles if len(role) > 3]
            # Limit to max 7 roles
            roles = roles[:7]
        
        # If no roles were extracted or the API call failed, return default roles
        if not roles:
            logger.warning("No roles extracted from OpenAI response, using defaults")
            return ["Software Engineer", "Web Developer", "Data Analyst", "Project Manager", "IT Specialist"]
        
        return roles
    
    except Exception as e:
        logger.error(f"Error suggesting roles from CV: {e}")
        # Return default roles on error to prevent complete failure
        return ["Software Engineer", "Web Developer", "Data Analyst", "Project Manager", "IT Specialist"]



async def analyze_job_description(job_role: str, job_descriptions: List[str], cv_text: Optional[str] = None) -> Dict:
    """
    Use OpenAI to analyze job descriptions with source indicators.
    If CV text is provided, also perform skills gap analysis.
    """
    try:
        # Determine if we're using real or AI-generated data
        is_ai_generated = len(job_descriptions) == 1 and len(job_descriptions[0]) > 500
        source_type = "AI-generated based on job market trends" if is_ai_generated else "Real job listings"
        
        # Combine job descriptions into one text
        combined_desc = "\n\n---\n\n".join(job_descriptions)
        
        # Base prompt for job analysis - More explicit instruction for JSON format
        prompt = (
            f"You are a career expert analyzing job listings for the role of '{job_role}'.\n\n"
            f"Below are {'an AI-generated job description' if is_ai_generated else 'several job listings'} for this role. "
            f"Please analyze {'it' if is_ai_generated else 'them'} and provide:\n"
            f"1. A concise summary of the role (2-3 sentences)\n"
            f"2. A list of key responsibilities commonly mentioned\n"
            f"3. A list of required qualifications and skills\n"
            f"4. Typical salary range and benefits if mentioned\n"
            f"5. Common technologies and tools required\n\n"
            f"Job listings:\n{combined_desc}\n\n"
            f"IMPORTANT: Return ONLY valid JSON with no additional text or formatting.\n"
            f"The response must be a JSON object with these exact keys: summary, responsibilities (array), "
            f"qualifications (array), salary (string or null), benefits (array or null), "
            f"technologies (array), additional_info (string or null).\n"
            f"Example format:\n"
            f'{{"summary": "...", "responsibilities": ["..."], "qualifications": ["..."], "salary": null, "benefits": null, "technologies": ["..."], "additional_info": null}}'
        )
        
        # Call OpenAI for job analysis
        job_analysis_response = call_openai(prompt)
        
        # Clean the response before parsing
        cleaned_response = job_analysis_response.strip()
        
        # Remove markdown code blocks if present
        if cleaned_response.startswith("```"):
            # Find the start and end of the JSON content
            lines = cleaned_response.split('\n')
            json_started = False
            json_lines = []
            
            for line in lines:
                if line.startswith("```") and not json_started:
                    json_started = True
                    continue
                elif line.startswith("```") and json_started:
                    break
                elif json_started:
                    json_lines.append(line)
            
            cleaned_response = '\n'.join(json_lines).strip()
        
        # Parse the JSON response
        try:
            job_data = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            logger.error(f"Response was: {cleaned_response}")
            
            # Extract JSON from text response using regex as fallback
            import re
            json_pattern = r'\{[\s\S]*\}'
            json_matches = re.findall(json_pattern, cleaned_response)
            
            if json_matches:
                # Try parsing the first JSON object found
                try:
                    job_data = json.loads(json_matches[0])
                except json.JSONDecodeError:
                    # Create minimal valid structure
                    job_data = {
                        "summary": f"Software Engineer role focusing on developing high-quality software applications.",
                        "responsibilities": ["Unable to parse responsibilities from the response"],
                        "qualifications": ["Unable to parse qualifications from the response"],
                        "technologies": [],
                        "salary": None,
                        "benefits": None,
                        "additional_info": None
                    }
            else:
                # Create minimal valid structure
                job_data = {
                    "summary": f"Software Engineer role focusing on developing high-quality software applications.",
                    "responsibilities": ["Unable to parse responsibilities from the response"],
                    "qualifications": ["Unable to parse qualifications from the response"],
                    "technologies": [],
                    "salary": None,
                    "benefits": None,
                    "additional_info": None
                }
        
        # Add skills gap analysis if CV text is provided
        if cv_text:
            skills_gap_prompt = (
                f"Based on this job analysis and CV, provide a skills gap analysis.\n\n"
                f"Job Role: {job_role}\n"
                f"Job Summary: {job_data.get('summary', '')}\n"
                f"Required Skills: {', '.join(job_data.get('qualifications', []))}\n"
                f"Required Technologies: {', '.join(job_data.get('technologies', []))}\n\n"
                f"CV Text (first 2000 chars): {cv_text[:2000]}\n\n"
                f"Return ONLY a JSON object with these exact keys:\n"
                f"matching_skills (array of strings)\n"
                f"missing_skills (array of strings)\n"
                f"recommendations (string)\n\n"
                f"Example:\n"
                f'{{"matching_skills": ["Python", "SQL"], "missing_skills": ["AWS", "Docker"], "recommendations": "Focus on cloud technologies..."}}'
            )
            
            # Call OpenAI for skills gap analysis
            skills_gap_response = call_openai(skills_gap_prompt)
            
            # Clean and parse skills gap response
            cleaned_skills_response = skills_gap_response.strip()
            
            # Remove markdown if present
            if cleaned_skills_response.startswith("```"):
                lines = cleaned_skills_response.split('\n')
                json_started = False
                json_lines = []
                
                for line in lines:
                    if line.startswith("```") and not json_started:
                        json_started = True
                        continue
                    elif line.startswith("```") and json_started:
                        break
                    elif json_started:
                        json_lines.append(line)
                
                cleaned_skills_response = '\n'.join(json_lines).strip()
            
            # Parse the skills gap JSON
            try:
                skills_gap_data = json.loads(cleaned_skills_response)
                job_data["skills_gap"] = skills_gap_data
            except json.JSONDecodeError:
                # Try regex extraction
                import re
                json_pattern = r'\{[\s\S]*\}'
                json_matches = re.findall(json_pattern, cleaned_skills_response)
                
                if json_matches:
                    try:
                        skills_gap_data = json.loads(json_matches[0])
                        job_data["skills_gap"] = skills_gap_data
                    except json.JSONDecodeError:
                        job_data["skills_gap"] = {
                            "matching_skills": ["Unable to determine matching skills"],
                            "missing_skills": ["Unable to determine missing skills"],
                            "recommendations": "Please review the job requirements manually"
                        }
                else:
                    job_data["skills_gap"] = {
                        "matching_skills": ["Unable to determine matching skills"],
                        "missing_skills": ["Unable to determine missing skills"],
                        "recommendations": "Please review the job requirements manually"
                    }
        
        # Add source information
        if is_ai_generated:
            job_data["sources"] = [f"AI-generated comprehensive job description for {job_role}"]
        else:
            job_data["sources"] = ["Data aggregated from multiple job listings"]
        
        # Add a flag for frontend to know if it's AI-generated
        job_data["is_ai_generated"] = is_ai_generated
        
        return job_data
    
    except Exception as e:
        logger.error(f"Error analyzing job descriptions: {e}")
        # Return a valid structure even on error
        return {
            "summary": f"Software Engineer role focusing on developing and maintaining high-quality software applications.",
            "responsibilities": ["Unable to parse responsibilities due to an error"],
            "qualifications": ["Unable to parse qualifications due to an error"],
            "technologies": [],
            "salary": None,
            "benefits": None,
            "additional_info": None,
            "sources": ["Error occurred while processing"],
            "is_ai_generated": True
        }
        
        

async def generate_pdf(job_role: str, job_data: Dict) -> bytes:
    """Generate a PDF report from job description data"""
    if not PDF_GEN_AVAILABLE:
        logger.warning("PDF generation libraries not available")
        return b"PDF generation libraries not available"
    
    try:
        # Create a temporary file for the PDF
        pdf_buffer = bytearray()
        
        # Create the PDF document
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=letter,
            rightMargin=72, 
            leftMargin=72,
            topMargin=72, 
            bottomMargin=72
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Title',
            parent=styles['Heading1'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='Section',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12
        ))
        styles.add(ParagraphStyle(
            name='Normal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6
        ))
        styles.add(ParagraphStyle(
            name='Bullet',
            parent=styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceAfter=3
        ))
        
        # Build content
        elements = []
        
        # Title
        elements.append(Paragraph(f"Job Description: {job_role}", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Summary
        elements.append(Paragraph("Summary", styles['Section']))
        elements.append(Paragraph(job_data.get("summary", "No summary available"), styles['Normal']))
        elements.append(Spacer(1, 10))
        
        # Responsibilities
        elements.append(Paragraph("Key Responsibilities", styles['Section']))
        responsibilities = job_data.get("responsibilities", [])
        if responsibilities:
            bullet_list = []
            for resp in responsibilities:
                bullet_list.append(ListItem(Paragraph(resp, styles['Bullet'])))
            elements.append(ListFlowable(bullet_list, bulletType='bullet', leftIndent=20))
        else:
            elements.append(Paragraph("No specific responsibilities listed.", styles['Normal']))
        elements.append(Spacer(1, 10))
        
        # Qualifications
        elements.append(Paragraph("Required Qualifications", styles['Section']))
        qualifications = job_data.get("qualifications", [])
        if qualifications:
            bullet_list = []
            for qual in qualifications:
                bullet_list.append(ListItem(Paragraph(qual, styles['Bullet'])))
            elements.append(ListFlowable(bullet_list, bulletType='bullet', leftIndent=20))
        else:
            elements.append(Paragraph("No specific qualifications listed.", styles['Normal']))
        elements.append(Spacer(1, 10))
        
        # Salary and Benefits
        if job_data.get("salary") or job_data.get("benefits"):
            elements.append(Paragraph("Compensation & Benefits", styles['Section']))
            if job_data.get("salary"):
                elements.append(Paragraph(f"Salary: {job_data['salary']}", styles['Normal']))
            
            benefits = job_data.get("benefits", [])
            if benefits:
                elements.append(Paragraph("Benefits:", styles['Normal']))
                bullet_list = []
                for benefit in benefits:
                    bullet_list.append(ListItem(Paragraph(benefit, styles['Bullet'])))
                elements.append(ListFlowable(bullet_list, bulletType='bullet', leftIndent=20))
            elements.append(Spacer(1, 10))
        
        # Technologies
        technologies = job_data.get("technologies", [])
        if technologies:
            elements.append(Paragraph("Technologies & Tools", styles['Section']))
            tech_para = ", ".join(technologies)
            elements.append(Paragraph(tech_para, styles['Normal']))
            elements.append(Spacer(1, 10))
        
        # Skills Gap Analysis
        if job_data.get("skills_gap"):
            elements.append(Paragraph("Skills Gap Analysis", styles['Section']))
            
            # Matching Skills
            elements.append(Paragraph("Your Matching Skills:", styles['Normal']))
            matching_skills = job_data["skills_gap"].get("matching_skills", [])
            if matching_skills:
                bullet_list = []
                for skill in matching_skills:
                    bullet_list.append(ListItem(Paragraph(skill, styles['Bullet'])))
                elements.append(ListFlowable(bullet_list, bulletType='bullet', leftIndent=20))
            else:
                elements.append(Paragraph("No matching skills identified.", styles['Normal']))
            elements.append(Spacer(1, 6))
            
            # Missing Skills
            elements.append(Paragraph("Skills to Develop:", styles['Normal']))
            missing_skills = job_data["skills_gap"].get("missing_skills", [])
            if missing_skills:
                bullet_list = []
                for skill in missing_skills:
                    bullet_list.append(ListItem(Paragraph(skill, styles['Bullet'])))
                elements.append(ListFlowable(bullet_list, bulletType='bullet', leftIndent=20))
            else:
                elements.append(Paragraph("No specific skill gaps identified.", styles['Normal']))
            elements.append(Spacer(1, 6))
            
            # Recommendations
            if job_data["skills_gap"].get("recommendations"):
                elements.append(Paragraph("Recommendations:", styles['Normal']))
                elements.append(Paragraph(job_data["skills_gap"]["recommendations"], styles['Normal']))
            elements.append(Spacer(1, 10))
        
        # Additional Information
        if job_data.get("additional_info"):
            elements.append(Paragraph("Additional Information", styles['Section']))
            elements.append(Paragraph(job_data["additional_info"], styles['Normal']))
            elements.append(Spacer(1, 10))
        
        # Sources
        if job_data.get("sources"):
            elements.append(Paragraph("Sources", styles['Section']))
            sources = job_data.get("sources", [])
            if sources:
                bullet_list = []
                for source in sources:
                    bullet_list.append(ListItem(Paragraph(source, styles['Bullet'])))
                elements.append(ListFlowable(bullet_list, bulletType='bullet', leftIndent=20))
            elements.append(Spacer(1, 10))
        
        # Date of report
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            f"Generated on {datetime.utcnow().strftime('%Y-%m-%d')} by FutureForceAI", 
            styles['Normal']
        ))
        
        # Build PDF
        doc.build(elements)
        
        return bytes(pdf_buffer)
    
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return f"Error generating PDF: {str(e)}".encode('utf-8')

# ------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------

@router.get("/history")
async def get_search_history(request: Request):
    """
    Get the user's job search history.
    """
    logger.info("Fetching job search history")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check if MongoDB is available
    if job_searches_col is None:
        logger.error("MongoDB not connected")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"}
        )
    
    try:
        # Retrieve search history
        cursor = job_searches_col.find(
            {"user_id": user_id},
            {"job_role": 1, "created_at": 1}
        ).sort("created_at", -1).limit(20)
        
        history = await cursor.to_list(length=20)
        
        # Format response
        formatted_history = []
        for item in history:
            formatted_history.append({
                "id": str(item["_id"]),
                "job_role": item["job_role"],
                "created_at": item["created_at"].isoformat() if isinstance(item["created_at"], datetime) else item["created_at"]
            })
        
        return {"history": formatted_history}
    except Exception as e:
        logger.error(f"Error retrieving search history: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error retrieving search history: {str(e)}"}
        )

@router.post("/suggest-roles")
async def suggest_roles(
    request: Request,
    data: SuggestRolesRequest
):
    """
    Suggest relevant job roles based on the user's CV.
    """
    logger.info(f"Suggesting roles based on CV ID: {data.cv_id}")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Get CV text
    cv_text = await get_cv_text(data.cv_id, user_id)
    if not cv_text:
        return JSONResponse(
            status_code=404,
            content={"detail": "Could not retrieve or extract CV content"}
        )
    
    # Suggest roles based on CV text
    suggested_roles = await suggest_roles_from_cv(cv_text)
    if not suggested_roles:
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to suggest roles based on CV"}
        )
    
    # Return suggested roles
    return {"suggested_roles": suggested_roles}

@router.post("/research")
async def research_job(
    request: Request,
    data: JobResearchRequest
):
    """
    Research a job role and provide comprehensive information.
    """
    logger.info(f"Researching job role: {data.job_role}")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Start with CV text as None
    cv_text = None
    
    # Get CV text if cv_id is provided
    if data.cv_id:
        cv_text = await get_cv_text(data.cv_id, user_id)
        if cv_text:
            logger.info(f"Retrieved CV text for skills gap analysis")
    
    # Scrape job listings
    job_descriptions = scrape_job_listings(data.job_role)
    
    # If scraping failed or no descriptions found, use a fallback approach
    if not job_descriptions:
        logger.warning(f"Web scraping failed for job role: {data.job_role}")
        
        # Generate a simulated job description using AI
        fallback_prompt = (
            f"Create a comprehensive job description for the role of {data.job_role}. "
            f"Include typical responsibilities, required qualifications, and technologies used. "
            f"Make it detailed and realistic, as if it were posted by a real company."
        )
        
        simulated_description = call_openai(fallback_prompt)
        job_descriptions = [simulated_description]
    
    # Analyze job descriptions
    job_data = await analyze_job_description(data.job_role, job_descriptions, cv_text)
    
    # Save search to history
    if job_searches_col is not None:
        try:
            search_record = {
                "user_id": user_id,
                "job_role": data.job_role,
                "created_at": datetime.utcnow(),
                "cv_id": data.cv_id
            }
            
            await job_searches_col.insert_one(search_record)
            logger.info(f"Saved job search to history: {data.job_role}")
        except Exception as db_err:
            logger.error(f"Error saving search history: {db_err}")
    
    # Return job data
    job_data["job_role"] = data.job_role
    return job_data

@router.post("/generate-pdf")
async def create_pdf(
    request: Request,
    data: PDFGenerationRequest
):
    """
    Generate a PDF report for a job description.
    """
    logger.info(f"Generating PDF for job role: {data.job_role}")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Generate PDF
    pdf_bytes = await generate_pdf(data.job_role, data.job_data.dict())
    
    # Return PDF as attachment
    filename = f"{data.job_role.replace(' ', '_')}_Job_Description.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/suggest-roles-upload")
async def suggest_roles_upload(
    request: Request,
    cv_file: UploadFile = File(...),
):
    """
    Suggest relevant job roles based on an uploaded CV with improved error handling.
    """
    logger.info(f"Suggesting roles based on uploaded CV: {cv_file.filename}")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Extract optional fields from form data
    form = await request.form()
    captcha_token = form.get("captcha_token")
    browser_info = form.get("browser_info")
    
    # Log received browser info
    if browser_info:
        try:
            browser_data = json.loads(browser_info)
            logger.info(f"Received browser info: {json.dumps(browser_data, indent=2)}")
        except:
            logger.warning("Failed to parse browser info")
    
    # Check for CAPTCHA verification if needed
    if captcha_token:
        logger.info("CAPTCHA token provided, verifying...")
        # In a real implementation, you would verify the token with reCAPTCHA service
        # For now, we'll just log it and continue
    
    # Check if we need to generate a CAPTCHA challenge
    # This could be based on IP rate limiting, suspicious behavior, etc.
    should_require_captcha = False  # Change based on your criteria
    
    if should_require_captcha and not captcha_token:
        logger.warning("CAPTCHA verification required but no token provided")
        return JSONResponse(
            status_code=403,
            content={
                "detail": "CAPTCHA verification required",
                "captcha_required": True,
                "captcha_site_key": "your-recaptcha-site-key"  # Replace with your actual site key
            }
        )
    
    try:
        # Ensure uploads directory exists
        uploads_dir = ensure_uploads_dir()
        
        # Generate a unique filename
        file_id = generate_timestamp_id()
        clean_filename_str = clean_filename(cv_file.filename or "uploaded_cv.pdf")
        filename = f"{file_id}_{clean_filename_str}"
        file_path = os.path.join(uploads_dir, filename)
        
        # Save file to disk with proper error handling
        try:
            content = await cv_file.read()
            if not content or len(content) < 100:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Uploaded file is empty or too small"}
                )
                
            with open(file_path, "wb") as f:
                f.write(content)
                
            # Reset file pointer
            await cv_file.seek(0)
            
            logger.info(f"CV file saved to: {file_path}")
        except Exception as file_err:
            logger.error(f"Error saving file: {file_err}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to save uploaded file"}
            )
        
        # Extract text from CV with timeout protection
        try:
            cv_text = extract_text_from_document(file_path, vision_client, openai_client)
            if not cv_text or len(cv_text.strip()) < 100:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Could not extract sufficient content from CV. Please try a different file."}
                )
        except Exception as extract_err:
            logger.error(f"Error extracting text: {extract_err}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to process CV content. Please try a different file format."}
            )
        
        # Save to database for future use
        try:
            cv_collection = db.get_collection("cvs")
            if cv_collection is not None:
                cv_document = {
                    "userId": user_id,
                    "filename": filename,
                    "originalName": cv_file.filename or "uploaded_cv.pdf",
                    "filePath": file_path,
                    "fileSize": len(content),
                    "contentType": cv_file.content_type or "application/octet-stream",
                    "extractedText": cv_text,
                    "uploadedAt": datetime.utcnow(),
                    "lastUsed": datetime.utcnow(),
                    "fileId": file_id
                }
            
            result = await cv_collection.insert_one(cv_document)
            cv_id = str(result.inserted_id)
            logger.info(f"Saved CV to database with ID: {cv_id}")
        except Exception as db_err:
            logger.error(f"Database error: {db_err}")
            # Continue even if DB save fails - we can still suggest roles
            cv_id = f"temp_{file_id}"
        
        # Suggest roles based on CV text
        suggested_roles = await suggest_roles_from_cv(cv_text)
        if not suggested_roles:
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to suggest roles based on CV"}
            )
        
        # Return suggested roles along with CV ID
        return {
            "suggested_roles": suggested_roles,
            "cv_id": cv_id
        }
    except Exception as e:
        logger.error(f"Error in suggest_roles_upload: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred: {str(e)}"}
        )
        
        

@router.post("/solve-captcha")
async def solve_captcha(
    request: Request,
    data: dict = Body(...)
):
    """
    Solve a reCAPTCHA with improved logging.
    """
    logger.info(f"Solving CAPTCHA with data: {data}")
    
    # Get token from request
    token = await get_token_from_request(request)
    if not token:
        logger.warning("No authentication token found")
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    
    # Verify token
    user_id = await verify_token(token)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication token"}
        )
    
    # Check required parameters
    site_key = data.get("site_key")
    page_url = data.get("page_url")
    
    logger.info(f"CAPTCHA solve request for site_key: {site_key}, page_url: {page_url}")
    
    if not site_key or not page_url:
        logger.error("Missing required parameters")
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing required parameters: site_key or page_url"}
        )
    
    try:
        # Import 2Captcha with detailed error handling
        try:
            from twocaptcha import TwoCaptcha, NetworkException, ApiException, TimeoutException, ValidationException
            logger.info("Successfully imported 2Captcha library")
        except ImportError as imp_err:
            logger.error(f"Failed to import 2Captcha: {imp_err}")
            return JSONResponse(
                status_code=500,
                content={"detail": "CAPTCHA solving service not configured - library missing"}
            )
        
        # Your 2Captcha API key - should be stored in environment variable
        api_key = os.getenv("TWOCAPTCHA_API_KEY")
        if not api_key:
            logger.error("2Captcha API key not set in environment")
            return JSONResponse(
                status_code=500,
                content={"detail": "CAPTCHA solving service not configured - missing API key"}
            )
        
        logger.info(f"Using 2Captcha API key: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
        
        # Initialize solver
        solver = TwoCaptcha(api_key)
        
        # Detect if it's invisible reCAPTCHA
        is_invisible = data.get("is_invisible", False)
        
        # Solve the CAPTCHA
        logger.info(f"Sending CAPTCHA to 2Captcha: site_key={site_key}, url={page_url}, invisible={is_invisible}")
        
        try:
            result = solver.recaptcha(
                sitekey=site_key,
                url=page_url,
                invisible=1 if is_invisible else 0,
                version='v2'
            )
            logger.info(f"2Captcha raw result: {result}")
        except NetworkException as ne:
            logger.error(f"2Captcha network error: {ne}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"CAPTCHA network error: {str(ne)}"}
            )
        except ApiException as ae:
            logger.error(f"2Captcha API error: {ae}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"CAPTCHA API error: {str(ae)}"}
            )
        except TimeoutException as te:
            logger.error(f"2Captcha timeout: {te}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"CAPTCHA solving timed out: {str(te)}"}
            )
        except ValidationException as ve:
            logger.error(f"2Captcha validation error: {ve}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"CAPTCHA validation error: {str(ve)}"}
            )
        except Exception as e:
            logger.error(f"General 2Captcha error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"CAPTCHA solving failed: {str(e)}"}
            )
        
        # Extract token
        if isinstance(result, dict) and 'code' in result:
            captcha_token = result['code']
        else:
            captcha_token = result
        
        if not captcha_token:
            logger.error("No token received from 2Captcha")
            return JSONResponse(
                status_code=500,
                content={"detail": "No CAPTCHA token received"}
            )
        
        logger.info(f"CAPTCHA solved successfully. Token: {captcha_token[:15]}...")
        
        # Return the token
        return {"captcha_token": captcha_token}
    
    except Exception as e:
        logger.error(f"Error solving CAPTCHA: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error solving CAPTCHA: {str(e)}"}
        )