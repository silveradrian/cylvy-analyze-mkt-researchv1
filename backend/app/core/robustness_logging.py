"""
Configurable Logging System for Pipeline Robustness
Provides detailed logging that can be toggled on/off for testing
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger
from pydantic_settings import BaseSettings
import contextvars

# Context variable for request tracking
request_context = contextvars.ContextVar('request_context', default={})


class RobustnessLoggingConfig(BaseSettings):
    """Configuration for robustness logging"""
    
    # Master switches
    ROBUSTNESS_DEBUG_ENABLED: bool = True
    ROBUSTNESS_LOG_TO_FILE: bool = True
    ROBUSTNESS_LOG_TO_CONSOLE: bool = True
    
    # Component-specific logging
    LOG_CIRCUIT_BREAKER: bool = True
    LOG_JOB_QUEUE: bool = True
    LOG_STATE_TRACKER: bool = True
    LOG_RETRY_MANAGER: bool = True
    LOG_ERROR_HANDLER: bool = True
    
    # Detail levels
    LOG_API_CALLS: bool = True
    LOG_DB_QUERIES: bool = True
    LOG_PERFORMANCE_METRICS: bool = True
    LOG_MEMORY_USAGE: bool = True
    
    # Log formatting
    LOG_JSON_FORMAT: bool = False
    LOG_INCLUDE_CONTEXT: bool = True
    LOG_INCLUDE_STACK_TRACE: bool = True
    
    # File logging settings
    LOG_FILE_PATH: str = "logs/robustness"
    LOG_FILE_ROTATION: str = "100 MB"
    LOG_FILE_RETENTION: str = "7 days"
    LOG_FILE_COMPRESSION: str = "zip"
    
    class Config:
        env_prefix = "ROBUSTNESS_"


# Global configuration instance
log_config = RobustnessLoggingConfig()


def setup_robustness_logging():
    """Configure robustness logging based on settings"""
    
    # Remove default logger
    logger.remove()
    
    # Console logging
    if log_config.ROBUSTNESS_LOG_TO_CONSOLE and log_config.ROBUSTNESS_DEBUG_ENABLED:
        if log_config.LOG_JSON_FORMAT:
            logger.add(
                sys.stdout,
                format="{message}",
                serialize=True,
                level="DEBUG"
            )
        else:
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                       "<level>{level: <8}</level> | "
                       "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                       "<level>{message}</level>",
                level="DEBUG",
                colorize=True
            )
    
    # File logging
    if log_config.ROBUSTNESS_LOG_TO_FILE and log_config.ROBUSTNESS_DEBUG_ENABLED:
        log_path = Path(log_config.LOG_FILE_PATH)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Detailed debug log
        logger.add(
            log_path / "robustness_debug_{time}.log",
            rotation=log_config.LOG_FILE_ROTATION,
            retention=log_config.LOG_FILE_RETENTION,
            compression=log_config.LOG_FILE_COMPRESSION,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            serialize=log_config.LOG_JSON_FORMAT
        )
        
        # Error log
        logger.add(
            log_path / "robustness_errors_{time}.log",
            rotation=log_config.LOG_FILE_ROTATION,
            retention=log_config.LOG_FILE_RETENTION,
            compression=log_config.LOG_FILE_COMPRESSION,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="ERROR",
            serialize=log_config.LOG_JSON_FORMAT,
            backtrace=True,
            diagnose=True
        )
        
        # Performance metrics log
        if log_config.LOG_PERFORMANCE_METRICS:
            logger.add(
                log_path / "robustness_performance_{time}.log",
                rotation=log_config.LOG_FILE_ROTATION,
                retention=log_config.LOG_FILE_RETENTION,
                filter=lambda record: "performance" in record["extra"],
                format="{message}",
                serialize=True
            )


class RobustnessLogger:
    """Enhanced logger for robustness components"""
    
    def __init__(self, component: str):
        self.component = component
        self.enabled = self._is_component_enabled(component)
        
    def _is_component_enabled(self, component: str) -> bool:
        """Check if logging is enabled for component"""
        if not log_config.ROBUSTNESS_DEBUG_ENABLED:
            return False
            
        component_map = {
            "circuit_breaker": log_config.LOG_CIRCUIT_BREAKER,
            "job_queue": log_config.LOG_JOB_QUEUE,
            "state_tracker": log_config.LOG_STATE_TRACKER,
            "retry_manager": log_config.LOG_RETRY_MANAGER,
            "error_handler": log_config.LOG_ERROR_HANDLER
        }
        return component_map.get(component, True)
    
    def _get_context(self) -> Dict[str, Any]:
        """Get current context information"""
        ctx = request_context.get()
        return {
            "component": self.component,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": ctx.get("request_id"),
            "user_id": ctx.get("user_id"),
            "pipeline_id": ctx.get("pipeline_id"),
            **ctx
        }
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with context if enabled"""
        if not log_config.LOG_INCLUDE_CONTEXT:
            return message
            
        context = self._get_context()
        context.update(kwargs)
        
        if log_config.LOG_JSON_FORMAT:
            return json.dumps({
                "message": message,
                "context": context
            })
        else:
            return f"{message} | context={json.dumps(context, default=str)}"
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        if self.enabled:
            logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if self.enabled:
            logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if self.enabled:
            logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception"""
        if self.enabled:
            if error and log_config.LOG_INCLUDE_STACK_TRACE:
                logger.exception(self._format_message(message, error=str(error), **kwargs))
            else:
                logger.error(self._format_message(message, error=str(error) if error else None, **kwargs))
    
    def api_call(self, service: str, method: str, url: str, status: Optional[int] = None, 
                 duration_ms: Optional[float] = None, **kwargs):
        """Log API call details"""
        if self.enabled and log_config.LOG_API_CALLS:
            self.debug(
                f"API Call: {method} {url}",
                service=service,
                method=method,
                url=url,
                status=status,
                duration_ms=duration_ms,
                **kwargs
            )
    
    def db_query(self, query: str, duration_ms: float, rows_affected: Optional[int] = None, **kwargs):
        """Log database query details"""
        if self.enabled and log_config.LOG_DB_QUERIES:
            self.debug(
                f"DB Query executed",
                query=query[:200],  # Truncate long queries
                duration_ms=duration_ms,
                rows_affected=rows_affected,
                **kwargs
            )
    
    def performance(self, metric_name: str, value: float, unit: str = "ms", **kwargs):
        """Log performance metrics"""
        if self.enabled and log_config.LOG_PERFORMANCE_METRICS:
            logger.bind(performance=True).info(
                json.dumps({
                    "metric": metric_name,
                    "value": value,
                    "unit": unit,
                    "component": self.component,
                    "timestamp": datetime.utcnow().isoformat(),
                    **kwargs
                })
            )
    
    def memory_usage(self, operation: str, memory_mb: float, **kwargs):
        """Log memory usage"""
        if self.enabled and log_config.LOG_MEMORY_USAGE:
            self.debug(
                f"Memory usage for {operation}: {memory_mb:.2f} MB",
                operation=operation,
                memory_mb=memory_mb,
                **kwargs
            )
    
    def state_transition(self, entity: str, from_state: str, to_state: str, reason: Optional[str] = None, **kwargs):
        """Log state transitions"""
        self.info(
            f"State transition: {entity} from {from_state} to {to_state}",
            entity=entity,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            **kwargs
        )
    
    def retry_attempt(self, operation: str, attempt: int, max_attempts: int, 
                     delay_seconds: float, error: Optional[str] = None, **kwargs):
        """Log retry attempts"""
        self.warning(
            f"Retry attempt {attempt}/{max_attempts} for {operation}",
            operation=operation,
            attempt=attempt,
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
            error=error,
            **kwargs
        )
    
    def queue_event(self, event: str, queue_name: str, job_id: Optional[str] = None, 
                   job_type: Optional[str] = None, **kwargs):
        """Log queue events"""
        self.debug(
            f"Queue event: {event}",
            event=event,
            queue_name=queue_name,
            job_id=job_id,
            job_type=job_type,
            **kwargs
        )
    
    def circuit_breaker_event(self, service: str, event: str, state: str, 
                            failure_count: Optional[int] = None, **kwargs):
        """Log circuit breaker events"""
        self.info(
            f"Circuit breaker {event}: {service}",
            service=service,
            event=event,
            state=state,
            failure_count=failure_count,
            **kwargs
        )


def get_logger(component: str) -> RobustnessLogger:
    """Get a logger instance for a component"""
    return RobustnessLogger(component)


def set_context(**kwargs):
    """Set context variables for current request/operation"""
    ctx = request_context.get()
    ctx.update(kwargs)
    request_context.set(ctx)


def clear_context():
    """Clear context variables"""
    request_context.set({})


# Performance monitoring decorator
def log_performance(component: str, operation: str):
    """Decorator to log function performance"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            if not log_config.ROBUSTNESS_DEBUG_ENABLED or not log_config.LOG_PERFORMANCE_METRICS:
                return await func(*args, **kwargs)
                
            logger_instance = get_logger(component)
            start_time = datetime.utcnow()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger_instance.performance(
                    f"{operation}_duration",
                    duration_ms,
                    operation=operation,
                    success=True
                )
                return result
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger_instance.performance(
                    f"{operation}_duration",
                    duration_ms,
                    operation=operation,
                    success=False,
                    error=str(e)
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            if not log_config.ROBUSTNESS_DEBUG_ENABLED or not log_config.LOG_PERFORMANCE_METRICS:
                return func(*args, **kwargs)
                
            logger_instance = get_logger(component)
            start_time = datetime.utcnow()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger_instance.performance(
                    f"{operation}_duration",
                    duration_ms,
                    operation=operation,
                    success=True
                )
                return result
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger_instance.performance(
                    f"{operation}_duration",
                    duration_ms,
                    operation=operation,
                    success=False,
                    error=str(e)
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Initialize logging on module import
setup_robustness_logging()
