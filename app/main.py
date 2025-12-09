from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.v1 import api_router
from sqlalchemy import create_engine, text
from app.core.config import settings as _settings
from app.core.security import is_valid_bcrypt_hash
from app.core.logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

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
            rows = conn.execute(text("SELECT id, email, hashed_password FROM users LIMIT 1000")).fetchall()
        malformed_users = []
        for user_id, email, h in rows:
            if not is_valid_bcrypt_hash(h):
                malformed_users.append({"id": user_id, "email": email})
        
        if malformed_users:
            logger.warning(
                f"Detected {len(malformed_users)} users with malformed bcrypt hashes "
                f"(first 1000 rows checked). "
                f"Run 'python scripts/fix_malformed_hashes.py --dry-run' for details."
            )
            # Log first few affected users for visibility
            for user in malformed_users[:5]:
                logger.debug(f"Malformed hash detected: user_id={user['id']}, email={user['email']}")
        else:
            logger.info("Password hash validation check passed - all hashes are valid")
    except Exception as e:
        # Avoid raising on startup; log error for diagnostics
        logger.warning(f"Startup hash check skipped: could not query users table - {str(e)}")

