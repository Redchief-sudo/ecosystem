# utils/memory_tracker.py
import time
from typing import Any, Dict, List, Optional, Set


class MemoryTracker:
    """Base memory tracking functionality."""
    
    def __init__(self):
        self.market_snapshots = {}
        self.blacklist = set()
        self.positions = {}
        self.recent_tokens = {}
        self.store = {}
        self._initialized = True

    def update_market_snapshot(self, chain, token, data):
        """Store snapshot for future AI/exit/risk decisions."""
        if chain not in self.market_snapshots:
            self.market_snapshots[chain] = {}

        self.market_snapshots[chain][token] = {
            "timestamp": time.time(),
            "data": data
        }

    def is_token_blacklisted(self, token_address, *args, **kwargs):
        """Simple global blacklist check."""
        return token_address.lower() in {addr.lower() for addr in self.blacklist}
        
    def store_recent_tokens(self, chain, tokens):
        """Store recently scanned tokens for the given chain."""
        if not hasattr(self, 'recent_tokens'):
            self.recent_tokens = {}
            
        if chain not in self.recent_tokens:
            self.recent_tokens[chain] = []
        
        # Store token objects
        self.recent_tokens[chain].extend(tokens)
        
        # Keep only the most recent 100 tokens per chain
        self.recent_tokens[chain] = self.recent_tokens[chain][-100:]
        
    def get_recent_tokens(self, chain, max_tokens=20):
        """Get recently scanned tokens for the given chain."""
        if not hasattr(self, 'recent_tokens') or chain not in self.recent_tokens:
            return []
            
        # Return the most recent tokens (up to max_tokens)
        return self.recent_tokens[chain][-max_tokens:]
        
    async def initialize(self):
        """Initialize the memory tracker."""
        if not hasattr(self, '_initialized') or not self._initialized:
            self.market_snapshots = {}
            self.blacklist = set()
            self.positions = {}
            self.recent_tokens = {}
            self.store = {}
            self._initialized = True
            
        return self

    def record_position(self, chain, token, position_data):
        """Record position data for a token."""
        if chain not in self.positions:
            self.positions[chain] = {}

        self.positions[chain][token] = position_data

    def get_position(self, chain, token):
        """Get position data for a token."""
        return self.positions.get(chain, {}).get(token)

    async def close(self):
        """Clean up resources."""
        pass
