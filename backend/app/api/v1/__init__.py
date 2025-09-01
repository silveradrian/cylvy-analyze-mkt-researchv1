"""
API v1 router aggregation
"""
from fastapi import APIRouter

from app.api.v1.config import router as config_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.auth import router as auth_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.dashboard import router as dashboard_router


# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(config_router, tags=["configuration"]) # Router already has prefix
api_router.include_router(keywords_router, prefix="/keywords", tags=["keywords"])
api_router.include_router(pipeline_router, tags=["pipeline"]) # Router already has prefix
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])


# Health check endpoint at API level
@api_router.get("/health")
async def api_health():
    """API health check"""
    return {
        "api_version": "v1",
        "status": "healthy",
        "endpoints": [
            "/auth",
            "/config", 
            "/keywords",
            "/pipeline",
            "/analysis",
            "/dashboard"
        ]
    }
