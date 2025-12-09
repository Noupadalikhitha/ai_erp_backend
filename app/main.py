from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.v1 import api_router
from sqlalchemy import create_engine, text
from app.core.config import settings as _settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _is_valid_bcrypt(h: str | None) -> bool:
    if not isinstance(h, str):
        return False
    return h.startswith(('$2b$', '$2a$', '$2y$')) and len(h) == 60

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
    # allow_origins=["*"],  # Allow all origins for development (uncomment for broad dev CORS)
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


@app.on_event("startup")
def startup_checks():
    """Non-blocking startup check: log number of malformed bcrypt hashes.

    This check is intentionally lightweight and only logs a count so operators
    are aware if seed/migration issues exist. It does not modify the DB.
    """
    try:
        engine = create_engine(_settings.DATABASE_URL)
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT hashed_password FROM users LIMIT 1000")).fetchall()
        malformed = 0
        for (h,) in rows:
            if not _is_valid_bcrypt(h):
                malformed += 1
        if malformed:
            print(f"WARNING: detected {malformed} malformed bcrypt hashes (first 1000 rows checked)")
    except Exception:
        # Avoid raising on startup; just print a short message for diagnostics
        print("Startup hash check skipped: could not query users table")

