"""
Logging configuration for the application
"""
import logging
import sys
import json
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime
from app.core.config import settings

# Context variable to store request ID for the current request
request_id_context: ContextVar[str] = ContextVar('request_id', default='system')

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request_id from record or context
        request_id = getattr(record, 'request_id', None)
        if request_id is None:
            request_id = request_id_context.get('system')
        log_data["request_id"] = request_id
        
        # Add user info if present
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'user_email'):
            log_data["user_email"] = record.user_email
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName',
                          'relativeCreated', 'thread', 'threadName', 'exc_info',
                          'exc_text', 'stack_info', 'request_id', 'user_id', 'user_email']:
                log_data[key] = value
        
        return json.dumps(log_data)

def setup_logging(log_level: Optional[str] = None, log_format: Optional[str] = None) -> None:
    """
    Configure application-wide logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format ("text" or "json")
    """
    # Get settings from config
    level = log_level or settings.LOG_LEVEL
    fmt = log_format or settings.LOG_FORMAT
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Choose formatter
    if fmt.lower() == "json":
        formatter = JSONFormatter()
        log_format_str = None  # JSON formatter handles format
    else:
        # Text formatter with optional request_id from context
        class TextFormatter(logging.Formatter):
            def format(self, record):
                # Try to get request_id from record, then from context, then default
                request_id = getattr(record, 'request_id', None)
                if request_id is None:
                    request_id = request_id_context.get('system')
                record.request_id = request_id
                return super().format(record)
        
        formatter = TextFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Suppress passlib bcrypt version warning (it's harmless)
    logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    Automatically includes request_id from context if available.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance with request_id context support
    """
    logger = logging.getLogger(name)
    
    # Create an adapter that adds request_id from context
    class ContextLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            # Get request_id from context if not explicitly provided
            if 'request_id' not in kwargs['extra']:
                kwargs['extra']['request_id'] = request_id_context.get('system')
            return msg, kwargs
    
    return ContextLoggerAdapter(logger, {})

