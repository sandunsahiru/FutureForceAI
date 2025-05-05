from fastapi import APIRouter
from .interviewprep import router as interview_router
from .cv_model import router as cv_router
from .job_description import router as job_description_router

api_router = APIRouter()

# Include routers with prefixes
api_router.include_router(interview_router, prefix="/interview", tags=["interview"])
api_router.include_router(cv_router, prefix="/cv", tags=["cv"])
api_router.include_router(job_description_router, prefix="/job-description", tags=["job-description"])
