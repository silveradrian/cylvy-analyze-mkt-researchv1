"""
Cylvy Digital Landscape Analyzer - Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger
import asyncio

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
    
    # Start pipeline monitor
    try:
        from app.services.robustness.pipeline_monitor import pipeline_monitor
        logger.info("Starting pipeline health monitor...")
        await pipeline_monitor.start_monitoring()
        app.state.pipeline_monitor = pipeline_monitor
    except Exception as e:
        logger.error(f"Failed to start pipeline monitor: {e}", exc_info=True)
        # Pipeline monitor is critical for reliability - log but don't crash
        app.state.pipeline_monitor = None
    
    # Resume interrupted pipelines after restart
    try:
        from app.services.pipeline.pipeline_resumption import check_and_resume_pipelines
        logger.info("Checking for interrupted pipelines...")
        asyncio.create_task(check_and_resume_pipelines())
    except Exception as e:
        logger.error(f"Failed to check pipeline resumption: {e}")
    
    # Start SERP scheduler if enabled
    try:
        if settings.SERP_SCHEDULER_ENABLED:
            from app.services.pipeline.pipeline_service import PipelineService
            from app.services.serp.serp_batch_scheduler import SerpBatchScheduler
            pipeline_service = PipelineService(settings, db_pool)
            scheduler = SerpBatchScheduler(db_pool, pipeline_service)
            await scheduler.start()
            app.state.serp_scheduler = scheduler
    except Exception as e:
        logger.error(f"Failed to start SerpBatchScheduler: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Stop pipeline monitor
    try:
        if hasattr(app.state, 'pipeline_monitor'):
            logger.info("Stopping pipeline monitor...")
            await app.state.pipeline_monitor.stop_monitoring()
    except Exception as e:
        logger.error(f"Error stopping pipeline monitor: {e}")
    
    # Stop SERP scheduler
    try:
        if hasattr(app.state, 'serp_scheduler'):
            await app.state.serp_scheduler.stop()
    except Exception:
        pass
    
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

