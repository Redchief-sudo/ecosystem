import os
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Set up logger
logger = logging.getLogger(__name__)

# =============================================================================
# Data models (local to avoid circular imports)
# =============================================================================

class TokenStatus:
    """Token status enumeration for tracking token lifecycle."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"
    PENDING = "pending"


# =============================================================================
# Memory Manager
# =============================================================================

class SimplePathManager:
    """Simple path manager for memory operations."""
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        
    def get_memory_db_path(self) -> str:
        return str(self.base_path / "ecosystem.db")
        
    def get_memory_persist_path(self) -> str:
        return str(self.base_path / "memory_persist.json")


class SimpleTokenMetadata:
    """Simple token metadata for memory operations."""
    def __init__(self, address: str, symbol: str = "", decimals: int = 18, price: float = None, volume_24h: float = None, liquidity_usd: float = None, chain: str = None):
        self.address = address
        self.symbol = symbol
        self.decimals = decimals
        self.price = price
        self.volume_24h = volume_24h
        self.liquidity_usd = liquidity_usd
        self.chain = chain


class MemoryManager:
    """SQLite-backed token memory with in-memory cache."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        persist_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or {}
        self.path_manager = SimplePathManager()
        self.db_path = db_path or self.path_manager.get_memory_db_path()
        self.persist_path = persist_path or self.path_manager.get_memory_persist_path()

        self.tokens: Dict[str, SimpleTokenMetadata] = {}
        self.blacklist: Set[str] = set()
        self.metadata: Dict[str, Any] = {}

        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        # Ensure parent directory exists; handle in-memory DB specially
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            address TEXT PRIMARY KEY,
            metadata TEXT,
            status TEXT,
            last_seen TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()

    # Minimal methods to satisfy tests
    def add(self, address: str, metadata: dict = None) -> None:
        """Add or update a token."""
        if metadata is None:
            metadata = {}
        self.tokens[address] = SimpleTokenMetadata(
            address=address,
            symbol=metadata.get("symbol", ""),
            decimals=metadata.get("decimals", 18),
            price=metadata.get("price"),
            volume_24h=metadata.get("volume_24h"),
            liquidity_usd=metadata.get("liquidity_usd"),
            chain=metadata.get("chain")
        )
        # Persist to DB only if not in-memory
        if self.db_path != ":memory:":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tokens (address, metadata, status, last_seen)
                VALUES (?, ?, ?, ?)
            """, (address, json.dumps(metadata), TokenStatus.ACTIVE, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()

    def add_token(self, token_data: dict) -> bool:
        """Add token from dict format used by tests."""
        address = token_data.get('address')
        if not address:
            return False
        metadata = {
            'symbol': token_data.get('symbol', ''),
            'decimals': token_data.get('decimals', 18),
            'chain': token_data.get('chain'),
            'price': token_data.get('price'),
            'volume_24h': token_data.get('volume_24h'),
            'liquidity_usd': token_data.get('liquidity_usd'),
        }
        self.add(address, metadata)
        return True

    def get(self, address: str) -> Optional[SimpleTokenMetadata]:
        """Get token metadata."""
        return self.tokens.get(address)

    def get_token(self, address: str) -> Optional['SimpleTokenMetadata']:
        """Get token metadata object for tests."""
        return self.tokens.get(address)

    def remove(self, address: str) -> None:
        """Remove a token."""
        self.tokens.pop(address, None)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE address = ?", (address,))
        conn.commit()
        conn.close()

    # Test helper / introspection
    def get_admission_stats(self) -> dict:
        """Return basic stats for tests."""
        return {
            "tokens_count": len(self.tokens),
            "blacklist_count": len(self.blacklist),
            "db_path": self.db_path,
            "persist_path": self.persist_path,
        }

    async def health_check(self):
        """Return health status for tests."""
        from core.health_check import HealthStatus
        # Degraded if no tokens present
        status = len(self.tokens) > 0
        return HealthStatus(
            component="MemoryManager",
            status=status,
            message="MemoryManager operational" if status else "No tokens loaded",
            metrics={
                "token_count": len(self.tokens),
                "blacklist_count": len(self.blacklist),
                "db_path": self.db_path,
            }
        )

    def close(self):
        """No-op for in-memory; close DB connection if persistent."""
        pass
