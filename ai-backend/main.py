from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import our APIRouter from interviewprep
from routers.interviewprep import router as interviewprep_router

app = FastAPI()

# CORS for your Next.js front end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the interviewprep router under the prefix "/api/interview"
app.include_router(interviewprep_router, prefix="/api/interview", tags=["InterviewPrep"])

# If you want to run directly with: python main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)