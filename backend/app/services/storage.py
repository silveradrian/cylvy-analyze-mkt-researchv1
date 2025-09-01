"""
File storage service for logos and exports
"""
import os
import uuid
from pathlib import Path
from typing import Optional
import aiofiles
from fastapi import UploadFile
from PIL import Image
import magic
from loguru import logger

from app.core.config import settings


class StorageService:
    """Handles file storage for client assets"""
    
    ALLOWED_IMAGE_TYPES = {
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/svg+xml': '.svg'
    }
    
    MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5MB
    LOGO_DIMENSIONS = (500, 500)  # Max dimensions for raster images
    
    def __init__(self):
        self.storage_path = Path(settings.STORAGE_PATH)
        self.logos_path = self.storage_path / "logos"
        self.exports_path = self.storage_path / "exports"
        
        # Ensure directories exist
        self.logos_path.mkdir(parents=True, exist_ok=True)
        self.exports_path.mkdir(parents=True, exist_ok=True)
    
    async def save_logo(self, file: UploadFile) -> str:
        """
        Save uploaded logo file
        
        Args:
            file: Uploaded file from FastAPI
            
        Returns:
            Relative path to saved logo
        """
        # Validate file size
        contents = await file.read()
        if len(contents) > self.MAX_LOGO_SIZE:
            raise ValueError(f"File too large. Maximum size is {self.MAX_LOGO_SIZE / 1024 / 1024}MB")
        
        # Reset file pointer
        await file.seek(0)
        
        # Validate file type
        mime = magic.from_buffer(contents, mime=True)
        if mime not in self.ALLOWED_IMAGE_TYPES:
            raise ValueError(f"Invalid file type. Allowed types: {', '.join(self.ALLOWED_IMAGE_TYPES.keys())}")
        
        # Generate unique filename
        file_ext = self.ALLOWED_IMAGE_TYPES[mime]
        filename = f"logo_{uuid.uuid4().hex}{file_ext}"
        file_path = self.logos_path / filename
        
        # Process and save file
        if mime == 'image/svg+xml':
            # SVG files can be saved directly
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(contents)
        else:
            # Process raster images
            await self._process_raster_logo(contents, file_path)
        
        logger.info(f"Logo saved to {file_path}")
        return f"/storage/logos/{filename}"
    
    async def _process_raster_logo(self, contents: bytes, output_path: Path):
        """Process and optimize raster images"""
        import io
        
        # Open image
        image = Image.open(io.BytesIO(contents))
        
        # Convert RGBA to RGB if needed (for JPEG compatibility)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Resize if too large
        if image.width > self.LOGO_DIMENSIONS[0] or image.height > self.LOGO_DIMENSIONS[1]:
            image.thumbnail(self.LOGO_DIMENSIONS, Image.Resampling.LANCZOS)
        
        # Save optimized image
        if output_path.suffix.lower() in ['.jpg', '.jpeg']:
            image.save(output_path, 'JPEG', quality=90, optimize=True)
        else:
            image.save(output_path, 'PNG', optimize=True)
    
    async def delete_logo(self, logo_path: str) -> bool:
        """Delete a logo file"""
        try:
            if logo_path.startswith('/storage/logos/'):
                filename = logo_path.split('/')[-1]
                file_path = self.logos_path / filename
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted logo: {file_path}")
                    return True
        except Exception as e:
            logger.error(f"Error deleting logo: {e}")
        return False
    
    async def save_export(self, data: bytes, filename: str) -> str:
        """Save export file"""
        file_path = self.exports_path / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(data)
        
        logger.info(f"Export saved to {file_path}")
        return f"/storage/exports/{filename}"
    
    def get_logo_url(self, filename: Optional[str]) -> Optional[str]:
        """Get full URL for logo"""
        if not filename:
            return None
        
        if filename.startswith('http'):
            return filename
        
        if filename.startswith('/'):
            return f"{settings.API_URL}{filename}"
        
        return f"{settings.API_URL}/storage/logos/{filename}"
