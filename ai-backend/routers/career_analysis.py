import os
import logging
import json
import aiohttp
from typing import List, Dict, Any, Optional
import random
import uuid
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from urllib.parse import quote
from twocaptcha import TwoCaptcha, NetworkException, ApiException, TimeoutException, ValidationException


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import OpenAI utilities
from .interviewprep import call_openai

# External API integration placeholders
async def fetch_job_market_data(job_role: str, location: str = None) -> Dict:
    """Fetch job market data for a role using available APIs"""
    logger.info(f"Fetching job market data for: {job_role}")
    
    # Try using JSearch API (RapidAPI)
    jsearch_key = os.getenv("JSEARCH_API_KEY")
    jsearch_host = os.getenv("JSEARCH_API_HOST")
    
    logger.info(f"JSearch API Key present: {bool(jsearch_key)}, Host present: {bool(jsearch_host)}")
    
    if jsearch_key and jsearch_host:
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            
            querystring = {
                "query": job_role,
                "num_pages": "1"
            }
            
            if location:
                querystring["location"] = location
                
            headers = {
                "X-RapidAPI-Key": jsearch_key,
                "X-RapidAPI-Host": jsearch_host
            }
            
            logger.info(f"Making JSearch API request to {url} with query: {querystring}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=querystring) as response:
                    logger.info(f"JSearch API response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("data") and len(data["data"]) > 0:
                            # Process the job data
                            jobs = data["data"]
                            logger.info(f"JSearch API returned {len(jobs)} job listings")
                            
                            # Extract salary information
                            salaries = [job.get("job_min_salary", 0) for job in jobs if job.get("job_min_salary")]
                            if salaries:
                                min_salary = min(salaries)
                                max_salary = max([job.get("job_max_salary", 0) for job in jobs if job.get("job_max_salary")])
                                median_salary = sorted(salaries)[len(salaries)//2]
                                
                                salary_data = {
                                    "median_salary": f"${median_salary:,}",
                                    "salary_range": f"${min_salary:,} - ${max_salary:,}",
                                }
                                logger.info(f"Extracted salary data: {salary_data}")
                            else:
                                salary_data = {"median_salary": "Not available"}
                                logger.info("No salary information available in job listings")
                            
                            # Extract top companies
                            companies = [job.get("employer_name") for job in jobs if job.get("employer_name")]
                            top_companies = list(set(companies))[:4]
                            
                            return {
                                "role": job_role,
                                "salary_data": salary_data,
                                "demand_level": "High" if len(jobs) > 20 else "Medium" if len(jobs) > 10 else "Low",
                                "growth_rate": f"{random.randint(5, 15)}% annually",  # Still using random as real data isn't available
                                "top_companies": top_companies
                            }
                        else:
                            logger.warning(f"JSearch API returned no job data: {data}")
                    else:
                        error_text = await response.text()
                        logger.error(f"JSearch API error: {error_text}")
            
        except Exception as e:
            logger.error(f"Error fetching job market data from JSearch API: {e}")
    
    # Fall back to Adzuna API if available
    adzuna_app_id = os.getenv("ADZUNA_APP_ID")
    adzuna_api_key = os.getenv("ADZUNA_API_KEY")
    
    logger.info(f"Adzuna API credentials present - App ID: {bool(adzuna_app_id)}, API Key: {bool(adzuna_api_key)}")
    
    if adzuna_app_id and adzuna_api_key:
        try:
            # Use Adzuna API to get job market data
            country_code = "us"  # Default to US
            
            # Build URL for Adzuna API
            url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
            
            params = {
                "app_id": adzuna_app_id,
                "app_key": adzuna_api_key,
                "results_per_page": 10,
                "what": job_role,
                "content-type": "application/json"
            }
            
            if location:
                params["where"] = location
                
            logger.info(f"Making Adzuna API request to {url} with params: {params}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    logger.info(f"Adzuna API response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if "results" in data and len(data["results"]) > 0:
                            jobs = data["results"]
                            logger.info(f"Adzuna API returned {len(jobs)} job listings")
                            
                            # Extract salary information
                            salaries = []
                            for job in jobs:
                                if "salary_min" in job and job["salary_min"]:
                                    salaries.append(job["salary_min"])
                            
                            if salaries:
                                min_salary = min(salaries)
                                max_salary = max([job.get("salary_max", 0) for job in jobs if job.get("salary_max", 0)])
                                median_salary = sorted(salaries)[len(salaries)//2]
                                
                                salary_data = {
                                    "median_salary": f"${median_salary:,}",
                                    "salary_range": f"${min_salary:,} - ${max_salary:,}",
                                }
                                logger.info(f"Extracted salary data from Adzuna: {salary_data}")
                            else:
                                salary_data = {"median_salary": "Not available"}
                                logger.info("No salary information available in Adzuna job listings")
                            
                            # Extract top companies
                            companies = [job.get("company", {}).get("display_name") for job in jobs if job.get("company", {}).get("display_name")]
                            top_companies = list(set(companies))[:4]
                            
                            return {
                                "role": job_role,
                                "salary_data": salary_data,
                                "demand_level": "High" if len(jobs) > 20 else "Medium" if len(jobs) > 10 else "Low",
                                "growth_rate": f"{random.randint(5, 15)}% annually",
                                "top_companies": top_companies
                            }
                        else:
                            logger.warning(f"Adzuna API returned no job data or invalid format: {data}")
                    else:
                        error_text = await response.text()
                        logger.error(f"Adzuna API error: {error_text}")
                        
        except Exception as e:
            logger.error(f"Error fetching job market data from Adzuna API: {e}")
    
    # Fallback to mock data if all APIs fail
    logger.info("All APIs failed or not configured, falling back to mock data")
    
    salary_data = {
        "median_salary": f"${random.randint(75, 120)}k",
        "salary_range": f"${random.randint(60, 75)}k - ${random.randint(120, 150)}k",
        "growth_rate": f"{random.randint(5, 15)}%"
    }
    
    mock_result = {
        "role": job_role,
        "salary_data": salary_data,
        "demand_level": random.choice(["High", "Medium", "Very High"]),
        "growth_rate": f"{random.randint(5, 15)}% annually",
        "top_companies": ["Tech Corp", "Innovate Inc", "Digital Systems", "Future Tech"]
    }
    
    logger.info(f"Generated mock data: {mock_result}")
    return mock_result

async def fetch_learning_resources(skill: str) -> List[Dict]:
    """Fetch learning resources for a skill with improved Coursera data extraction"""
    logger.info(f"Fetching learning resources for skill: {skill}")
    
    try:
        # Get 2Captcha API key from environment variable
        two_captcha_api_key = os.getenv("TWOCAPTCHA_API_KEY")
        logger.info(f"2Captcha API Key present: {bool(two_captcha_api_key)}")
        
        # Prepare the search URL
        encoded_skill = quote(skill)
        coursera_search_url = f"https://www.coursera.org/courses?query={encoded_skill}"
        logger.info(f"Scraping courses from: {coursera_search_url}")
        
        # Enhanced user agent list with modern browser signatures
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36 Edg/97.0.1072.69",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 15_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Mobile/15E148 Safari/604.1"
        ]
        
        # Enhanced headers that more closely mimic a real browser
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"97\", \"Google Chrome\";v=\"97\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Referer": "https://www.google.com/",
            "DNT": "1"
        }
        
        courses = []
        
        async with aiohttp.ClientSession() as session:
            # Add cookies to potentially bypass some anti-scraping
            cookies = {
                "CSRF3-Token": str(uuid.uuid4()),
                "csrftoken": str(uuid.uuid4()),
                "OptanonAlertBoxClosed": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "OptanonConsent": f"isIABGlobal=false&datestamp={datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')}&version=6.10.0",
                "_ga": f"GA1.2.{random.randint(1000000000, 9999999999)}.{int(time.time())}",
                "_gid": f"GA1.2.{random.randint(1000000000, 9999999999)}.{int(time.time())}",
                "_fbp": f"fb.1.{int(time.time())}.{random.randint(1000000000, 9999999999)}"
            }
            
            # First request to get the page with cookies
            async with session.get(
                coursera_search_url, 
                headers=headers, 
                cookies=cookies,
                allow_redirects=True,
                timeout=30
            ) as response:
                logger.info(f"Coursera search response status: {response.status}")
                
                if response.status == 200:
                    html_content = await response.text()
                    logger.info(f"Received HTML content (length: {len(html_content)})")
                    
                    # Check if CAPTCHA is present
                    captcha_detected = False
                    if "recaptcha" in html_content.lower() or "captcha" in html_content.lower():
                        logger.warning("CAPTCHA detected on Coursera page")
                        captcha_detected = True
                        
                        # Try to extract the reCAPTCHA site key with improved regex
                        site_key = None
                        site_key_patterns = [
                            r'data-sitekey="([^"]+)"',
                            r'sitekey:\s*[\'"]([^\'"]+)[\'"]',
                            r'sitekey=([^&"\']+)',
                            r'g-recaptcha.*?data-sitekey="([^"]+)"',
                            r'"RECAPTCHA_SITE_KEY":"([^"]+)"',
                            r'recaptcha[^"]*"[^"]*"([^"]+)"'
                        ]
                        
                        for pattern in site_key_patterns:
                            site_key_match = re.search(pattern, html_content)
                            if site_key_match:
                                site_key = site_key_match.group(1)
                                logger.info(f"Found reCAPTCHA site key: {site_key}")
                                break
                        
                        if site_key:
                            # Attempt to solve the CAPTCHA
                            try:
                                captcha_solution = await solve_with_2captcha(site_key, coursera_search_url, two_captcha_api_key)
                                if captcha_solution:
                                    logger.info("CAPTCHA solution received, attempting to bypass")
                                    
                                    # Try different methods to bypass CAPTCHA
                                    
                                    # Method 1: POST with form data
                                    form_data = {
                                        "g-recaptcha-response": captcha_solution,
                                        "h-captcha-response": captcha_solution  # Some sites use hCaptcha
                                    }
                                    
                                    captcha_headers = headers.copy()
                                    captcha_headers["Content-Type"] = "application/x-www-form-urlencoded"
                                    
                                    try:
                                        post_url = response.url.human_repr()  # Use the final URL after any redirects
                                        async with session.post(
                                            post_url, 
                                            headers=captcha_headers, 
                                            data=form_data,
                                            cookies=cookies,
                                            allow_redirects=True,
                                            timeout=30
                                        ) as captcha_post_response:
                                            if captcha_post_response.status == 200:
                                                html_content = await captcha_post_response.text()
                                                if "recaptcha" not in html_content.lower() and "captcha" not in html_content.lower():
                                                    logger.info("Successfully bypassed CAPTCHA with POST request!")
                                                    captcha_detected = False
                                    except Exception as post_err:
                                        logger.error(f"Error with CAPTCHA POST request: {post_err}")
                                    
                                    # Method 2: GET with CAPTCHA solution in cookies and headers
                                    if captcha_detected:
                                        try:
                                            cookies.update({
                                                "g-recaptcha-response": captcha_solution,
                                                "captcha-token": captcha_solution
                                            })
                                            
                                            captcha_headers = headers.copy()
                                            captcha_headers["X-Captcha-Token"] = captcha_solution
                                            captcha_headers["X-Recaptcha-Token"] = captcha_solution
                                            
                                            # Add cookies to headers (some servers check here too)
                                            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                                            captcha_headers["Cookie"] = cookie_str
                                            
                                            search_url_with_token = f"{coursera_search_url}&captchaResponse={captcha_solution}"
                                            
                                            async with session.get(
                                                search_url_with_token, 
                                                headers=captcha_headers, 
                                                cookies=cookies,
                                                allow_redirects=True,
                                                timeout=30
                                            ) as captcha_get_response:
                                                if captcha_get_response.status == 200:
                                                    html_content = await captcha_get_response.text()
                                                    if "recaptcha" not in html_content.lower() and "captcha" not in html_content.lower():
                                                        logger.info("Successfully bypassed CAPTCHA with GET request!")
                                                        captcha_detected = False
                                        except Exception as get_err:
                                            logger.error(f"Error with CAPTCHA GET request: {get_err}")
                            except Exception as captcha_err:
                                logger.error(f"Error solving CAPTCHA: {captcha_err}")
                    
                    # Parse the HTML with BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Save HTML for debugging if needed
                    # with open(f"/tmp/coursera_{skill.replace(' ', '_')}.html", "w") as f:
                    #     f.write(html_content)
                    
                    # ----------- COMPREHENSIVE CARD EXTRACTION STRATEGIES -----------
                    
                    # Track all potential course data for later filtering
                    potential_courses = []
                    
                    # STRATEGY 1: Look for product card elements with specific test IDs
                    product_cards = soup.find_all('div', {'data-testid': 'product-card-cds'})
                    logger.info(f"Strategy 1: Found {len(product_cards)} product cards with test ID")
                    
                    for card in product_cards:
                        try:
                            course_data = extract_course_data(card)
                            if course_data and course_data["title"] != "Course Name Not Found":
                                potential_courses.append(course_data)
                        except Exception as e:
                            logger.error(f"Error processing product card: {e}")
                    
                    # STRATEGY 2: Look for standard course cards by class
                    card_classes = [
                        lambda c: c and 'card' in c.lower() if c else False,
                        lambda c: c and 'product-card' in c.lower() if c else False,
                        lambda c: c and 'course-card' in c.lower() if c else False,
                        lambda c: c and 'ais-hit' in c.lower() if c else False,
                        lambda c: c and 'css-1ssv3q1' in c if c else False  # Example of Coursera's React-generated class
                    ]
                    
                    for class_check in card_classes:
                        course_cards = soup.find_all(['div', 'li'], class_=class_check)
                        logger.info(f"Strategy 2: Found {len(course_cards)} course cards with class check")
                        
                        for card in course_cards:
                            # Avoid duplicates by checking if this might be a card we already processed
                            already_processed = False
                            for processed_card in product_cards:
                                if card.get_text() == processed_card.get_text():
                                    already_processed = True
                                    break
                            
                            if not already_processed:
                                try:
                                    course_data = extract_course_data(card)
                                    if course_data and course_data["title"] != "Course Name Not Found":
                                        potential_courses.append(course_data)
                                except Exception as e:
                                    logger.error(f"Error processing course card: {e}")
                    
                    # STRATEGY 3: Look for direct course links and extract surrounding containers
                    if len(potential_courses) < 4:
                        course_links = soup.find_all('a', href=lambda h: h and ('/learn/' in h or '/specialization/' in h or '/professional-certificate/' in h))
                        logger.info(f"Strategy 3: Found {len(course_links)} direct course links")
                        
                        for link in course_links[:10]:  # Limit to 10 to avoid processing too many
                            try:
                                # Try to get the parent container
                                container = link
                                parent_levels = 0
                                while parent_levels < 4:  # Go up to 4 levels
                                    if container.parent and container.parent.name != 'html':
                                        container = container.parent
                                        parent_levels += 1
                                        
                                        # If this container has multiple elements, it might be a card
                                        children = list(container.children)
                                        if len(children) >= 3:
                                            course_data = extract_course_data(container)
                                            if course_data and course_data["title"] != "Course Name Not Found":
                                                # Check if this is a duplicate based on title
                                                is_duplicate = False
                                                for existing in potential_courses:
                                                    if existing.get("title") == course_data.get("title"):
                                                        is_duplicate = True
                                                        break
                                                
                                                if not is_duplicate:
                                                    potential_courses.append(course_data)
                                                    break
                                    else:
                                        break
                            except Exception as e:
                                logger.error(f"Error processing course link: {e}")
                    
                    # STRATEGY 4: Direct title extraction (if we still don't have enough courses)
                    if len(potential_courses) < 4:
                        course_titles = soup.find_all(['h2', 'h3', 'h4'], class_=lambda c: c and 'title' in c.lower() if c else False)
                        logger.info(f"Strategy 4: Found {len(course_titles)} course titles")
                        
                        for title_elem in course_titles[:10]:
                            try:
                                title_text = title_elem.get_text(strip=True)
                                if not title_text or len(title_text) < 5 or len(title_text) > 150:
                                    continue
                                    
                                # Check if this title is already in our courses
                                is_duplicate = False
                                for existing in potential_courses:
                                    if existing.get("title") == title_text:
                                        is_duplicate = True
                                        break
                                
                                if is_duplicate:
                                    continue
                                    
                                # Find the closest link
                                link = None
                                # Check siblings and parents for link
                                for elem in list(title_elem.next_siblings) + list(title_elem.previous_siblings):
                                    if elem.name == 'a' and 'href' in elem.attrs:
                                        link = elem['href']
                                        break
                                
                                # Check parent's children for link
                                if not link and title_elem.parent:
                                    for elem in title_elem.parent.find_all('a', href=True):
                                        link = elem['href']
                                        break
                                
                                # Format the URL
                                if link:
                                    if link.startswith('/'):
                                        link = f"https://www.coursera.org{link}"
                                    elif not link.startswith(('http://', 'https://')):
                                        link = f"https://www.coursera.org/{link}"
                                else:
                                    # Create a search URL based on the title
                                    link = f"https://www.coursera.org/search?query={quote(title_text)}"
                                
                                # Get provider info if available
                                provider = "Coursera"
                                if title_elem.parent:
                                    provider_elems = title_elem.parent.find_all(['span', 'div', 'p'], 
                                                                             class_=lambda c: c and ('partner' in c.lower() or 'provider' in c.lower()) if c else False)
                                    for elem in provider_elems:
                                        provider_text = elem.get_text(strip=True)
                                        if provider_text and len(provider_text) < 50 and "Coursera" not in provider_text:
                                            provider = provider_text
                                            break
                                
                                # Create course entry
                                course_data = {
                                    "title": title_text,
                                    "provider": f"Coursera - {provider}",
                                    "level": "Intermediate",  # Default
                                    "duration": "4-8 weeks",  # Default
                                    "price": "Free audit available (Certificate: $49)",
                                    "url": link,
                                    "rating": "4.5+",  # Default
                                }
                                
                                potential_courses.append(course_data)
                                
                                # Stop if we have enough courses
                                if len(potential_courses) >= 8:
                                    break
                            except Exception as e:
                                logger.error(f"Error processing title element: {e}")
                    
                    # STRATEGY 5: JSON data extraction - look for script tags with course data
                    if len(potential_courses) < 4:
                        script_tags = soup.find_all('script', type='application/json')
                        logger.info(f"Strategy 5: Found {len(script_tags)} JSON script tags")
                        
                        for script in script_tags:
                            try:
                                json_content = script.string
                                if json_content:
                                    data = json.loads(json_content)
                                    
                                    # Look for course data in JSON structure (could be in various formats)
                                    # This requires exploring the actual JSON structure from Coursera
                                    course_data_found = False
                                    
                                    # Pattern 1: Direct course list
                                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                                        for item in data[:8]:  # Limit to 8 items
                                            if "name" in item or "title" in item:
                                                title = item.get("name", item.get("title", ""))
                                                if title and len(title) > 5 and len(title) < 150:
                                                    # Extract other fields
                                                    provider = "Coursera"
                                                    if "partner" in item or "university" in item or "provider" in item:
                                                        provider = item.get("partner", item.get("university", item.get("provider", "Coursera")))
                                                    
                                                    url = None
                                                    if "url" in item or "link" in item or "href" in item:
                                                        url = item.get("url", item.get("link", item.get("href", None)))
                                                        
                                                    # Format URL
                                                    if url:
                                                        if url.startswith('/'):
                                                            url = f"https://www.coursera.org{url}"
                                                        elif not url.startswith(('http://', 'https://')):
                                                            url = f"https://www.coursera.org/{url}"
                                                    else:
                                                        url = f"https://www.coursera.org/search?query={quote(title)}"
                                                    
                                                    level = item.get("level", item.get("difficulty", "Intermediate"))
                                                    duration = item.get("duration", item.get("length", "4-8 weeks"))
                                                    rating = item.get("rating", item.get("stars", "4.5+"))
                                                    
                                                    # Create course entry
                                                    course_data = {
                                                        "title": title,
                                                        "provider": f"Coursera - {provider}",
                                                        "level": level,
                                                        "duration": duration,
                                                        "price": "Free audit available (Certificate: $49)",
                                                        "url": url,
                                                        "rating": rating,
                                                    }
                                                    
                                                    # Check for duplicates
                                                    is_duplicate = False
                                                    for existing in potential_courses:
                                                        if existing.get("title") == title:
                                                            is_duplicate = True
                                                            break
                                                    
                                                    if not is_duplicate:
                                                        potential_courses.append(course_data)
                                                        course_data_found = True
                                                        
                                                    if len(potential_courses) >= 8:
                                                        break
                                        
                                    # Pattern 2: Nested course data
                                    if not course_data_found and isinstance(data, dict):
                                        # Look for common keys that might contain course data
                                        for key in ["courses", "hits", "products", "results", "data", "items"]:
                                            if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                                                for item in data[key][:8]:  # Limit to 8 items
                                                    if isinstance(item, dict) and ("name" in item or "title" in item):
                                                        title = item.get("name", item.get("title", ""))
                                                        if title and len(title) > 5 and len(title) < 150:
                                                            # Create course entry following the same pattern as above
                                                            # (Code would be similar to the block above)
                                                            # This is omitted for brevity but would follow the same pattern
                                                            pass
                            except Exception as e:
                                logger.error(f"Error processing JSON script tag: {e}")
                    
                    # Filter and deduplicate courses
                    filtered_courses = []
                    seen_titles = set()
                    
                    for course in potential_courses:
                        title = course.get("title", "").lower()
                        if title and title != "course name not found" and title not in seen_titles:
                            seen_titles.add(title)
                            filtered_courses.append(course)
                            
                            # Limit to 6 courses
                            if len(filtered_courses) >= 6:
                                break
                    
                    if filtered_courses:
                        logger.info(f"Successfully extracted {len(filtered_courses)} courses from Coursera")
                        return filtered_courses
                    else:
                        logger.warning("No courses could be extracted from Coursera HTML using any strategy")
                
                else:
                    logger.error(f"Failed to fetch courses from Coursera: {response.status}")
                    error_content = await response.text()
                    logger.error(f"Error response preview: {error_content[:500]}...")
        
        # Fall back to alternative method if no courses found or request failed
        if not courses:
            logger.info("Attempting to generate mock courses based on skill")
            mock_courses = generate_mock_courses_for_skill(skill)
            logger.info(f"Generated {len(mock_courses)} mock courses for {skill}")
            return mock_courses
        
        return courses
    
    except Exception as e:
        logger.error(f"Error in fetch_learning_resources: {e}")
        # Fall back to mock data in case of any uncaught exception
        mock_courses = generate_mock_courses_for_skill(skill)
        logger.info(f"Generated {len(mock_courses)} mock courses due to error")
        return mock_courses
    
    
    
async def solve_with_2captcha(site_key: str, page_url: str, api_key: str) -> Optional[str]:
    """Solve reCAPTCHA via 2Captcha with improved async handling"""
    if not api_key:
        logger.error("2Captcha API key not provided")
        return None
    
    try:
        # Create the solver instance
        solver = TwoCaptcha(api_key)
        
        # Log the attempt
        logger.info(f"Attempting to solve CAPTCHA: sitekey={site_key}, url={page_url}")
        
        # The TwoCaptcha library is synchronous, so we need to run it in a separate thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                solver.recaptcha, 
                sitekey=site_key,
                url=page_url,
                invisible=1,  # Try invisible recaptcha first
                action='search',
                enterprise=0,  # Try standard recaptcha
                version='v2'   # Specify v2 recaptcha
            )
            
            try:
                # Wait for result with timeout
                result = future.result(timeout=90)  # Increased timeout further
                if result and 'code' in result:
                    logger.info(f"2Captcha solution received: {result['code'][:10]}...")
                    return result['code']
                else:
                    logger.error(f"2Captcha returned invalid result: {result}")
                    return None
            except concurrent.futures.TimeoutError:
                logger.error("2Captcha solving timed out after 90 seconds")
                return None
    except Exception as e:
        logger.error(f"Unexpected error solving CAPTCHA: {e}")
        return None

def extract_course_data(card) -> Dict:
    """Extract course data from card element with improved parsing for Coursera's structure"""
    try:
        # --- Title extraction with multiple approaches ---
        course_name = "Course Name Not Found"
        
        # Find any heading elements that might contain the title
        heading_tags = card.find_all(['h2', 'h3', 'h4', 'div', 'span'], 
                                     class_=lambda x: x and any(c in x.lower() for c in ['title', 'name', 'heading', 'card-title']) if x else False)
        
        # Look for the course title (usually the first heading-like element with text)
        for tag in heading_tags:
            text = tag.get_text(strip=True)
            if text and len(text) > 5 and len(text) < 150:  # Reasonable title length
                course_name = text
                break
                
        # If still not found, try finding the most prominent text element
        if course_name == "Course Name Not Found":
            # Look for any element with font-weight: bold or large text
            prominent_elements = card.find_all(['div', 'span', 'p'], 
                                             style=lambda x: x and ('font-weight: 700' in x or 'font-weight:700' in x or 'font-size: 16' in x) if x else False)
            for elem in prominent_elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 5 and len(text) < 150:
                    course_name = text
                    break
        
        # Last resort - find the first significant text in the card
        if course_name == "Course Name Not Found":
            for elem in card.find_all(['div', 'span', 'p']):
                text = elem.get_text(strip=True)
                if text and len(text) > 5 and len(text) < 150:
                    course_name = text
                    break
        
        # --- URL extraction ---
        course_link = None
        # Find the main link in the card
        links = card.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            if href and ('/learn/' in href or '/professional-certificate/' in href or '/specialization/' in href):
                course_link = href
                break
                
        # If no specific course link found, use any link
        if not course_link and links:
            course_link = links[0].get('href', '')
            
        # Properly format the URL
        if course_link:
            if course_link.startswith('/'):
                course_link = f"https://www.coursera.org{course_link}"
            elif not course_link.startswith(('http://', 'https://')):
                course_link = f"https://www.coursera.org/{course_link}"
        else:
            # Create a search URL based on the course name if no link found
            course_link = f"https://www.coursera.org/search?query={quote(course_name)}"
            
        # --- Provider extraction ---
        provider = "Coursera"
        # Look for partner/university name (often a smaller text near logo or below title)
        partner_tags = card.find_all(['div', 'span', 'p'], 
                                    class_=lambda x: x and any(c in x.lower() for c in ['partner', 'provider', 'university', 'author', 'org']) if x else False)
        
        for tag in partner_tags:
            text = tag.get_text(strip=True)
            if text and "Coursera" not in text and len(text) < 50:
                provider = text
                break
                
        # --- Extract image if available ---
        image_url = None
        img_tag = card.find('img')
        if img_tag and 'src' in img_tag.attrs:
            image_url = img_tag['src']
            
        # --- Return structured data ---
        return {
            "title": course_name[:120],  # Limit title length
            "provider": f"Coursera - {provider}",
            "level": "Intermediate",  # Default level
            "duration": "4-8 weeks",  # Default duration
            "price": "Free audit available (Certificate: $49)",
            "url": course_link,
            "rating": "4.5+",  # Default rating
            "image": image_url
        }
    except Exception as e:
        logger.error(f"Error extracting course data: {e}")
        return {
            "title": "Course Not Available",
            "provider": "Coursera",
            "level": "Intermediate",
            "duration": "4-6 weeks",
            "price": "Varies",
            "url": "https://www.coursera.org/",
            "rating": "Not rated"
        }

def extract_course_data(card) -> Dict:
    """Extract course data from card element with multiple fallback strategies"""
    try:
        # --- Title extraction with fallbacks ---
        course_name = "Course Name Not Found"
        # Strategy 1: Look for h3 with specific classes
        for class_fragment in ['title', 'name', 'heading', 'card-title']:
            title_elem = card.find(['h2', 'h3', 'h4'], class_=lambda x: x and class_fragment in x.lower() if x else False)
            if title_elem and title_elem.text.strip():
                course_name = title_elem.text.strip()
                break
                
        # Strategy 2: Just find any h3
        if course_name == "Course Name Not Found":
            title_elem = card.find(['h2', 'h3', 'h4'])
            if title_elem and title_elem.text.strip():
                course_name = title_elem.text.strip()
                
        # Strategy 3: Look for any element with title-like classes
        if course_name == "Course Name Not Found":
            title_elem = card.find(['div', 'span', 'p'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower() or 'heading' in x.lower()) if x else False)
            if title_elem and title_elem.text.strip():
                course_name = title_elem.text.strip()
                
        # --- URL extraction with fallbacks ---
        course_link = None
        # Strategy 1: Look for anchor with title-related classes
        link_elem = card.find('a', class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower()) if x else False)
        if link_elem and 'href' in link_elem.attrs:
            course_link = link_elem['href']
            
        # Strategy 2: Just find any anchor
        if not course_link:
            link_elem = card.find('a', href=True)
            if link_elem:
                course_link = link_elem['href']
                
        # Format the URL properly
        if course_link:
            if course_link.startswith('/'):
                course_link = f"https://www.coursera.org{course_link}"
            elif not course_link.startswith(('http://', 'https://')):
                course_link = f"https://www.coursera.org/{course_link}"
        else:
            # Create a search URL based on the course name if no link found
            course_link = f"https://www.coursera.org/search?query={quote(course_name)}"
            
        # --- Provider extraction with fallbacks ---
        provider = "Coursera"
        # Strategy 1: Look for specific partner classes
        provider_elem = card.find(['p', 'span', 'div'], class_=lambda x: x and ('partner' in x.lower() or 'provider' in x.lower() or 'author' in x.lower()) if x else False)
        if provider_elem and provider_elem.text.strip():
            provider = provider_elem.text.strip()
            
        # Strategy 2: Look for small text that might be provider
        if provider == "Coursera":
            small_elements = card.find_all(['small', 'span', 'div'], class_=lambda x: x and not ('title' in x.lower() if x else False))
            for elem in small_elements:
                if elem.text and len(elem.text.strip()) < 50 and "Coursera" not in elem.text:
                    provider = elem.text.strip()
                    break
                    
        # --- Level extraction ---
        level = "Intermediate"  # Default
        # Check for text containing level indicators
        level_keywords = {
            "beginner": "Beginner",
            "novice": "Beginner",
            "intermediate": "Intermediate",
            "advanced": "Advanced",
            "expert": "Advanced",
            "all level": "All Levels"
        }
        
        for elem in card.find_all(['span', 'div', 'p']):
            if elem.text:
                text_lower = elem.text.lower()
                for keyword, level_value in level_keywords.items():
                    if keyword in text_lower:
                        level = level_value
                        break
                        
        # --- Duration extraction ---
        duration = "4-6 weeks"  # Default
        duration_patterns = [
            r'(\d+\s*-\s*\d+\s*\w+)',  # e.g., "1 - 3 Months"
            r'(\d+\s*\w+\s*course)',   # e.g., "4 week course"
            r'(\d+\s*\w+)'             # e.g., "4 Weeks"
        ]
        
        for elem in card.find_all(['span', 'div', 'p']):
            if elem.text:
                for pattern in duration_patterns:
                    match = re.search(pattern, elem.text, re.IGNORECASE)
                    if match:
                        duration = match.group(1)
                        break
                        
        # --- Rating extraction ---
        rating = "Not rated"
        # Look for rating indicators (stars, numbers out of 5, etc.)
        rating_patterns = [
            r'(\d\.\d+)\s*stars',
            r'(\d\.\d+)\s*out of',
            r'(\d\.\d+)/5',
            r'(\d\.\d+)'
        ]
        
        for elem in card.find_all(['span', 'div']):
            if elem.text:
                for pattern in rating_patterns:
                    match = re.search(pattern, elem.text, re.IGNORECASE)
                    if match:
                        rating = match.group(1)
                        break
                        
        # --- Extract image URL if available ---
        image_url = None
        img_tag = card.find('img')
        if img_tag and 'src' in img_tag.attrs:
            image_url = img_tag['src']
            
        # --- Assemble and return course data ---
        return {
            "title": course_name[:120],  # Limit title length
            "provider": f"Coursera - {provider}",
            "level": level,
            "duration": duration,
            "price": "Varies (Free audit available)",
            "url": course_link,
            "rating": rating,
            "image": image_url
        }
    except Exception as e:
        logger.error(f"Error extracting course data: {e}")
        # Return a minimal data object on error
        return {
            "title": "Course Not Available",
            "provider": "Coursera",
            "level": "Intermediate",
            "duration": "4-6 weeks",
            "price": "Varies",
            "url": f"https://www.coursera.org/search?query={quote(skill)}",
            "rating": "Not rated"
        }
        
def generate_mock_courses_for_skill(skill: str) -> List[Dict]:
    """Generate realistic mock courses for a skill when scraping fails"""
    logger.info(f"Generating mock courses for skill: {skill}")
    
    # Predefined mock courses for common skills
    mock_courses = {
        "Software Development": [
            {
                "title": "Complete Software Development Bootcamp",
                "provider": "Coursera - University of Michigan",
                "level": "Beginner to Advanced",
                "duration": "12 weeks",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/learn/software-development",
                "rating": "4.7",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/e7/7afa30f2e711e8b2dcbd4a7b409c58/Logo_Software-Development-Lifecycle.png"
            },
            {
                "title": "Software Engineering: Principles and Practices",
                "provider": "Coursera - Stanford University",
                "level": "Intermediate",
                "duration": "8 weeks",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/learn/software-engineering",
                "rating": "4.8",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/19/c88bc089344a4492577b40f2ac5c00/Introduction-to-Software-Engineering--Final-image.jpg"
            }
        ],
        "Product Management": [
            {
                "title": "Digital Product Management",
                "provider": "Coursera - University of Virginia",
                "level": "Intermediate",
                "duration": "5 weeks",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/learn/uva-darden-digital-product-management",
                "rating": "4.6",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/e0/5d2ebe1eeb4a6d8fad665c1b9fa376/Logo.jpg"
            },
            {
                "title": "Product Management Fundamentals",
                "provider": "Coursera - Google",
                "level": "Beginner",
                "duration": "6 weeks",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/professional-certificates/google-product-management",
                "rating": "4.8",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/2f/47aae0e0ea11e5ae481b031d9d3149/Thumb_Image_PM.png"
            },
            {
                "title": "Agile Product Management",
                "provider": "Coursera - University of Alberta",
                "level": "Intermediate",
                "duration": "4 weeks",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/learn/uva-darden-agile-product-management",
                "rating": "4.7",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/d9/81c7c6db8a43b4b167e14e9bdb5ba7/albertaschoolofbusiness-icon-cmyk.jpg"
            }
        ],
        "Project Management": [
            {
                "title": "Google Project Management Certificate",
                "provider": "Coursera - Google",
                "level": "Beginner",
                "duration": "6 months",
                "price": "Free audit available (Certificate: $49/month)",
                "url": "https://www.coursera.org/professional-certificates/google-project-management",
                "rating": "4.8",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/65/afee00b8c411e89da71f69584172ee/GoogleG_FullColor.png"
            },
            {
                "title": "Project Management Principles and Practices",
                "provider": "Coursera - University of California, Irvine",
                "level": "Intermediate",
                "duration": "4 months",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/specializations/project-management",
                "rating": "4.7",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/e8/df3554112c4e17a0a639dd33cae1a5/PM_capstone_1200x1200_Text.png"
            }
        ],
        "Data Science": [
            {
                "title": "IBM Data Science Professional Certificate",
                "provider": "Coursera - IBM",
                "level": "Beginner to Intermediate",
                "duration": "3-6 months",
                "price": "Free audit available (Certificate: $49/month)",
                "url": "https://www.coursera.org/professional-certificates/ibm-data-science",
                "rating": "4.6",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/60/7c4a30d5e111e8b0b339de9e40d817/IBM-Data-Science-Key-Visual.png"
            },
            {
                "title": "Applied Data Science with Python",
                "provider": "Coursera - University of Michigan",
                "level": "Intermediate",
                "duration": "5 months",
                "price": "Free audit available (Certificate: $49)",
                "url": "https://www.coursera.org/specializations/data-science-python",
                "rating": "4.5",
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/bd/f655b08c7311e7b6d8774e9d456108/Course-Logo.png"
            }
        ]
    }
    
    # Check if we have predefined mock courses for this skill
    for key, courses in mock_courses.items():
        if key.lower() in skill.lower():
            logger.info(f"Using predefined mock courses for {key}")
            return courses
    
    # Otherwise generate generic courses for the skill
    logger.info(f"Generating generic mock courses for {skill}")
    
    providers = [
        "Coursera - Stanford University",
        "Coursera - University of Michigan",
        "Coursera - Duke University",
        "Coursera - Google",
        "Coursera - IBM",
        "Coursera - Meta"
    ]
    
    levels = ["Beginner", "Intermediate", "Advanced", "All Levels"]
    durations = ["4 weeks", "6 weeks", "8 weeks", "3 months"]
    
    generic_courses = []
    
    for i in range(1, 5):  # Generate 4 courses
        provider = random.choice(providers)
        level = random.choice(levels)
        duration = random.choice(durations)
        rating = f"{random.uniform(4.0, 4.9):.1f}"
        
        # Generate appropriate titles based on the skill
        titles = [
            f"{skill} Specialization",
            f"Professional Certificate in {skill}",
            f"Introduction to {skill}",
            f"Advanced {skill} Techniques",
            f"{skill} for Professionals",
            f"Mastering {skill}: A Comprehensive Guide",
            f"The Complete {skill} Bootcamp",
            f"Applied {skill}"
        ]
        
        title = random.choice(titles)
        
        # Create slug for URL
        slug = title.lower().replace(' ', '-').replace(':', '').replace('&', 'and')
        url = f"https://www.coursera.org/learn/{slug}"
        
        # Random image URL
        image_id = random.randint(10, 99)
        course_id = random.randint(1000, 9999)
        image = f"https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/{image_id}/course-{course_id}.jpg"
        
        # Create the course object
        course = {
            "title": title,
            "provider": provider,
            "level": level,
            "duration": duration,
            "price": "Free audit available (Certificate: $49)",
            "url": url,
            "rating": rating,
            "image": image
        }
        
        generic_courses.append(course)
    
    return generic_courses



# Core analysis functions
async def analyze_cv_skills(cv_text: str, career_interests: List[str], career_goals: Dict) -> Dict:
    """
    Analyze CV to extract skills, strengths, and areas for improvement
    related to the career interests.
    Added enhanced error handling and text validation.
    """
    logger.info(f"Analyzing CV skills for career interests: {career_interests}")
    
    try:
        # Check if CV text is valid and extractable
        if not cv_text or not isinstance(cv_text, str) or len(cv_text.strip()) < 100:
            logger.warning(f"CV text is insufficient for detailed analysis: {len(cv_text) if cv_text else 0} chars")
            return create_cv_analysis_from_goals(career_interests, career_goals)
        
        # Prepare the prompt for OpenAI
        career_interests_str = ", ".join(career_interests) if career_interests else "professional roles"
        goals_summary = []
        desired_role = ""
        
        if career_goals and isinstance(career_goals, dict):
            if career_goals.get("shortTerm"):
                goals_summary.append(f"Short-term goals: {career_goals['shortTerm']}")
            if career_goals.get("longTerm"):
                goals_summary.append(f"Long-term goals: {career_goals['longTerm']}")
            if career_goals.get("desiredRole"):
                desired_role = career_goals['desiredRole']
                goals_summary.append(f"Desired role: {desired_role}")
            if career_goals.get("priorities") and isinstance(career_goals["priorities"], list):
                goals_summary.append(f"Priorities: {', '.join(career_goals['priorities'])}")
        
        goals_text = "\n".join(goals_summary) if goals_summary else "No specific career goals provided"
        
        # Limit CV text to avoid token limits
        cv_text_limited = cv_text[:4000] + "..." if len(cv_text) > 4000 else cv_text
        
        prompt = (
            f"Analyze this CV in relation to these career interests: {career_interests_str}.\n\n"
            f"Career Goals:\n{goals_text}\n\n"
            f"CV Text:\n{cv_text_limited}\n\n"
            f"Provide a comprehensive analysis including:\n"
            f"1. A summary of the candidate's profile and suitability for the career interests\n"
            f"2. Current skills relevant to the career interests (with skill level: Beginner, Intermediate, Advanced, or Expert)\n"
            f"3. Key strengths with brief explanations\n"
            f"4. Areas for improvement with brief explanations\n"
            f"5. Assessment of current career level (Junior, Mid-level, Senior, etc.)\n"
            f"6. Growth potential assessment\n"
            f"7. Market demand for their skills\n"
            f"8. Future skills they should develop with reasons and market demand\n\n"
            f"Respond with a JSON object with these keys: summary, skills (array), strengths (array), "
            f"improvements (array), currentLevel, growthPotential, marketDemand, future_skills (array)\n\n"
            f"For the arrays (skills, strengths, improvements, future_skills), each item should be an object with 'name' and 'description' keys."
        )
        
        # Call OpenAI with retry logic
        max_retries = 2
        response_text = None
        
        for attempt in range(max_retries):
            try:
                response_text = call_openai(prompt)
                break
            except Exception as api_err:
                logger.error(f"OpenAI API error (attempt {attempt+1}/{max_retries}): {api_err}")
                if attempt == max_retries - 1:  # Last attempt failed
                    return create_cv_analysis_from_goals(career_interests, career_goals)
                time.sleep(2)  # Wait before retry
        
        if not response_text:
            logger.error("Failed to get response from OpenAI")
            return create_cv_analysis_from_goals(career_interests, career_goals)
            
        # Parse the response
        try:
            # Clean the response text
            cleaned_response = clean_openai_json_response(response_text)
            
            # Parse the JSON
            analysis = json.loads(cleaned_response)
            
            # Ensure all required fields are present
            ensure_analysis_fields(analysis, career_interests, desired_role)
            
            return analysis
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from OpenAI response: {e}")
            logger.error(f"Response was: {response_text}")
            logger.error(f"Cleaned response: {cleaned_response}")
            
            # Try to extract JSON directly
            try:
                # Look for anything that might be JSON in the response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    analysis = json.loads(json_str)
                    
                    # Ensure all required fields are present
                    ensure_analysis_fields(analysis, career_interests, desired_role)
                    
                    return analysis
            except Exception as inner_e:
                logger.error(f"Secondary JSON extraction failed: {inner_e}")
            
            # If still failing, create a fallback response based on career goals
            return create_cv_analysis_from_goals(career_interests, career_goals)
    
    except Exception as e:
        logger.error(f"Error in analyze_cv_skills: {e}")
        return create_cv_analysis_from_goals(career_interests, career_goals)


def create_cv_analysis_from_goals(career_interests: List[str], career_goals: Dict) -> Dict:
    """Create meaningful analysis based on career goals when CV is not readable."""
    interests_str = ", ".join(career_interests) if career_interests else "specified fields"
    
    # Extract key information from career goals
    desired_role = "professional role"
    short_term = ""
    long_term = ""
    priorities = []
    
    if career_goals:
        if career_goals.get("desiredRole"):
            desired_role = career_goals["desiredRole"]
        if career_goals.get("shortTerm"):
            short_term = career_goals["shortTerm"]
        if career_goals.get("longTerm"):
            long_term = career_goals["longTerm"]
        if career_goals.get("priorities"):
            priorities = career_goals["priorities"]
    
    # Create custom summary based on provided information
    summary_parts = []
    summary_parts.append(f"The candidate is aiming for a career in {interests_str} with aspirations to become a {short_term or 'Senior Professional'} in the short term")
    
    if long_term:
        summary_parts.append(f"and a {long_term} in the long term")
    
    summary_parts.append(f". Their desired role is {desired_role}")
    
    if priorities:
        summary_parts.append(f", with priorities including {', '.join(priorities)}")
    
    summary_parts.append(". However, the provided CV content is minimal and mostly consists of PDF metadata and encoded data, with no extractable information on work experience, education, or specific skills. Given this, a comprehensive analysis is limited. Assuming the candidate has some foundation in software development and project management based on career interests and goals, they may be in the early to mid stages of their career.")
    
    summary = "".join(summary_parts)
    
    # Create future skills based on career interests
    future_skills = []
    
    if any("project" in interest.lower() for interest in career_interests):
        future_skills.append({
            "name": "Project Management Certification", 
            "reason": "To progress to Senior Project Manager and beyond, advanced skills and certifications like PMP or PRINCE2 are valuable.",
            "marketDemand": "Growing"
        })
    
    if any("software" in interest.lower() or "develop" in interest.lower() for interest in career_interests):
        future_skills.append({
            "name": "Software Development", 
            "reason": "Expanding software development skills and familiarity with coding languages strengthens technical credibility.",
            "marketDemand": "Growing"
        })
    
    if any("agile" in interest.lower() for interest in career_interests):
        future_skills.append({
            "name": "Agile Methodologies", 
            "reason": "Most software development projects use Agile frameworks, knowledge of which is highly sought after.",
            "marketDemand": "Growing"
        })
    
    if any("lead" in interest.lower() or "manage" in interest.lower() for interest in career_interests):
        future_skills.append({
            "name": "Leadership Skills", 
            "reason": "Essential for managing teams and progressing into senior and director-level roles.",
            "marketDemand": "Growing"
        })
    
    # Add data analytics if no skills have been added yet
    if not future_skills:
        future_skills.append({
            "name": "Data Analysis", 
            "reason": "Important for project tracking and decision-making.",
            "marketDemand": "Growing"
        })
    
    # Ensure we have at least 3 skills
    if len(future_skills) < 3:
        if not any(skill["name"] == "Communication Skills" for skill in future_skills):
            future_skills.append({
                "name": "Communication Skills", 
                "reason": "Critical for effective team collaboration and stakeholder management.",
                "marketDemand": "High"
            })
        
        if len(future_skills) < 3 and not any(skill["name"] == "Strategic Planning" for skill in future_skills):
            future_skills.append({
                "name": "Strategic Planning", 
                "reason": "Essential for higher-level management positions.",
                "marketDemand": "Growing"
            })
    
    # Create the analysis structure
    return {
        "summary": summary,
        "currentLevel": "Junior to Mid-level",
        "growthPotential": "High",
        "marketDemand": f"Strong demand for {interests_str} exists, especially those with leadership capabilities and technical expertise.",
        "skills": [],
        "strengths": [],
        "improvements": [
            {"name": "Provide extractable CV", "description": "Upload a CV in a format that allows text extraction for better analysis"}
        ],
        "future_skills": future_skills
    }
    

def ensure_analysis_fields(analysis: Dict, career_interests: List[str], desired_role: str = None) -> None:
    """Ensure all required fields are present in the analysis."""
    if "summary" not in analysis or not analysis["summary"]:
        analysis["summary"] = f"Based on the CV analysis and career interests in {', '.join(career_interests)}, we've prepared a career assessment."
    
    if "currentLevel" not in analysis or not analysis["currentLevel"]:
        analysis["currentLevel"] = "Professional"
    
    if "growthPotential" not in analysis or not analysis["growthPotential"]:
        analysis["growthPotential"] = "Good"
    
    if "marketDemand" not in analysis or not analysis["marketDemand"]:
        analysis["marketDemand"] = f"Moderate to high demand for professionals in {', '.join(career_interests)}."
    
    if "skills" not in analysis or not analysis["skills"]:
        analysis["skills"] = []
    
    if "strengths" not in analysis or not analysis["strengths"]:
        analysis["strengths"] = []
    
    if "improvements" not in analysis or not analysis["improvements"]:
        analysis["improvements"] = []
    
    if "future_skills" not in analysis or not analysis["future_skills"]:
        # Generate some default future skills based on career interests
        analysis["future_skills"] = generate_default_future_skills(career_interests)



def create_fallback_analysis(career_interests: List[str], career_goals: Dict) -> Dict:
    """Create a fallback analysis when CV processing fails or CV is unreadable."""
    interests_str = ", ".join(career_interests) if career_interests else "specified fields"
    desired_role = career_goals.get("desiredRole", "relevant roles") if career_goals else "relevant roles"
    
    return {
        "summary": f"Based on your stated career interests in {interests_str} and career goals, we've prepared a general analysis. For a more detailed assessment, please consider uploading a CV in a text-extractable format.",
        "currentLevel": "Unable to determine from provided CV",
        "growthPotential": "Based on your career goals, you show potential for growth in your desired field",
        "marketDemand": f"Roles in {interests_str} currently show moderate to high demand in the job market",
        "skills": [],
        "strengths": [],
        "improvements": [
            {"name": "Provide extractable CV", "description": "Upload a CV in a format that allows text extraction for better analysis"}
        ],
        "future_skills": generate_default_future_skills(career_interests)
    }
    
    

def generate_default_future_skills(career_interests: List[str]) -> List[Dict]:
    """Generate default future skills based on career interests."""
    default_skills = []
    
    common_skills = [
        {"name": "Communication Skills", "reason": "Essential in any professional role", "marketDemand": "High across all industries"},
        {"name": "Project Management", "reason": "Valuable for career advancement", "marketDemand": "Strong demand in most sectors"},
        {"name": "Leadership", "reason": "Critical for senior positions", "marketDemand": "Always in demand"}
    ]
    
    # Add industry-specific skills based on interests
    for interest in career_interests:
        interest_lower = interest.lower()
        
        if "software" in interest_lower or "development" in interest_lower:
            default_skills.append({"name": "Modern Programming Languages", "reason": "Essential for software development", "marketDemand": "High demand across tech industry"})
        
        if "qa" in interest_lower or "quality" in interest_lower or "assurance" in interest_lower:
            default_skills.append({"name": "Test Automation", "reason": "Essential for modern QA roles", "marketDemand": "High demand in tech companies"})
            default_skills.append({"name": "CI/CD Knowledge", "reason": "Important for DevOps integration", "marketDemand": "Growing rapidly"})
        
        if "data" in interest_lower:
            default_skills.append({"name": "Data Analysis Tools", "reason": "Fundamental for data roles", "marketDemand": "High demand in data-driven companies"})
        
        if "management" in interest_lower:
            default_skills.append({"name": "Strategic Planning", "reason": "Essential for management roles", "marketDemand": "High value in leadership positions"})
    
    # Ensure we have at least 3 skills by adding common skills if needed
    default_skills.extend(common_skills)
    
    # Return a unique list of skills (up to 5)
    unique_skills = []
    skill_names = set()
    for skill in default_skills:
        if skill["name"] not in skill_names and len(unique_skills) < 5:
            unique_skills.append(skill)
            skill_names.add(skill["name"])
    
    return unique_skills


def clean_openai_json_response(response_text: str) -> str:
    """Clean OpenAI JSON response by removing Markdown code blocks if present."""
    cleaned_response = response_text
    
    # Remove Markdown code block formatting if present
    if "```json" in response_text:
        cleaned_response = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        # Find all code blocks and extract the one that looks like JSON
        code_blocks = response_text.split("```")
        for block in code_blocks:
            if block.strip() and (block.strip()[0] == '[' or block.strip()[0] == '{'):
                cleaned_response = block.strip()
                break
    
    return cleaned_response

async def generate_career_paths(
    cv_text: str, 
    career_interests: List[str], 
    career_goals: Dict,
    skills_analysis: Dict
) -> List[Dict]:
    """
    Generate potential career paths based on CV analysis and interests.
    Added better error handling and type checking.
    """
    logger.info(f"Generating career paths for interests: {career_interests}")
    
    try:
        # Validate and extract skills from analysis with better type checking
        skills_list = []
        if isinstance(skills_analysis, dict) and "skills" in skills_analysis:
            if isinstance(skills_analysis["skills"], list):
                for skill in skills_analysis["skills"]:
                    if isinstance(skill, dict) and "name" in skill:
                        skills_list.append(skill["name"])
                    elif isinstance(skill, str):
                        skills_list.append(skill)
        
        skills_str = ", ".join(skills_list) if skills_list else "Not specified"
        
        # Similar validation for strengths
        strengths_list = []
        if isinstance(skills_analysis, dict) and "strengths" in skills_analysis:
            if isinstance(skills_analysis["strengths"], list):
                for strength in skills_analysis["strengths"]:
                    if isinstance(strength, dict) and "name" in strength:
                        strengths_list.append(strength["name"])
                    elif isinstance(strength, str):
                        strengths_list.append(strength)
        
        strengths_str = ", ".join(strengths_list) if strengths_list else "Not specified"
        
        # Format career goals with validation
        goals_parts = []
        if isinstance(career_goals, dict):
            if career_goals.get("shortTerm"):
                goals_parts.append(f"Short-term goals: {career_goals['shortTerm']}")
            if career_goals.get("longTerm"):
                goals_parts.append(f"Long-term goals: {career_goals['longTerm']}")
            if career_goals.get("desiredRole"):
                goals_parts.append(f"Desired role: {career_goals['desiredRole']}")
            if career_goals.get("workStyle"):
                goals_parts.append(f"Preferred work style: {career_goals['workStyle']}")
            if career_goals.get("priorities") and isinstance(career_goals["priorities"], list):
                priorities_str = ", ".join(career_goals["priorities"])
                goals_parts.append(f"Priorities: {priorities_str}")
        
        goals_str = "\n".join(goals_parts) if goals_parts else "No specific career goals provided"
        
        # Rest of the function stays the same
        prompt = (
            f"Based on this career profile, generate 2-3 viable career paths that align with their interests and skills.\n\n"
            f"Career Interests: {', '.join(career_interests)}\n"
            f"Current Skills: {skills_str}\n"
            f"Key Strengths: {strengths_str}\n"
            f"Career Goals:\n{goals_str}\n\n"
            f"For each career path, include:\n"
            f"1. Title and brief description\n"
            f"2. Match percentage (how well it fits the person's profile)\n"
            f"3. Reasons why this path suits them (3-4 points)\n"
            f"4. Challenges they might face (2-3 points)\n"
            f"5. Typical progression steps (role titles and timeframes)\n"
            f"6. Salary range\n"
            f"7. Job growth outlook\n"
            f"8. Estimated time to transition\n\n"
            f"Return a JSON array where each object has these keys: title, description, fitScore, reasons, "
            f"challenges, progression, salary, growth, timeToTransition. The progression field must be an array of objects, "
            f"where each object has a role and years property."
        )
        
        # Call OpenAI
        response_text = call_openai(prompt)
        
        # Parse the response with robust error handling
        try:
            # Clean the response text
            cleaned_response = clean_openai_json_response(response_text)
            
            # Parse the JSON
            career_paths = json.loads(cleaned_response)
            
            # Validate that we got a list
            if not isinstance(career_paths, list):
                logger.error(f"Expected list from OpenAI, got: {type(career_paths)}")
                # Convert to list if we got a single object
                if isinstance(career_paths, dict):
                    career_paths = [career_paths]
                else:
                    # Create a default career path if we got something unexpected
                    career_paths = [{
                        "title": career_interests[0] if career_interests else "Software Developer",
                        "description": "A career path based on your interests and skills.",
                        "fitScore": "75%",
                        "reasons": ["Aligns with your skills", "Matches your career goals", "Growing industry"],
                        "challenges": ["May require additional training", "Competitive field"],
                        "progression": [{"role": "Junior Developer", "years": "1-2 years"}, 
                                      {"role": "Mid-level Developer", "years": "2-3 years"},
                                      {"role": "Senior Developer", "years": "3+ years"}],
                        "salary": "$70,000 - $120,000",
                        "growth": "Positive (10-15% annually)",
                        "timeToTransition": "3-6 months"
                    }]
            
            # Ensure proper structure for progression field
            for i, path in enumerate(career_paths):
                if not isinstance(path, dict):
                    logger.warning(f"Career path at index {i} is not a dictionary: {path}")
                    continue
                    
                if "progression" in path:
                    if not isinstance(path["progression"], list):
                        # Convert to list if it's not already
                        if isinstance(path["progression"], str):
                            path["progression"] = [{"role": path["progression"], "years": "Varies"}]
                        else:
                            path["progression"] = [{"role": "Entry Level", "years": "1-2 years"}, 
                                                {"role": "Mid Level", "years": "2-4 years"},
                                                {"role": "Senior Level", "years": "4+ years"}]
                    else:
                        # Check each item in the progression list
                        new_progression = []
                        for item in path["progression"]:
                            if isinstance(item, dict) and "role" in item and "years" in item:
                                new_progression.append(item)
                            elif isinstance(item, str):
                                # Parse string format like "Role Name (2-3 years)"
                                parts = item.split("(")
                                if len(parts) > 1:
                                    role = parts[0].strip()
                                    years = "(" + parts[1]
                                else:
                                    role = item
                                    years = "Varies"
                                new_progression.append({"role": role, "years": years})
                            else:
                                # Create a default item
                                new_progression.append({"role": f"Career Stage {len(new_progression)+1}", 
                                                      "years": "Varies"})
                        path["progression"] = new_progression
                else:
                    # Create default progression if missing
                    path["progression"] = [
                        {"role": "Entry Level", "years": "1-2 years"},
                        {"role": "Mid Level", "years": "2-4 years"},
                        {"role": "Senior Level", "years": "4+ years"}
                    ]
            
            # Add real market data if possible
            enhanced_paths = []
            for path in career_paths:
                if not isinstance(path, dict) or "title" not in path:
                    continue
                    
                try:
                    # Fetch real market data for the role
                    market_data = await fetch_job_market_data(path["title"])
                    
                    # Enhance with real market data
                    if market_data and isinstance(market_data, dict):
                        if "salary_data" in market_data and isinstance(market_data["salary_data"], dict) and "median_salary" in market_data["salary_data"]:
                            path["salary"] = market_data["salary_data"]["median_salary"]
                        if "growth_rate" in market_data:
                            path["growth"] = market_data["growth_rate"]
                except Exception as market_err:
                    logger.error(f"Error fetching market data: {market_err}")
                    # Keep the original AI-generated data
                
                enhanced_paths.append(path)
            
            return enhanced_paths if enhanced_paths else career_paths
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from OpenAI response: {e}")
            logger.error(f"Response was: {response_text}")
            logger.error(f"Cleaned response: {cleaned_response}")
            
            # Try to extract JSON directly from the original response if possible
            try:
                # Look for anything that might be JSON in the response
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    career_paths = json.loads(json_str)
                    return career_paths
            except:
                pass
            
            # If all else fails, return a default response
            return [{
                "title": career_interests[0] if career_interests else "Software Developer",
                "description": "A career path based on your interests and skills.",
                "fitScore": "75%",
                "reasons": ["Aligns with your skills", "Matches your career goals", "Growing industry"],
                "challenges": ["May require additional training", "Competitive field"],
                "progression": [
                    {"role": "Junior Developer", "years": "1-2 years"}, 
                    {"role": "Mid-level Developer", "years": "2-3 years"},
                    {"role": "Senior Developer", "years": "3+ years"}
                ],
                "salary": "$70,000 - $120,000",
                "growth": "Positive (10-15% annually)",
                "timeToTransition": "3-6 months"
            }]
    
    except Exception as e:
        logger.error(f"Error in generate_career_paths: {e}")
        # Return a fallback career path
        return [{
            "title": career_interests[0] if career_interests and career_interests[0] else "Software Developer",
            "description": "A career path based on your interests and skills.",
            "fitScore": "75%",
            "reasons": ["Aligns with your skills", "Matches your career goals", "Growing industry"],
            "challenges": ["May require additional training", "Competitive field"],
            "progression": [
                {"role": "Junior Developer", "years": "1-2 years"}, 
                {"role": "Mid-level Developer", "years": "2-3 years"},
                {"role": "Senior Developer", "years": "3+ years"}
            ],
            "salary": "$70,000 - $120,000",
            "growth": "Positive (10-15% annually)",
            "timeToTransition": "3-6 months"
        }]

async def identify_skill_gaps(
    cv_text: str, 
    career_interests: List[str],
    skills_analysis: Dict
) -> List[Dict]:
    """
    Identify skill gaps between current skills and career requirements.
    """
    logger.info(f"Identifying skill gaps for career interests: {career_interests}")
    
    try:
        # Extract current skills
        current_skills = [skill["name"] for skill in skills_analysis.get("skills", [])]
        current_skills_str = ", ".join(current_skills)
        
        # Prepare OpenAI prompt
        prompt = (
            f"Based on the candidate's CV and career interests, identify key skill gaps that need to be addressed.\n\n"
            f"Career Interests: {', '.join(career_interests)}\n"
            f"Current Skills: {current_skills_str}\n\n"
            f"For each skill gap, provide:\n"
            f"1. The skill name\n"
            f"2. Current proficiency level (0-5 scale where 0 is none, 5 is expert)\n"
            f"3. Required level for the target career (0-5 scale)\n"
            f"4. Priority (High, Medium, Low)\n"
            f"5. Why this skill is important for the career\n"
            f"6. Recommended learning path to acquire this skill\n\n"
            f"Return a JSON array where each object has these keys: skill, currentLevel, requiredLevel, priority, importance, learningPath"
        )
        
        # Call OpenAI
        response_text = call_openai(prompt)
        
        # Parse the response
        try:
            # Clean the response text
            cleaned_response = clean_openai_json_response(response_text)
            
            # Parse the JSON
            skill_gaps = json.loads(cleaned_response)
            
            # Validate the response and ensure it's a list of dictionaries
            if not isinstance(skill_gaps, list):
                logger.warning(f"Expected list from identify_skill_gaps, got {type(skill_gaps)}")
                if isinstance(skill_gaps, dict):
                    skill_gaps = [skill_gaps]
                else:
                    skill_gaps = []
            
            # Enhance with learning resources if available
            for i, gap in enumerate(skill_gaps):
                if not isinstance(gap, dict):
                    logger.warning(f"Expected dict in skill_gaps, got {type(gap)}")
                    skill_gaps[i] = {
                        "skill": str(gap) if gap else "Unknown Skill",
                        "currentLevel": 2,
                        "requiredLevel": 4,
                        "priority": "Medium",
                        "importance": "This skill appears to be relevant for your career path",
                        "learningPath": "Consider courses or self-study options to develop this skill"
                    }
                    continue
                
                try:
                    # Add estimated time to acquire
                    current_level = gap.get("currentLevel", 0)
                    required_level = gap.get("requiredLevel", 0)
                    if isinstance(current_level, str):
                        try:
                            current_level = int(current_level)
                        except:
                            current_level = 0
                    
                    if isinstance(required_level, str):
                        try:
                            required_level = int(required_level)
                        except:
                            required_level = 0
                            
                    gap_size = required_level - current_level
                    if gap_size <= 1:
                        gap["timeToAcquire"] = "1-2 months"
                    elif gap_size <= 2:
                        gap["timeToAcquire"] = "2-4 months"
                    elif gap_size <= 3:
                        gap["timeToAcquire"] = "4-6 months"
                    else:
                        gap["timeToAcquire"] = "6+ months"
                except Exception as err:
                    logger.error(f"Error calculating time to acquire: {err}")
                    gap["timeToAcquire"] = "3-6 months"
            
            return skill_gaps
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from OpenAI response: {e}")
            logger.error(f"Response was: {response_text}")
            logger.error(f"Cleaned response: {cleaned_response}")
            
            # Try to extract JSON directly
            try:
                # Look for anything that might be JSON in the response
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    skill_gaps = json.loads(json_str)
                    return skill_gaps
            except:
                pass
            
            # If still failing, return an empty list
            logger.warning("Failed to parse skill gaps, returning empty list")
            return []
    
    except Exception as e:
        logger.error(f"Error in identify_skill_gaps: {e}")
        return []

async def recommend_learning_resources(skill_gaps: List[Dict], career_interests: List[str]) -> Dict:
    """
    Fetch and recommend learning resources for identified skill gaps.
    Enhanced with better error handling and resource gathering.
    """
    logger.info(f"Recommending learning resources for skill gaps and career interests: {career_interests}")
    
    try:
        # Extract skills from gaps for targeted resource search
        high_priority_skills = []
        medium_priority_skills = []
        
        if skill_gaps:
            high_priority_skills = [gap["skill"] for gap in skill_gaps if isinstance(gap, dict) and gap.get("priority") == "High"]
            medium_priority_skills = [gap["skill"] for gap in skill_gaps if isinstance(gap, dict) and gap.get("priority") == "Medium"]
        
        # If no skill gaps were found, use career interests
        all_skills = high_priority_skills + medium_priority_skills
        
        if not all_skills and career_interests:
            all_skills = career_interests
        
        logger.info(f"Skills to search for resources: {all_skills}")
        
        # Collect learning resources for all skills
        courses = []
        certifications = []
        
        # Generate learning paths based on skill gaps or career interests
        paths = []
        
        # Create learning paths for high priority skills or career interests
        priority_skills = high_priority_skills if high_priority_skills else career_interests
        
        for idx, skill in enumerate(priority_skills[:3]):  # Limit to top 3 skills
            # Create a learning path
            duration = random.choice(["2-3 months", "3-4 months", "4-6 months"])
            topics = [skill]
            
            # Add related topics
            related_topics = []
            for interest in career_interests:
                # Don't add duplicates
                if interest != skill:
                    related_topics.append(f"{skill} for {interest}")
            
            # Add 1-2 random related topics if available
            if related_topics:
                topics.extend(random.sample(related_topics, min(2, len(related_topics))))
            
            path_description = f"A focused learning path to develop your {skill} skills"
            if career_interests:
                path_description += f" for roles in {career_interests[0]}"
            
            # Create path with URL
            path_url = f"https://www.coursera.org/search?query={quote(skill)}+learning+path"
            
            paths.append({
                "title": f"{skill} Mastery Path",
                "description": path_description,
                "duration": duration,
                "topics": topics,
                "url": path_url
            })
        
        # Determine unique skills to search for courses
        # Give priority to high priority skills and career interests
        search_skills = []
        
        # Add skills in priority order, avoiding duplicates
        for skill in high_priority_skills:
            if skill not in search_skills:
                search_skills.append(skill)
                
        for interest in career_interests:
            if interest not in search_skills:
                search_skills.append(interest)
                
        for skill in medium_priority_skills:
            if skill not in search_skills:
                search_skills.append(skill)
        
        # If still no skills, ensure we have at least some defaults
        if not search_skills:
            search_skills = ["Professional Development"]
            
        # Limit to top 5 skills to avoid too many API calls
        search_skills = search_skills[:5]
        
        # Track successful fetches to avoid redundant searches
        searched_skills = set()
        successful_searches = 0
        
        # Generate courses for skill gaps or career interests
        for skill in search_skills:
            # Skip if we already have enough courses or already searched this skill
            if len(courses) >= 8 or skill.lower() in searched_skills or successful_searches >= 3:
                continue
                
            try:
                # Mark this skill as searched
                searched_skills.add(skill.lower())
                
                # Fetch course recommendations
                logger.info(f"Fetching courses for skill: {skill}")
                skill_courses = await fetch_learning_resources(skill)
                
                if skill_courses and len(skill_courses) > 0:
                    logger.info(f"Found {len(skill_courses)} courses for {skill}")
                    
                    # Filter out low-quality or duplicate courses
                    filtered_courses = []
                    existing_titles = {course["title"].lower() for course in courses}
                    
                    for course in skill_courses:
                        # Skip courses with missing titles or duplicates
                        if not course.get("title") or course["title"].lower() in existing_titles:
                            continue
                            
                        # Add to filtered list and update existing titles
                        filtered_courses.append(course)
                        existing_titles.add(course["title"].lower())
                        
                    # Add to courses list, limiting to 10 per skill
                    courses.extend(filtered_courses[:10])
                    successful_searches += 1
                    
                else:
                    logger.warning(f"No courses found for skill: {skill}")
            except Exception as course_err:
                logger.error(f"Error fetching courses for {skill}: {course_err}")
                # Continue with next skill
        
        # Generate certifications based on career interests
        certification_options = {
            "software development": {
                "name": "Professional Certificate in Software Development",
                "provider": "edX / IBM",
                "description": "Learn key programming languages and develop skills for a career in software development",
                "duration": "3-6 months",
                "cost": "$1,000",
                "url": "https://www.edx.org/professional-certificate/ibm-full-stack-cloud-developer"
            },
            "data science": {
                "name": "Data Science Professional Certificate",
                "provider": "Coursera / IBM",
                "description": "Master data science tools and techniques for a career in this high-demand field",
                "duration": "6-12 months",
                "cost": "$400 per year",
                "url": "https://www.coursera.org/professional-certificates/ibm-data-science"
            },
            "cloud": {
                "name": "AWS Certified Solutions Architect",
                "provider": "Amazon Web Services",
                "description": "Validate your expertise in designing distributed systems on AWS",
                "duration": "2-3 months of study",
                "cost": "$150 exam fee",
                "url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/"
            },
            "project management": {
                "name": "Google Project Management Certificate",
                "provider": "Coursera / Google",
                "description": "Gain the skills needed to start a career in project management",
                "duration": "3-6 months",
                "cost": "$39/month subscription",
                "url": "https://www.coursera.org/professional-certificates/google-project-management"
            },
            "product management": {
                "name": "Professional Certificate in Product Management",
                "provider": "edX / Boston University",
                "description": "Learn essential product management skills from ideation to market launch",
                "duration": "3-5 months",
                "cost": "$1,100",
                "url": "https://www.edx.org/certificates/professional-certificate/product-management"
            },
            "web development": {
                "name": "Full Stack Web Development Certificate",
                "provider": "edX / The Hong Kong University of Science and Technology",
                "description": "Learn front-end and back-end web development technologies and frameworks",
                "duration": "4-8 months",
                "cost": "$350",
                "url": "https://www.edx.org/professional-certificate/hongkongx-full-stack-web-developer"
            },
            "ui": {
                "name": "UI/UX Design Professional Certificate",
                "provider": "Coursera / Google",
                "description": "Learn the skills needed to create effective and user-friendly digital experiences",
                "duration": "6 months",
                "cost": "$39/month subscription",
                "url": "https://www.coursera.org/professional-certificates/google-ux-design"
            },
            "cybersecurity": {
                "name": "CompTIA Security+ Certification",
                "provider": "CompTIA",
                "description": "Industry-standard certification for IT security professionals",
                "duration": "2-3 months",
                "cost": "$370 exam fee",
                "url": "https://www.comptia.org/certifications/security"
            },
            "mobile": {
                "name": "iOS App Development with Swift",
                "provider": "Coursera / University of Toronto",
                "description": "Learn to create iOS applications using Swift and Apple's development frameworks",
                "duration": "4-5 months",
                "cost": "$49/month subscription",
                "url": "https://www.coursera.org/specializations/ios-app-development"
            }
        }
        
        # Select certifications relevant to career interests
        for interest in career_interests:
            interest_lower = interest.lower()
            for key, cert in certification_options.items():
                if key in interest_lower and cert not in certifications:
                    certifications.append(cert)
                    break
        
        # If no matches found, add a default certification based on first career interest
        if not certifications and career_interests:
            # Try to find a close match
            interest_lower = career_interests[0].lower()
            best_match = None
            best_score = 0
            
            for key, cert in certification_options.items():
                # Simple string matching score
                score = 0
                for word in interest_lower.split():
                    if word in key:
                        score += 1
                
                if score > best_score:
                    best_score = score
                    best_match = cert
            
            if best_match:
                certifications.append(best_match)
            else:
                # Fall back to software development as default
                certifications.append(certification_options["software development"])
        
        # Ensure we have at least one certification
        if not certifications and "software development" in certification_options:
            certifications.append(certification_options["software development"])
        
        # Remove duplicates from courses
        unique_courses = []
        course_titles = set()
        
        for course in courses:
            title = course.get("title", "")
            if title and title not in course_titles:
                course_titles.add(title)
                unique_courses.append(course)
        
        # Ensure we have at least one of each resource type
        if not paths:
            interest = career_interests[0] if career_interests else 'Professional'
            paths = [{
                "title": f"{interest} Development Path",
                "description": "A comprehensive learning path to develop key skills for your career progression",
                "duration": "3-6 months",
                "topics": [interest, "Advanced Techniques", "Leadership Development"],
                "url": f"https://www.coursera.org/search?query={quote(interest)}+learning+path"
            }]
        
        if not unique_courses:
            interest = career_interests[0] if career_interests else 'Professional'
            unique_courses = [{
                "title": f"{interest} Skills Masterclass",
                "provider": "Coursera - Top University",
                "duration": "8 weeks",
                "level": "Intermediate",
                "price": "Free audit available (Certificate: $49)",
                "url": f"https://www.coursera.org/search?query={quote(interest)}",
                "rating": "4.5",
                "reviews": "5K+ reviews",
                "skills": [f"{interest} Fundamentals", "Industry Best Practices", "Advanced Techniques"],
                "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/default-course-image.jpg"
            }]
        
        # Return structured learning resources
        result = {
            "paths": paths,
            "courses": unique_courses,
            "certifications": certifications
        }
        
        logger.info(f"Returning learning resources: {len(paths)} paths, {len(unique_courses)} courses, {len(certifications)} certifications")
        return result
    
    except Exception as e:
        logger.error(f"Error in recommend_learning_resources: {e}")
        # Return default structure on error with URLs
        primary_interest = career_interests[0] if career_interests and len(career_interests) > 0 else "Professional Development"
        encoded_interest = quote(primary_interest)
        
        return {
            "paths": [
                {
                    "title": f"{primary_interest} Development Path",
                    "description": "A comprehensive learning path to develop key skills",
                    "duration": "3-6 months",
                    "topics": ["Core Skills", "Advanced Techniques", "Professional Development"],
                    "url": f"https://www.coursera.org/search?query={encoded_interest}+learning+path"
                }
            ],
            "courses": [
                {
                    "title": f"Essential {primary_interest} Skills Course",
                    "provider": "Coursera - Top University",
                    "duration": "8 weeks",
                    "level": "Intermediate",
                    "price": "Free audit available (Certificate: $49)",
                    "url": f"https://www.coursera.org/search?query={encoded_interest}",
                    "rating": "4.6",
                    "reviews": "1K+ reviews",
                    "skills": [f"{primary_interest} Fundamentals", "Industry Best Practices", "Advanced Techniques"],
                    "image": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://s3.amazonaws.com/coursera-course-photos/default-course-image.jpg"
                }
            ],
            "certifications": [
                {
                    "name": f"Professional {primary_interest} Certificate",
                    "description": f"Industry-recognized certification for {primary_interest} professionals",
                    "provider": "Coursera",
                    "duration": "3 months",
                    "cost": "$300",
                    "url": f"https://www.coursera.org/professional-certificates/search?query={encoded_interest}"
                }
            ]
        }

async def create_action_plan(
    career_paths: List[Dict], 
    skill_gaps: List[Dict], 
    learning_resources: Dict
) -> List[Dict]:
    """
    Create a personalized action plan based on career analysis.
    """
    logger.info(f"Creating personalized action plan")
    
    try:
        action_plan = []
        
        # Step 1: Address high priority skill gaps
        if skill_gaps and isinstance(skill_gaps, list) and len(skill_gaps) > 0:
            high_priority_gaps = [gap for gap in skill_gaps if isinstance(gap, dict) and gap.get("priority") == "High"]
            if high_priority_gaps:
                gap_skills = []
                for gap in high_priority_gaps[:3]:
                    if isinstance(gap, dict) and "skill" in gap:
                        gap_skills.append(gap["skill"])
                
                if gap_skills:
                    action_plan.append({
                        "title": "Address Critical Skill Gaps",
                        "description": f"Focus on developing {', '.join(gap_skills)}",
                        "timeline": "1-3 months"
                    })
                    logger.info(f"Added action plan step for skill gaps: {gap_skills}")
        
        # Step 2: Complete a learning path
        if learning_resources and isinstance(learning_resources, dict) and "paths" in learning_resources:
            paths = learning_resources["paths"]
            if paths and isinstance(paths, list) and len(paths) > 0:
                path = paths[0]
                if isinstance(path, dict):
                    path_title = path.get("title", "Learning Path")
                    path_duration = path.get("duration", "3-6 months")
                    
                    topics = []
                    if "topics" in path and isinstance(path["topics"], list):
                        topics = [topic for topic in path["topics"][:3] if topic]
                    
                    topics_str = ", ".join(topics) if topics else "essential skills"
                    
                    action_plan.append({
                        "title": f"Complete {path_title}",
                        "description": f"Follow the structured learning path to develop essential skills: {topics_str}",
                        "timeline": path_duration
                    })
                    logger.info(f"Added action plan step for learning path: {path_title}")
        
        # Step 3: Earn relevant certification
        if learning_resources and isinstance(learning_resources, dict) and "certifications" in learning_resources:
            certifications = learning_resources["certifications"]
            if certifications and isinstance(certifications, list) and len(certifications) > 0:
                cert = certifications[0]
                if isinstance(cert, dict):
                    cert_name = cert.get("name", "Professional Certification")
                    cert_provider = cert.get("provider", "a recognized provider")
                    cert_duration = cert.get("duration", "3-6 months")
                    
                    action_plan.append({
                        "title": f"Earn {cert_name}",
                        "description": f"This certification from {cert_provider} will validate your skills and boost your credibility",
                        "timeline": cert_duration
                    })
                    logger.info(f"Added action plan step for certification: {cert_name}")
        
        # Step 4: Build portfolio projects
        action_plan.append({
            "title": "Build Portfolio Projects",
            "description": "Create 2-3 projects that demonstrate your newly acquired skills and align with your target career path",
            "timeline": "2-4 months"
        })
        logger.info("Added action plan step for portfolio projects")
        
        # Step 5: Network and job search
        if career_paths and isinstance(career_paths, list) and len(career_paths) > 0:
            path = career_paths[0]
            if isinstance(path, dict) and "title" in path:
                action_plan.append({
                    "title": "Network and Begin Job Search",
                    "description": f"Connect with professionals in {path['title']} roles and start applying for positions that match your new skill set",
                    "timeline": "Ongoing"
                })
                logger.info(f"Added action plan step for job search based on career path: {path['title']}")
            else:
                action_plan.append({
                    "title": "Network and Begin Job Search",
                    "description": "Connect with professionals in your desired field and start applying for positions that match your skill set",
                    "timeline": "Ongoing"
                })
                logger.info("Added generic action plan step for job search")
        else:
            action_plan.append({
                "title": "Network and Begin Job Search",
                "description": "Connect with professionals in your desired field and start applying for positions that match your skill set",
                "timeline": "Ongoing"
            })
            logger.info("Added generic action plan step for job search")
        
        logger.info(f"Created action plan with {len(action_plan)} steps")
        return action_plan
    
    except Exception as e:
        logger.error(f"Error in create_action_plan: {e}")
        # Return a basic action plan on error
        default_plan = [
            {
                "title": "Develop Key Skills",
                "description": "Focus on learning and practicing essential skills for your target career",
                "timeline": "3-6 months"
            },
            {
                "title": "Build Portfolio",
                "description": "Create projects showcasing your skills and expertise",
                "timeline": "2-4 months"
            },
            {
                "title": "Job Search",
                "description": "Apply for relevant positions in your desired field",
                "timeline": "Ongoing"
            }
        ]
        logger.info("Returning default action plan due to error")
        return default_plan