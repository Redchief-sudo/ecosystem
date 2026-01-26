"""
Dead Letter Queue for Failed Tokens
----------------------------------
Handles tokens that fail processing for later analysis and recovery.
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from trading.token_pipeline.token_candidate import TokenCandidate

logger = logging.getLogger(__name__)

@dataclass
class FailedToken:
    """Represents a token that failed processing."""
    token_data: Dict[str, Any]
    error_message: str
    error_type: str
    scanner_name: str
    failed_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'token_data': self.token_data,
            'error_message': self.error_message,
            'error_type': self.error_type,
            'scanner_name': self.scanner_name,
            'failed_at': self.failed_at.isoformat(),
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FailedToken':
        """Create from dictionary."""
        return cls(
            token_data=data['token_data'],
            error_message=data['error_message'],
            error_type=data['error_type'],
            scanner_name=data['scanner_name'],
            failed_at=datetime.fromisoformat(data['failed_at']),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3)
        )

class DeadLetterQueue:
    """
    Dead letter queue for failed tokens with persistence and retry logic.
    
    Features:
    - Persistent storage to file
    - Retry logic with exponential backoff
    - Automatic cleanup of old/expired tokens
    - Metrics and monitoring
    """
    
    def __init__(self, storage_path: str = "/tmp/dead_letter_queue.json"):
        self.storage_path = Path(storage_path)
        self.failed_tokens: List[FailedToken] = []
        self.lock = asyncio.Lock()
        
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Metrics
        self.total_failed = 0
        self.total_retried = 0
        self.total_recovered = 0
        
        logger.info(f"DeadLetterQueue initialized with storage: {self.storage_path}")
    
    async def add_failed_token(
        self,
        token_data: Dict[str, Any],
        error_message: str,
        error_type: str,
        scanner_name: str,
        max_retries: int = 3
    ):
        """
        Add a failed token to the dead letter queue.
        
        Args:
            token_data: Raw token data that failed
            error_message: Detailed error message
            error_type: Type of error (normalization, validation, etc.)
            scanner_name: Name of the scanner that produced the token
            max_retries: Maximum number of retry attempts
        """
        async with self.lock:
            failed_token = FailedToken(
                token_data=token_data,
                error_message=error_message,
                error_type=error_type,
                scanner_name=scanner_name,
                failed_at=datetime.now(timezone.utc),
                max_retries=max_retries
            )
            
            self.failed_tokens.append(failed_token)
            self.total_failed += 1
            
            # Persist to storage
            await self._save_to_storage()
            
            logger.warning(f"Added failed token to DLQ: {scanner_name} - {error_type}: {error_message}")
    
    async def get_retry_candidates(self, max_age_hours: int = 1) -> List[FailedToken]:
        """
        Get tokens that are ready for retry.
        
        Args:
            max_age_hours: Minimum age before retry (for exponential backoff)
            
        Returns:
            List of FailedToken objects ready for retry
        """
        async with self.lock:
            now = datetime.now(timezone.utc)
            candidates = []
            
            for failed_token in self.failed_tokens:
                # Check if token has retries left
                if failed_token.retry_count >= failed_token.max_retries:
                    continue
                
                # Calculate backoff delay (exponential: 1min, 2min, 4min, etc.)
                backoff_minutes = 60 * (2 ** failed_token.retry_count)
                retry_time = failed_token.failed_at + timedelta(minutes=backoff_minutes)
                
                # Check if enough time has passed
                if now >= retry_time:
                    candidates.append(failed_token)
            
            return candidates
    
    async def mark_retry(self, failed_token: FailedToken, success: bool = False):
        """
        Mark a token as retried.
        
        Args:
            failed_token: The token that was retried
            success: Whether the retry was successful
        """
        async with self.lock:
            failed_token.retry_count += 1
            self.total_retried += 1
            
            if success:
                # Remove from queue if successful
                self.failed_tokens.remove(failed_token)
                self.total_recovered += 1
                logger.info(f"Successfully recovered token from DLQ: {failed_token.scanner_name}")
            else:
                logger.warning(f"Retry failed for token: {failed_token.scanner_name} (attempt {failed_token.retry_count}/{failed_token.max_retries})")
            
            # Persist changes
            await self._save_to_storage()
    
    async def cleanup_old_tokens(self, max_age_days: int = 7):
        """
        Remove old tokens that have exceeded retry limits.
        
        Args:
            max_age_days: Maximum age to keep tokens
        """
        async with self.lock:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(days=max_age_days)
            
            original_count = len(self.failed_tokens)
            
            # Remove old tokens that have exhausted retries
            self.failed_tokens = [
                token for token in self.failed_tokens
                if (token.retry_count < token.max_retries and token.failed_at > cutoff_time)
            ]
            
            removed_count = original_count - len(self.failed_tokens)
            
            if removed_count > 0:
                await self._save_to_storage()
                logger.info(f"Cleaned up {removed_count} old tokens from DLQ")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get dead letter queue metrics."""
        async with self.lock:
            error_types = {}
            scanner_counts = {}
            
            for token in self.failed_tokens:
                # Count by error type
                error_types[token.error_type] = error_types.get(token.error_type, 0) + 1
                # Count by scanner
                scanner_counts[token.scanner_name] = scanner_counts.get(token.scanner_name, 0) + 1
            
            return {
                'total_failed': self.total_failed,
                'total_retried': self.total_retried,
                'total_recovered': self.total_recovered,
                'current_queue_size': len(self.failed_tokens),
                'recovery_rate': self.total_recovered / max(self.total_failed, 1),
                'error_types': error_types,
                'scanner_counts': scanner_counts
            }
    
    async def _save_to_storage(self):
        """Save failed tokens to persistent storage."""
        try:
            data = [token.to_dict() for token in self.failed_tokens]
            async with aiofiles.open(self.storage_path, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save DLQ to storage: {e}")
    
    async def load_from_storage(self):
        """Load failed tokens from persistent storage."""
        try:
            if not self.storage_path.exists():
                return
            
            async with aiofiles.open(self.storage_path, 'r') as f:
                content = await f.read()
                if content:
                    data = json.loads(content)
                    self.failed_tokens = [FailedToken.from_dict(item) for item in data]
                    logger.info(f"Loaded {len(self.failed_tokens)} failed tokens from storage")
        except Exception as e:
            logger.error(f"Failed to load DLQ from storage: {e}")
    
    async def get_failed_tokens_for_analysis(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get failed tokens for analysis.
        
        Args:
            limit: Maximum number of tokens to return
            
        Returns:
            List of failed token data for analysis
        """
        async with self.lock:
            return [
                {
                    'token_data': token.token_data,
                    'error_message': token.error_message,
                    'error_type': token.error_type,
                    'scanner_name': token.scanner_name,
                    'failed_at': token.failed_at.isoformat(),
                    'retry_count': token.retry_count
                }
                for token in self.failed_tokens[:limit]
            ]

# Global dead letter queue instance
_dead_letter_queue: Optional[DeadLetterQueue] = None

async def get_dead_letter_queue() -> DeadLetterQueue:
    """Get the global dead letter queue instance."""
    global _dead_letter_queue
    if _dead_letter_queue is None:
        _dead_letter_queue = DeadLetterQueue()
        await _dead_letter_queue.load_from_storage()
    return _dead_letter_queue

async def initialize_dead_letter_queue(storage_path: str = "/tmp/dead_letter_queue.json") -> DeadLetterQueue:
    """Initialize the global dead letter queue."""
    global _dead_letter_queue
    _dead_letter_queue = DeadLetterQueue(storage_path)
    await _dead_letter_queue.load_from_storage()
    return _dead_letter_queue
