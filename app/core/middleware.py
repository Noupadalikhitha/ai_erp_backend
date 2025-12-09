"""
Middleware for request logging and tracking
"""
import uuid
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests for log correlation"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Start time tracking
        start_time = time.time()
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            # Log request (only for non-health/root endpoints to reduce noise)
            path = request.url.path
            if path not in ["/", "/health", "/health/detailed", "/docs", "/openapi.json", "/redoc"]:
                # Create a logger adapter with request_id
                request_logger = logging.LoggerAdapter(
                    logger,
                    {"request_id": request_id}
                )
                
                status_code = response.status_code
                method = request.method
                
                # Log level based on status code
                if status_code >= 500:
                    log_level = "error"
                elif status_code >= 400:
                    log_level = "warning"
                else:
                    log_level = "info"
                
                getattr(request_logger, log_level)(
                    f"{method} {path} - {status_code} - {duration:.3f}s"
                )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            request_logger = logging.LoggerAdapter(
                logger,
                {"request_id": request_id}
            )
            request_logger.error(
                f"{request.method} {request.url.path} - Exception - {duration:.3f}s",
                exc_info=True
            )
            raise

