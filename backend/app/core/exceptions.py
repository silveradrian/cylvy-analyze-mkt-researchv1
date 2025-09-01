"""
Exception handling and error responses
"""
from typing import Union, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger


class CylvyException(Exception):
    """Base exception for Cylvy application"""
    
    def __init__(self, message: str, code: str = "CYLVY_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class DatabaseError(CylvyException):
    """Database related errors"""
    
    def __init__(self, message: str):
        super().__init__(message, "DATABASE_ERROR")


class ServiceUnavailableError(CylvyException):
    """External service unavailable"""
    
    def __init__(self, service: str, message: str = None):
        msg = message or f"{service} service is unavailable"
        super().__init__(msg, "SERVICE_UNAVAILABLE")


class ValidationError(CylvyException):
    """Validation errors"""
    
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class AuthenticationError(CylvyException):
    """Authentication errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR")


class AuthorizationError(CylvyException):
    """Authorization errors"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHORIZATION_ERROR")


def setup_exception_handlers(app: FastAPI):
    """Setup global exception handlers for the application"""
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions"""
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "type": "http_error"
                }
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors"""
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                    "type": "validation_error"
                }
            }
        )
    
    @app.exception_handler(CylvyException)
    async def cylvy_exception_handler(request: Request, exc: CylvyException):
        """Handle Cylvy application exceptions"""
        logger.error(f"Application error: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "type": "application_error"
                }
            }
        )
    
    @app.exception_handler(DatabaseError)
    async def database_exception_handler(request: Request, exc: DatabaseError):
        """Handle database errors"""
        logger.error(f"Database error: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Database operation failed",
                    "type": "database_error"
                }
            }
        )
    
    @app.exception_handler(ServiceUnavailableError)
    async def service_exception_handler(request: Request, exc: ServiceUnavailableError):
        """Handle external service errors"""
        logger.error(f"Service error: {exc.message}")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "SERVICE_UNAVAILABLE", 
                    "message": exc.message,
                    "type": "service_error"
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.error(f"Unexpected error: {type(exc).__name__}: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "type": "internal_error"
                }
            }
        )
