"""
Cylvy Digital Landscape Analyzer - Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import db_pool
from app.api.v1 import api_router
from app.core.exceptions import setup_exception_handlers
from app.core.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Cylvy Digital Landscape Analyzer...")
    
    # Initialize database pool
    await db_pool.initialize()
    
    # Check database health on startup
    from app.core.database_check import DatabaseHealthChecker
    checker = DatabaseHealthChecker()
    health = await checker.check_connection()
    
    if health["status"] != "healthy":
        logger.error("Database connection failed on startup!")
        raise Exception("Database not available")
    
    logger.info("Database connection verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await db_pool.close()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-powered competitive intelligence platform for B2B content analysis",
    lifespan=lifespan
)

# Setup middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Setup exception handlers
setup_exception_handlers(app)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Include WebSocket router
app.include_router(websocket_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health"
    }

