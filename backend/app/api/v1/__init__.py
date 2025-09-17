"""
API v1 router aggregation
"""
from fastapi import APIRouter

from app.api.v1.config import router as config_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.auth import router as auth_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.keyword_metrics import router as keyword_metrics_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.dimensions import router as dimensions_router
from app.api.v1.generic_dimensions import router as generic_dimensions_router
from app.api.v1.generic_analysis import router as generic_analysis_router
from app.api.v1.landscapes import router as landscapes_router
from app.api.v1.historical_metrics import router as historical_metrics_router
from app.api.v1.monitoring import router as monitoring_router
from app.api.v1.pipeline_monitoring import router as pipeline_monitoring_router
from app.api.v1.endpoints.webhooks import router as webhooks_router
from app.api.v1.pipeline_logs import router as pipeline_logs_router
from app.api.v1.export import router as export_router


# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(config_router, tags=["configuration"]) # Router already has prefix
api_router.include_router(keywords_router, prefix="/keywords", tags=["keywords"])
api_router.include_router(keyword_metrics_router, tags=["keyword-metrics"]) # Router already has prefix
api_router.include_router(pipeline_router, tags=["pipeline"]) # Router already has prefix
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(dimensions_router, prefix="/dimensions", tags=["dimensions"])
api_router.include_router(generic_dimensions_router, prefix="/generic-dimensions", tags=["generic-dimensions"])
api_router.include_router(generic_analysis_router, prefix="/generic-analysis", tags=["generic-analysis"])
api_router.include_router(landscapes_router, prefix="/landscapes", tags=["landscapes"])
api_router.include_router(historical_metrics_router, prefix="/historical-metrics", tags=["historical-metrics"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(pipeline_monitoring_router, prefix="/pipeline", tags=["pipeline-monitoring"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(pipeline_logs_router, tags=["pipeline-logs"])
api_router.include_router(export_router, tags=["export"])


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
            "/keyword-metrics",
            "/pipeline",
            "/analysis",
            "/dashboard",
            "/dimensions",
            "/generic-dimensions",
            "/generic-analysis",
            "/landscapes",
            "/historical-metrics",
            "/monitoring",
            "/webhooks",
            "/export"
        ]
    }
