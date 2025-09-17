"""
Retry Management Service
Handles retry logic with categorized errors and adaptive strategies
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Dict, TypeVar, Union
import uuid
from enum import Enum
import asyncpg
from loguru import logger

from app.core.database import DatabasePool
from app.core.robustness_logging import get_logger


T = TypeVar('T')


class RetryStrategy(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    NONE = "none"


class RetryManager:
    """
    Manages retry logic with error categorization and adaptive strategies
    """
    
    def __init__(self, db_pool: DatabasePool):
        self.db_pool = db_pool
        self.logger = get_logger("retry_manager")
        self._error_categories: Optional[Dict[str, Dict[str, Any]]] = None
        
    async def _load_error_categories(self):
        """Load error categories from database"""
        if self._error_categories is not None:
            return
            
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM error_categories")
            self._error_categories = {
                row['error_code']: dict(row) for row in rows
            }
            
    def _categorize_error(self, error: Exception) -> Dict[str, Any]:
        """Categorize an error and determine retry strategy"""
        error_str = str(error)
        error_type = type(error).__name__
        
        # Check for HTTP status codes
        http_status = None
        if hasattr(error, 'status_code'):
            http_status = error.status_code
        elif hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            http_status = error.response.status_code
            
        # Find matching error category
        for code, category in (self._error_categories or {}).items():
            # Check HTTP status codes
            if http_status and category['http_status_codes']:
                if http_status in category['http_status_codes']:
                    return category
                    
            # Check error patterns
            if category['error_patterns']:
                for pattern in category['error_patterns']:
                    if pattern.lower() in error_str.lower():
                        return category
                        
        # Default categorization based on error type
        if 'timeout' in error_str.lower():
            return self._error_categories.get('TIMEOUT', self._default_category())
        elif 'rate' in error_str.lower() and 'limit' in error_str.lower():
            return self._error_categories.get('RATE_LIMIT', self._default_category())
        elif 'network' in error_str.lower() or 'connection' in error_str.lower():
            return self._error_categories.get('NETWORK_ERROR', self._default_category())
            
        return self._default_category()
    
    def _default_category(self) -> Dict[str, Any]:
        """Default error category for unknown errors"""
        return {
            'error_code': 'UNKNOWN',
            'category': 'unknown',
            'is_recoverable': True,
            'retry_strategy': RetryStrategy.EXPONENTIAL,
            'max_retries': 3,
            'base_delay_seconds': 1,
            'max_delay_seconds': 60
        }
    
    def _calculate_delay(
        self,
        attempt: int,
        strategy: RetryStrategy,
        base_delay: float,
        max_delay: float
    ) -> float:
        """Calculate delay based on retry strategy"""
        if strategy == RetryStrategy.EXPONENTIAL:
            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            return delay + jitter
            
        elif strategy == RetryStrategy.LINEAR:
            # Linear backoff
            return min(base_delay * attempt, max_delay)
            
        elif strategy == RetryStrategy.CONSTANT:
            # Constant delay
            return base_delay
            
        else:
            return 0
    
    async def retry_with_backoff(
        self,
        func: Callable[..., T],
        *args,
        max_attempts: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        **kwargs
    ) -> T:
        """
        Execute function with automatic retry and backoff
        
        Args:
            func: Function to execute
            max_attempts: Override max attempts (uses error category default if None)
            entity_type: Type of entity for tracking (e.g., 'pipeline_state')
            entity_id: Entity ID for tracking
            *args, **kwargs: Arguments for function
            
        Returns:
            Result from successful function execution
            
        Raises:
            Last exception if all retries fail
        """
        await self._load_error_categories()
        
        attempt = 0
        last_error = None
        
        while True:
            attempt += 1
            
            try:
                # Log retry attempt
                if attempt > 1:
                    self.logger.retry_attempt(
                        operation=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts or 3,
                        delay_seconds=0,
                        error=str(last_error) if last_error else None
                    )
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                    
                # Success - record if tracking
                if entity_type and entity_id and attempt > 1:
                    try:
                        normalized_entity_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(entity_id)))
                    except Exception:
                        normalized_entity_id = str(uuid.uuid4())
                    await self._record_retry_success(
                        entity_type, normalized_entity_id, attempt
                    )
                    
                return result
                
            except Exception as e:
                last_error = e
                
                # Categorize error
                error_category = self._categorize_error(e)
                
                # Check if recoverable
                if not error_category['is_recoverable']:
                    self.logger.error(
                        f"Non-recoverable error: {error_category['error_code']}",
                        error=e,
                        error_code=error_category['error_code']
                    )
                    raise
                
                # Check max attempts
                effective_max_attempts = max_attempts or error_category['max_retries']
                if attempt >= effective_max_attempts:
                    self.logger.error(
                        f"Max retries exceeded",
                        error=e,
                        attempts=attempt,
                        max_attempts=effective_max_attempts
                    )
                    raise
                
                # Calculate delay
                delay = self._calculate_delay(
                    attempt,
                    error_category['retry_strategy'],
                    error_category['base_delay_seconds'],
                    error_category['max_delay_seconds']
                )
                
                # Record retry attempt
                if entity_type and entity_id:
                    try:
                        normalized_entity_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(entity_id)))
                    except Exception:
                        normalized_entity_id = str(uuid.uuid4())
                    await self._record_retry_attempt(
                        entity_type, normalized_entity_id, attempt, 
                        error_category['error_code'], str(e), delay
                    )
                
                # Log and wait
                self.logger.warning(
                    f"Retrying after error",
                    error_code=error_category['error_code'],
                    attempt=attempt,
                    delay_seconds=delay,
                    error=str(e)
                )
                
                await asyncio.sleep(delay)
    
    async def _record_retry_attempt(
        self,
        entity_type: str,
        entity_id: str,
        attempt: int,
        error_code: str,
        error_message: str,
        retry_delay: float
    ):
        """Record retry attempt in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO retry_history (
                    entity_type,
                    entity_id,
                    attempt_number,
                    started_at,
                    success,
                    error_code,
                    error_message,
                    retry_delay_seconds,
                    next_retry_at
                ) VALUES ($1, $2, $3, NOW(), FALSE, $4, $5, $6, $7)
                """,
                entity_type,
                entity_id,
                attempt,
                error_code,
                error_message[:1000],
                retry_delay,
                datetime.utcnow() + timedelta(seconds=retry_delay)
            )
    
    async def _record_retry_success(
        self,
        entity_type: str,
        entity_id: str,
        attempt: int
    ):
        """Record successful retry in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO retry_history (
                    entity_type,
                    entity_id,
                    attempt_number,
                    started_at,
                    completed_at,
                    success
                ) VALUES ($1, $2, $3, NOW(), NOW(), TRUE)
                """,
                entity_type,
                entity_id,
                attempt
            )
    
    async def batch_retry(
        self,
        items: list[Dict[str, Any]],
        func: Callable,
        concurrency: int = 10,
        max_attempts: int = 3
    ) -> Dict[str, Union[Any, Exception]]:
        """
        Retry multiple items with concurrency control
        
        Args:
            items: List of items to process
            func: Function to call for each item
            concurrency: Max concurrent executions
            max_attempts: Max retry attempts per item
            
        Returns:
            Dict mapping item ID to result or exception
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}
        
        async def process_item(item: Dict[str, Any]):
            async with semaphore:
                try:
                    result = await self.retry_with_backoff(
                        func,
                        item,
                        max_attempts=max_attempts,
                        entity_type='batch_item',
                        entity_id=str(item.get('id', item))
                    )
                    results[str(item.get('id', item))] = result
                except Exception as e:
                    results[str(item.get('id', item))] = e
        
        # Process all items
        await asyncio.gather(
            *[process_item(item) for item in items],
            return_exceptions=True
        )
        
        # Log summary
        success_count = sum(1 for r in results.values() if not isinstance(r, Exception))
        failure_count = len(results) - success_count
        
        self.logger.info(
            f"Batch retry completed",
            total=len(items),
            success=success_count,
            failure=failure_count
        )
        
        return results
    
    async def get_retry_statistics(
        self,
        entity_type: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """Get retry statistics"""
        query = """
            SELECT 
                entity_type,
                COUNT(*) as total_retries,
                COUNT(DISTINCT entity_id) as unique_entities,
                AVG(attempt_number) as avg_attempts,
                MAX(attempt_number) as max_attempts,
                COUNT(*) FILTER (WHERE success = TRUE) as successful_retries,
                COUNT(*) FILTER (WHERE success = FALSE) as failed_retries,
                COUNT(DISTINCT error_code) as unique_error_codes,
                AVG(retry_delay_seconds) as avg_retry_delay
            FROM retry_history
            WHERE started_at > NOW() - INTERVAL '%s hours'
        """
        params = [time_window_hours]
        
        if entity_type:
            query += " AND entity_type = $2"
            params.append(entity_type)
            
        query += " GROUP BY entity_type"
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
        stats = {}
        for row in rows:
            stats[row['entity_type']] = dict(row)
            stats[row['entity_type']]['success_rate'] = (
                row['successful_retries'] / row['total_retries'] * 100
                if row['total_retries'] > 0 else 0
            )
            
        return stats
    
    async def update_error_category(
        self,
        error_code: str,
        updates: Dict[str, Any]
    ):
        """Update error category configuration"""
        allowed_fields = {
            'is_recoverable', 'retry_strategy', 'max_retries',
            'base_delay_seconds', 'max_delay_seconds'
        }
        
        # Filter allowed updates
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            return
            
        # Build update query
        set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(filtered_updates.keys())]
        query = f"""
            UPDATE error_categories
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE error_code = $1
        """
        
        params = [error_code] + list(filtered_updates.values())
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(query, *params)
            
        # Clear cache
        self._error_categories = None
        
        self.logger.info(
            f"Updated error category",
            error_code=error_code,
            updates=filtered_updates
        )
