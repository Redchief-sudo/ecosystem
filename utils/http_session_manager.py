"""
Centralized HTTP Session Manager
---------------------------------
Eliminates aiohttp session and connector leaks by providing exactly one shared session per process.
"""

import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """
    Centralized HTTP session manager for all scanners.
    
    Provides exactly one shared aiohttp.ClientSession per process
    to eliminate resource leaks and connection pool exhaustion.
    """
    
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """
        Get the shared HTTP session.
        
        Creates the session if it doesn't exist or is closed.
        Uses a lock to prevent race conditions during creation.
        
        Returns:
            Shared aiohttp.ClientSession instance
        """
        async with cls._lock:
            if cls._session is None or cls._session.closed:
                logger.info("Creating new shared HTTP session")
                cls._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=15),
                    connector=aiohttp.TCPConnector(
                        limit=100,  # Total connection pool size
                        limit_per_host=20,  # Connections per host
                        force_close=True,  # Force close connections
                        enable_cleanup_closed=True  # Enable cleanup
                    )
                )
            return cls._session
    
    @classmethod
    async def close(cls) -> None:
        """
        Close the shared HTTP session.
        
        Should be called during application shutdown.
        """
        async with cls._lock:
            if cls._session and not cls._session.closed:
                logger.info("Closing shared HTTP session")
                await cls._session.close()
                cls._session = None
    
    @classmethod
    def is_active(cls) -> bool:
        """Check if the shared session is active and not closed."""
        return cls._session is not None and not cls._session.closed


# Convenience functions for external use
async def get_http_session() -> aiohttp.ClientSession:
    """Convenience function to get the shared HTTP session."""
    return await HTTPSessionManager.get_session()


async def close_http_session() -> None:
    """Convenience function to close the shared HTTP session."""
    await HTTPSessionManager.close()
