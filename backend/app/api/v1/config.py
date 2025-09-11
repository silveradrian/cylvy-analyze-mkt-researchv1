"""
Client configuration API endpoints
"""
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.config_service import ConfigService
from app.services.storage import StorageService
from app.core.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/config", tags=["configuration"])


class ClientConfigBase(BaseModel):
    """Base client configuration model"""
    company_name: str = Field(..., description="Company name")
    company_domain: str = Field(..., description="Primary company domain")
    admin_email: Optional[str] = Field(None, description="Admin contact email")
    support_email: Optional[str] = Field(None, description="Support contact email")
    description: Optional[str] = Field(None, description="Company description")


class ClientConfigUpdate(BaseModel):
    """Client configuration update model"""
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    admin_email: Optional[str] = None
    support_email: Optional[str] = None
    description: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    legal_name: Optional[str] = None
    additional_domains: Optional[list[str]] = None
    competitors: Optional[list[dict]] = None


class ClientConfigResponse(ClientConfigBase):
    """Client configuration response model"""
    id: str
    company_logo_url: Optional[str] = None
    primary_color: str = "#3B82F6"
    secondary_color: str = "#10B981"
    legal_name: Optional[str] = None
    additional_domains: Optional[list[str]] = None
    competitors: Optional[list[dict]] = None
    created_at: str
    updated_at: str
    
    @classmethod
    def from_db_record(cls, record):
        """Convert database record to response model"""
        data = dict(record)
        # Convert UUID and datetime to strings
        data['id'] = str(data['id']) if data.get('id') else 'default'
        data['created_at'] = data['created_at'].isoformat() if data.get('created_at') else ''
        data['updated_at'] = data['updated_at'].isoformat() if data.get('updated_at') else ''
        return cls(**data)


class BrandingConfig(BaseModel):
    """Branding configuration model"""
    company_logo_url: Optional[str] = None
    primary_color: str = Field("#3B82F6", pattern="^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field("#10B981", pattern="^#[0-9A-Fa-f]{6}$")


# Initialize services
config_service = ConfigService()
storage_service = StorageService()


@router.get("", response_model=ClientConfigResponse)
async def get_client_config(
    current_user: User = Depends(get_current_user)
):
    """Get current client configuration"""
    config = await config_service.get_config()
    if not config:
        # Return default config for initial setup
        return ClientConfigResponse(
            id="default",
            company_name="My Company",
            company_domain="example.com",
            created_at="",
            updated_at=""
        )
    
    # Convert database record to proper response format
    return ClientConfigResponse.from_db_record(config)


@router.put("", response_model=ClientConfigResponse)
async def update_client_config(
    config_update: ClientConfigUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update client configuration"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Filter out None values
    updates = {k: v for k, v in config_update.dict().items() if v is not None}
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    updated_config = await config_service.update_config(updates)
    return ClientConfigResponse.from_db_record(updated_config)


@router.get("/branding", response_model=BrandingConfig)
async def get_branding_config():
    """Get branding configuration (public endpoint)"""
    config = await config_service.get_config()
    return BrandingConfig(
        company_logo_url=config.company_logo_url,
        primary_color=config.primary_color,
        secondary_color=config.secondary_color
    )


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload company logo"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        # Delete existing logo if any
        current_config = await config_service.get_config()
        if current_config.company_logo_url:
            await storage_service.delete_logo(current_config.company_logo_url)
        
        # Save new logo
        logo_path = await storage_service.save_logo(file)
        
        # Update configuration
        await config_service.update_config({"company_logo_url": logo_path})
        
        return {
            "message": "Logo uploaded successfully",
            "logo_url": storage_service.get_logo_url(logo_path)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upload logo")


@router.delete("/logo")
async def delete_logo(
    current_user: User = Depends(get_current_user)
):
    """Delete company logo and revert to default"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get current logo
    config = await config_service.get_config()
    if config.company_logo_url:
        await storage_service.delete_logo(config.company_logo_url)
    
    # Clear logo from configuration
    await config_service.update_config({"company_logo_url": None})
    
    return {"message": "Logo deleted successfully"}


@router.get("/setup-status")
async def get_setup_status():
    """Check if initial setup is complete"""
    try:
        config = await config_service.get_config()
        
        # Simple setup status based on client config only
        has_company_config = (
            config is not None and
            config.company_name and
            config.company_name != "My Company" and
            config.company_domain and
            config.company_domain != "example.com"
        )
        
        return {
            "setup_complete": has_company_config,
            "steps_completed": {
                "company_info": has_company_config,
                "branding": config is not None and getattr(config, 'company_logo_url', None) is not None,
                "api_keys": False,  # Simplified for now
                "personas": False,  # Simplified for now
                "jtbd_phases": False  # Simplified for now
            },
            "company_name": config.company_name if config else None,
            "company_domain": config.company_domain if config else None
        }
    except Exception as e:
        # Return safe default if anything fails
        return {
            "setup_complete": False,
            "steps_completed": {
                "company_info": False,
                "branding": False,
                "api_keys": False,
                "personas": False,
                "jtbd_phases": False
            },
            "error": str(e)
        }

