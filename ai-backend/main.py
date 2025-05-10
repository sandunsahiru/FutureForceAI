from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("futureforceai")

# Import our APIRouters
try:
    # Import interview prep router
    from routers.interviewprep import router as interviewprep_router
    logger.info("Successfully imported interviewprep router")
    
    # Import the new CV router
    from routers.cv_model import router as cv_router
    logger.info("Successfully imported CV router")
    
    # Import the new saved CV router
    from routers.saved_cv_route import router as saved_cv_router
    logger.info("Successfully imported saved CV router")
    
    # Import the job description router
    from routers.job_description import router as job_description_router
    logger.info("Successfully imported job description router")
    
    # Import the job search router
    from routers.job_search import router as job_search_router, setup_job_search_routes
    logger.info("Successfully imported job search router")
    
    # Import the career guidance router (NEW)
    from routers.career_guidance import router as career_guidance_router
    logger.info("Successfully imported career guidance router")
    
except ImportError as e:
    logger.error(f"Failed to import routers: {e}")
    # List the contents of the routers directory to debug
    try:
        routers_dir = os.path.join(os.path.dirname(__file__), "routers")
        if os.path.exists(routers_dir):
            logger.info(f"Contents of routers directory: {os.listdir(routers_dir)}")
        else:
            logger.error(f"Routers directory not found at {routers_dir}")
    except Exception as list_err:
        logger.error(f"Error listing routers directory: {list_err}")
    raise

app = FastAPI()

# Add debugging middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"Response status code: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request error: {e}")
        raise

# CORS for your Next.js front end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create __init__.py if it doesn't exist
def initialize():
    """
    Initialize the application:
    1. Create __init__.py in the routers directory if it doesn't exist
    2. Check if all required routes are properly registered
    """
    try:
        # Create __init__.py in routers directory if it doesn't exist
        routers_dir = os.path.join(os.path.dirname(__file__), "routers")
        
        if not os.path.exists(routers_dir):
            logger.warning(f"Creating routers directory: {routers_dir}")
            os.makedirs(routers_dir, exist_ok=True)
        
        init_file = os.path.join(routers_dir, "__init__.py")
        if not os.path.exists(init_file):
            logger.info(f"Creating __init__.py in routers directory: {init_file}")
            with open(init_file, "w") as f:
                f.write("# This file makes the routers directory a Python package\n")
    except Exception as e:
        logger.error(f"Error during initialization: {e}")

# Call initialize function
initialize()

# Register routers with their API path prefixes
logger.info("Registering interviewprep router with prefix: /api/interview")
app.include_router(interviewprep_router, prefix="/api/interview", tags=["InterviewPrep"])

# Changed: Update the CV router prefix to match the frontend's expected path
logger.info("Registering CV router with prefix: /api/user")
app.include_router(cv_router, prefix="/api/user", tags=["CV"])

# Register the saved CV router
# Note: We don't add a prefix here since the saved_cv_router already includes the full path
logger.info("Registering saved CV router")
app.include_router(saved_cv_router, tags=["SavedCV"])

# Register the job description router
logger.info("Registering job description router with prefix: /api/job-description")
app.include_router(job_description_router, prefix="/api/job-description", tags=["JobDescription"])

# Register the job search router
logger.info("Registering job search router with prefix: /api")
app.include_router(job_search_router, prefix="/api", tags=["JobSearch"])

# Register the career guidance router (NEW)
logger.info("Registering career guidance router with prefix: /api/career-guidance")
app.include_router(career_guidance_router, prefix="/api/career-guidance", tags=["CareerGuidance"])

# Set up additional job search routes
logger.info("Setting up job search routes")
setup_job_search_routes(app)

# Log all registered routes for debugging
for route in app.routes:
    logger.info(f"Registered route: {route.path} [{', '.join(route.methods) if hasattr(route, 'methods') else ''}]")

# Add a health check endpoint
@app.get("/")
async def root():
    logger.info("Health check endpoint called")
    return {
        "status": "healthy", 
        "message": "FutureForceAI API is running",
        "routes": [
            {"path": route.path, "methods": list(route.methods)}
            for route in app.routes
            if hasattr(route, "methods")
        ]
    }

# If you want to run directly with: python main.py
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")