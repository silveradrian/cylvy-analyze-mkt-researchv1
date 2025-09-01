"""
Core storage configuration
"""
from pathlib import Path
from app.core.config import settings


# Storage paths
STORAGE_PATH = Path(getattr(settings, 'STORAGE_PATH', '/app/storage'))
LOGOS_PATH = STORAGE_PATH / "logos"
EXPORTS_PATH = STORAGE_PATH / "exports"

# Ensure directories exist
STORAGE_PATH.mkdir(parents=True, exist_ok=True)
LOGOS_PATH.mkdir(parents=True, exist_ok=True)
EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
