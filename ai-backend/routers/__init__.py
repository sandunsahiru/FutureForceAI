from fastapi import APIRouter
from .interviewprep import router as interview_router
from .cv_model import router as cv_router
from .job_description import router as job_description_router
from .career_guidance import router as career_guidance_router
from .resume_analyzer import router as resume_analyzer_router
from .saved_cv_route import router as saved_cv_router
from .job_search import router as job_search_router

api_router = APIRouter()

# Include all routers with appropriate prefixes
api_router.include_router(interview_router, prefix="/api/interview", tags=["interview"])
api_router.include_router(cv_router, prefix="/api/user", tags=["cv"])
api_router.include_router(resume_analyzer_router, prefix="/api/resume", tags=["resume"])
api_router.include_router(job_description_router, prefix="/api/job-description", tags=["job-description"])
api_router.include_router(career_guidance_router, prefix="/api/career-guidance", tags=["career-guidance"])
api_router.include_router(saved_cv_router, prefix="/api/cv", tags=["saved-cv"])
api_router.include_router(job_search_router, prefix="/api/jobs", tags=["job-search"])