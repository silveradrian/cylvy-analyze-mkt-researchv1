"""
Circuit Breaker Pattern Implementation
Prevents cascade failures by temporarily blocking calls to failing services
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Any, Dict
from enum import Enum
import asyncpg
from loguru import logger

from app.core.database import DatabasePool


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking calls
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are blocked
    - HALF_OPEN: Testing if service recovered, limited requests
    """
    
    def __init__(
        self,
        service_name: str,
        db_pool: DatabasePool,
        failure_threshold: int = 10,
        success_threshold: int = 5,
        timeout_seconds: int = 300,
        half_open_requests: int = 1
    ):
        self.service_name = service_name
        self.db_pool = db_pool
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_requests = half_open_requests
        self._half_open_counter = 0
        self._lock = asyncio.Lock()
        
    async def _get_state(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Get or create circuit breaker state from database"""
        state = await conn.fetchrow(
            """
            INSERT INTO circuit_breakers (
                service_name, 
                failure_threshold, 
                success_threshold, 
                timeout_seconds
            ) VALUES ($1, $2, $3, $4)
            ON CONFLICT (service_name) 
            DO UPDATE SET 
                updated_at = NOW()
            RETURNING *
            """,
            self.service_name,
            self.failure_threshold,
            self.success_threshold,
            self.timeout_seconds
        )
        return dict(state)
    
    async def _should_attempt_reset(self, state: Dict[str, Any]) -> bool:
        """Check if enough time has passed to attempt reset"""
        if state['state'] != CircuitState.OPEN:
            return False
            
        if not state['opened_at']:
            return False
            
        time_since_open = datetime.utcnow() - state['opened_at'].replace(tzinfo=None)
        return time_since_open > timedelta(seconds=self.timeout_seconds)
    
    async def _update_state(
        self,
        conn: asyncpg.Connection,
        new_state: CircuitState,
        increment_success: bool = False,
        increment_failure: bool = False,
        reset_counts: bool = False
    ):
        """Update circuit breaker state in database"""
        # Build SET clause parts separately from UPDATE statement
        set_parts = [
            "state = $2",
            "updated_at = NOW()"
        ]
        
        params = [self.service_name, new_state]
        param_count = 3
        
        if increment_success:
            set_parts.append(f"success_count = success_count + 1")
            set_parts.append(f"total_successes = total_successes + 1")
            set_parts.append(f"last_success_at = NOW()")
            
        if increment_failure:
            set_parts.append(f"failure_count = failure_count + 1")
            set_parts.append(f"total_failures = total_failures + 1")
            set_parts.append(f"last_failure_at = NOW()")
            
        if reset_counts:
            set_parts.append(f"success_count = 0")
            set_parts.append(f"failure_count = 0")
            
        if new_state == CircuitState.OPEN:
            set_parts.append(f"opened_at = NOW()")
        elif new_state == CircuitState.HALF_OPEN:
            set_parts.append(f"half_opened_at = NOW()")
            
        set_parts.append("total_requests = total_requests + 1")
        
        # Build the query with proper comma separation
        set_clause = ", ".join(set_parts)
        query = f"UPDATE circuit_breakers SET {set_clause} WHERE service_name = $1"
        await conn.execute(query, *params)
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function through circuit breaker
        
        Args:
            func: The function to call
            fallback: Optional fallback function if circuit is open
            *args, **kwargs: Arguments for the function
            
        Returns:
            Result from func or fallback
            
        Raises:
            Exception: If circuit is open and no fallback provided
        """
        async with self.db_pool.acquire() as conn:
            async with self._lock:
                state = await self._get_state(conn)
                
                # Check if we should transition from OPEN to HALF_OPEN
                if await self._should_attempt_reset(state):
                    await self._update_state(conn, CircuitState.HALF_OPEN, reset_counts=True)
                    state['state'] = CircuitState.HALF_OPEN
                    self._half_open_counter = 0
                    logger.info(f"Circuit breaker for {self.service_name} entering HALF_OPEN state")
                
                # OPEN state - reject calls
                if state['state'] == CircuitState.OPEN:
                    logger.warning(f"Circuit breaker OPEN for {self.service_name}, rejecting call")
                    if fallback:
                        return await fallback(*args, **kwargs)
                    raise Exception(f"Circuit breaker is OPEN for {self.service_name}")
                
                # HALF_OPEN state - limited calls
                if state['state'] == CircuitState.HALF_OPEN:
                    if self._half_open_counter >= self.half_open_requests:
                        logger.warning(f"Circuit breaker HALF_OPEN limit reached for {self.service_name}")
                        if fallback:
                            return await fallback(*args, **kwargs)
                        raise Exception(f"Circuit breaker HALF_OPEN limit reached for {self.service_name}")
                    self._half_open_counter += 1
            
            # Try to execute the function
            try:
                result = await func(*args, **kwargs)
                
                # Success - update state
                async with self._lock:
                    state = await self._get_state(conn)
                    
                    if state['state'] == CircuitState.HALF_OPEN:
                        new_success_count = state['success_count'] + 1
                        if new_success_count >= self.success_threshold:
                            # Recover to CLOSED
                            await self._update_state(
                                conn, 
                                CircuitState.CLOSED, 
                                increment_success=True,
                                reset_counts=True
                            )
                            logger.info(f"Circuit breaker for {self.service_name} recovered to CLOSED state")
                        else:
                            await self._update_state(conn, state['state'], increment_success=True)
                    else:
                        # CLOSED state - just track success
                        await self._update_state(conn, state['state'], increment_success=True)
                
                return result
                
            except Exception as e:
                # Failure - update state
                async with self._lock:
                    state = await self._get_state(conn)
                    
                    if state['state'] == CircuitState.CLOSED:
                        new_failure_count = state['failure_count'] + 1
                        if new_failure_count >= self.failure_threshold:
                            # Trip to OPEN
                            await self._update_state(
                                conn,
                                CircuitState.OPEN,
                                increment_failure=True
                            )
                            logger.error(f"Circuit breaker for {self.service_name} tripped to OPEN state")
                        else:
                            await self._update_state(conn, state['state'], increment_failure=True)
                            
                    elif state['state'] == CircuitState.HALF_OPEN:
                        # Failed in HALF_OPEN, back to OPEN
                        await self._update_state(
                            conn,
                            CircuitState.OPEN,
                            increment_failure=True
                        )
                        logger.warning(f"Circuit breaker for {self.service_name} failed in HALF_OPEN, back to OPEN")
                    else:
                        # Already OPEN
                        await self._update_state(conn, state['state'], increment_failure=True)
                
                raise
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        async with self.db_pool.acquire() as conn:
            state = await self._get_state(conn)
            
            # Calculate success rate
            total = state['total_requests']
            success_rate = (state['total_successes'] / total * 100) if total > 0 else 0
            
            return {
                'service_name': self.service_name,
                'current_state': state['state'],
                'failure_count': state['failure_count'],
                'success_count': state['success_count'],
                'total_requests': state['total_requests'],
                'total_failures': state['total_failures'],
                'total_successes': state['total_successes'],
                'success_rate': round(success_rate, 2),
                'last_failure_at': state['last_failure_at'],
                'last_success_at': state['last_success_at'],
                'opened_at': state['opened_at'],
                'half_opened_at': state['half_opened_at']
            }
    
    async def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        async with self.db_pool.acquire() as conn:
            async with self._lock:
                await self._update_state(conn, CircuitState.CLOSED, reset_counts=True)
                self._half_open_counter = 0
                logger.info(f"Circuit breaker for {self.service_name} manually reset to CLOSED")


class CircuitBreakerManager:
    """Manages circuit breakers for multiple services"""
    
    def __init__(self, db_pool: DatabasePool):
        self.db_pool = db_pool
        self._breakers: Dict[str, CircuitBreaker] = {}
        
    def get_breaker(
        self,
        service_name: str,
        failure_threshold: int = 10,
        success_threshold: int = 5,
        timeout_seconds: int = 300
    ) -> CircuitBreaker:
        """Get or create circuit breaker for a service"""
        if service_name not in self._breakers:
            self._breakers[service_name] = CircuitBreaker(
                service_name=service_name,
                db_pool=self.db_pool,
                failure_threshold=failure_threshold,
                success_threshold=success_threshold,
                timeout_seconds=timeout_seconds
            )
        return self._breakers[service_name]
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        metrics = {}
        for name, breaker in self._breakers.items():
            metrics[name] = await breaker.get_metrics()
        return metrics
    
    async def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            await breaker.reset()
