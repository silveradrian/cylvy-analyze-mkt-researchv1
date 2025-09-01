"""
Logging configuration
"""
import sys
from loguru import logger
from app.core.config import settings


def setup_logging():
    """Configure application logging"""
    # Remove default logger
    logger.remove()
    
    # Console logging
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )
    
    # File logging for production
    if settings.ENVIRONMENT == "production":
        logger.add(
            "/var/log/cylvy/app.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="INFO",
            rotation="1 day",
            retention="30 days",
            compression="gz"
        )
    
    logger.info(f"Logging configured for {settings.ENVIRONMENT} environment")
