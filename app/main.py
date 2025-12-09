from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.v1 import api_router

app = FastAPI(
    title="AI-Powered ERP System",
    description="Full-stack ERP with AI capabilities",
    version="1.0.0"
)

# CORS middleware - Allow all origins in development
# TODO: Restrict to specific origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://frontend-likhitha.vercel.app",
        "http://localhost:5173"
    ],
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],   # Allow all headers
    expose_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "AI-Powered ERP System API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

