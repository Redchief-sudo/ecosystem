"""
Token data validation and normalization.
"""
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum

class TokenStandard(str, Enum):
    ERC20 = "ERC20"
    BEP20 = "BEP20"
    ERC721 = "ERC721"
    ERC1155 = "ERC1155"
    SPL = "SPL"  # Solana
    TRC20 = "TRC20"  # TRON

@dataclass
class TokenMetadata:
    """Standardized token metadata with validation."""
    # Required fields
    address: str
    symbol: str
    name: str
    decimals: int
    chain: str
    status: str = "active"  # Added status field
    
    # Price and market data
    price: float = 0.0
    price_confidence: str = "low"  # low, medium, high
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    market_cap: Optional[float] = None
    
    # Additional fields for MemoryManager compatibility
    holders: Optional[int] = None
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    strength: float = 0.0
    zscore: float = 0.0
    ai_score: float = 0.0
    momentum: Dict[str, float] = field(default_factory=lambda: {"5m": 0.0, "1h": 0.0, "24h": 0.0})
    volatility: float = 0.0
    
    # Timestamps
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    last_updated: Optional[int] = None  # For MemoryManager compatibility
    
    # Additional metadata
    pair_address: Optional[str] = None
    exchange: Optional[str] = None
    is_vulnerable: bool = False
    tags: List[str] = field(default_factory=list)
    standard: TokenStandard = TokenStandard.ERC20
    total_supply: Optional[int] = None
    circulating_supply: Optional[int] = None
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    discord: Optional[str] = None
    github: Optional[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        """Validate fields after initialization."""
        self._validate_address()
        self._validate_symbol()
        self._validate_decimals()
        self._normalize_fields()
        
    def _validate_address(self):
        """Validate token address based on chain or auto-detect format."""
        if not self.address:
            raise ValueError("Token address is required")
        
        # Auto-detect address format if chain is unknown or ambiguous
        detected_format = self._detect_address_format(self.address)
        
        # EVM address validation
        if self.chain in ['ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 'avalanche', 'fantom', 'base', 'zksync_era', 'scroll', 'linea']:
            if not (self.address.startswith('0x') and 
                len(self.address) >= 40 and len(self.address) <= 42 and 
                all(c in '0123456789abcdefABCDEF' for c in self.address[2:])):
                raise ValueError(f"Invalid EVM address format: {self.address}")
        
        # Solana address validation
        elif self.chain == 'solana':
            if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', self.address):
                raise ValueError(f"Invalid Solana address format: {self.address}")
        
        # TRON address validation
        elif self.chain == 'tron':
            if not re.match(r'^T[a-zA-Z0-9]{33}$', self.address):
                raise ValueError(f"Invalid TRON address format: {self.address}")
        
        # Auto-validation for unknown chains - use detected format
        elif detected_format == 'evm':
            if not (self.address.startswith('0x') and 
                len(self.address) >= 40 and len(self.address) <= 42 and 
                all(c in '0123456789abcdefABCDEF' for c in self.address[2:])):
                raise ValueError(f"Invalid EVM address format: {self.address}")
        
        elif detected_format == 'solana':
            if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', self.address):
                raise ValueError(f"Invalid Solana address format: {self.address}")
        
        elif detected_format == 'tron':
            if not re.match(r'^T[a-zA-Z0-9]{33}$', self.address):
                raise ValueError(f"Invalid TRON address format: {self.address}")
        
        # If format is unknown, be permissive but log warning
        else:
            # Accept the address but this could be enhanced with more validation
            pass
    
    def _detect_address_format(self, address: str) -> str:
        """Detect address format."""
        # EVM address
        if (address.startswith('0x') and 
            len(address) >= 40 and len(address) <= 42 and 
            all(c in '0123456789abcdefABCDEF' for c in address[2:])):
            return 'evm'
        
        # Solana address (base58)
        if re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
            return 'solana'
        
        # TRON address
        if re.match(r'^T[a-zA-Z0-9]{33}$', address):
            return 'tron'
        
        return 'unknown'
    
    def _validate_symbol(self):
        """Validate token symbol."""
        if not self.symbol or len(self.symbol) > 20:
            raise ValueError("Symbol must be 1-20 characters long")
        if not re.match(r'^[A-Za-z0-9]+$', self.symbol):
            raise ValueError("Symbol must contain only letters and numbers")
    
    def _validate_decimals(self):
        """Validate token decimals."""
        if not (0 <= self.decimals <= 36):
            raise ValueError("Decimals must be between 0 and 36")
    
    def _normalize_fields(self):
        """Normalize string fields."""
        self.symbol = self.symbol.upper() if self.symbol else ''
        self.name = self.name.strip() if self.name else ''
        # Don't lowercase address - preserve checksum for EVM addresses
        if self.chain in ['solana', 'tron']:
            # Only lowercase non-EVM addresses
            self.address = self.address.lower() if self.address else ''
        else:
            # Keep original case for EVM addresses (preserves checksum)
            self.address = self.address.strip() if self.address else ''
        self.tags = [tag.lower().strip() for tag in self.tags if tag.strip()]
        
        # Ensure price and market data are non-negative
        self.price = max(0.0, float(self.price))
        self.liquidity_usd = max(0.0, float(self.liquidity_usd))
        self.volume_24h = max(0.0, float(self.volume_24h))
        
        # Ensure timestamps are positive
        current_time = int(time.time())
        self.created_at = max(0, int(self.created_at))
        self.updated_at = max(current_time, int(self.updated_at))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenMetadata':
        """Create TokenMetadata from dictionary with validation."""
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__annotations__
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper type conversion."""
        result = {}
        for field_name, field_type in self.__annotations__.items():
            value = getattr(self, field_name)
            
            # Handle special cases
            if field_name == 'standard' and value is not None:
                value = value.value
            elif field_name in ['created_at', 'updated_at'] and value is not None:
                value = int(value)
            
            result[field_name] = value
        return result
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update token data with validation."""
        for key, value in data.items():
            if key in self.__annotations__:
                setattr(self, key, value)
        self.updated_at = int(time.time())
        self.__post_init__()  # Re-validate after update

def validate_token_data(data: Dict[str, Any], required_fields: List[str] = None) -> Tuple[bool, str]:
    """
    Validate token data against required fields and basic formatting.
    
    Args:
        data: Token data to validate
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if required_fields is None:
        required_fields = ['address', 'symbol', 'name', 'decimals', 'chain']
    
    # Check required fields
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    
    # Check address format if present
    if 'address' in data and data['address']:
        try:
            # Auto-detect chain if not provided or if there's a clear format mismatch
            chain = data.get('chain', '')
            address = data['address']
            
            # Detect address format
            temp_token = TokenMetadata(
                address=address,
                symbol=data.get('symbol', 'TEMP'),
                name=data.get('name', 'Temporary'),
                decimals=data.get('decimals', 18),
                chain='unknown'  # Will trigger auto-detection
            )
            detected_format = temp_token._detect_address_format(address)
            
            # Check for chain/address format mismatches and override if necessary
            if chain:
                if detected_format == 'solana' and chain in ['ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 'avalanche', 'fantom', 'base']:
                    # Solana address on EVM chain - override to solana
                    chain = 'solana'
                elif detected_format == 'evm' and chain == 'solana':
                    # EVM address on Solana chain - override to ethereum
                    chain = 'ethereum'
                elif detected_format == 'tron' and chain in ['ethereum', 'bsc', 'polygon']:
                    # TRON address on EVM chain - override to tron
                    chain = 'tron'
            else:
                # No chain provided - use detected format
                if detected_format == 'solana':
                    chain = 'solana'
                elif detected_format == 'tron':
                    chain = 'tron'
                elif detected_format == 'evm':
                    chain = 'ethereum'
                else:
                    chain = 'unknown'
            
            temp_token = TokenMetadata(
                address=address,
                symbol=data.get('symbol', 'TEMP'),
                name=data.get('name', 'Temporary'),
                decimals=data.get('decimals', 18),
                chain=chain
            )
        except ValueError as e:
            return False, f"Invalid token data: {str(e)}"
    
    return True, "Valid token data"
