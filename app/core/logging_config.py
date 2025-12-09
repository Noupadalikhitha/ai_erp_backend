"""
Logging configuration for the application
"""
import logging
import sys
import json
from typing import Optional, Dict, Any
from datetime import datetime
from app.core.config import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request_id if present
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        
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
        # Text formatter with optional request_id
        class TextFormatter(logging.Formatter):
            def format(self, record):
                request_id = getattr(record, 'request_id', 'system')
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
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Add default request_id if not set (for non-request contexts)
    if not hasattr(logger, '_request_id_default'):
        # Create an adapter that adds default request_id
        class LoggerAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                if 'extra' not in kwargs:
                    kwargs['extra'] = {}
                if 'request_id' not in kwargs['extra']:
                    kwargs['extra']['request_id'] = 'system'
                return msg, kwargs
        
        return LoggerAdapter(logger, {})
    
    return logger

