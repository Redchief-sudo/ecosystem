"""
TokenCandidate - Canonical Token Model
------------------------------------
Enforced structure for all tokens entering the decision queue.
Nothing enters the queue unless it's a TokenCandidate.

Enhanced Validation Features:
- Address validation (EVM, MEV, non-EVM formats)
- Chain validation against known registry
- Symbol validation (length, characters)
- Numeric field handling (None, 0, negative values)
- Confidence score validation (0-1 range)
- Detailed validation error reporting
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set as TypingSet, Union

from core.trace_context import TraceContext

logger = logging.getLogger(__name__)


# ============================================================================
# Token Identifier Model (Chain-Aware)
# ============================================================================

class TokenIdentifierType(Enum):
    """Supported token identifier types per chain."""
    EVM_ADDRESS = "evm_address"
    BASE58_PUBKEY = "base58_pubkey"
    BECH32 = "bech32"
    TYPE_TAG = "type_tag"
    IBC_DENOM = "ibc_denom"
    SYMBOL_ONLY = "symbol_only"  # fallback scanners


@dataclass(frozen=True)
class TokenIdentifier:
    """Chain-aware token identifier."""
    chain: str
    value: str
    id_type: TokenIdentifierType


# Chain → Identifier Type Registry (Non-negotiable for multi-network support)
CHAIN_IDENTIFIER_TYPES = {
    # EVM chains
    "ethereum": TokenIdentifierType.EVM_ADDRESS,
    "bsc": TokenIdentifierType.EVM_ADDRESS,
    "arbitrum": TokenIdentifierType.EVM_ADDRESS,
    "polygon": TokenIdentifierType.EVM_ADDRESS,
    "optimism": TokenIdentifierType.EVM_ADDRESS,
    "base": TokenIdentifierType.EVM_ADDRESS,
    "blast": TokenIdentifierType.EVM_ADDRESS,
    "avalanche": TokenIdentifierType.EVM_ADDRESS,
    "fantom": TokenIdentifierType.EVM_ADDRESS,
    "celo": TokenIdentifierType.EVM_ADDRESS,
    "linea": TokenIdentifierType.EVM_ADDRESS,
    "scroll": TokenIdentifierType.EVM_ADDRESS,
    "mantle": TokenIdentifierType.EVM_ADDRESS,
    "fuse": TokenIdentifierType.EVM_ADDRESS,
    "evmos": TokenIdentifierType.EVM_ADDRESS,
    "gnosis": TokenIdentifierType.EVM_ADDRESS,
    "moonbeam": TokenIdentifierType.EVM_ADDRESS,
    "moonriver": TokenIdentifierType.EVM_ADDRESS,
    "metis": TokenIdentifierType.EVM_ADDRESS,
    "kava": TokenIdentifierType.EVM_ADDRESS,
    "aurora": TokenIdentifierType.EVM_ADDRESS,
    "harmony": TokenIdentifierType.EVM_ADDRESS,
    "klaytn": TokenIdentifierType.EVM_ADDRESS,
    "boba": TokenIdentifierType.EVM_ADDRESS,
    "telos": TokenIdentifierType.EVM_ADDRESS,
    "thundercore": TokenIdentifierType.EVM_ADDRESS,
    "palm": TokenIdentifierType.EVM_ADDRESS,
    "manta": TokenIdentifierType.EVM_ADDRESS,
    "polygonzkevm": TokenIdentifierType.EVM_ADDRESS,
    "opbnb": TokenIdentifierType.EVM_ADDRESS,
    "syscoin": TokenIdentifierType.EVM_ADDRESS,
    "velas": TokenIdentifierType.EVM_ADDRESS,
    "zksync": TokenIdentifierType.EVM_ADDRESS,
    "arbitrumnova": TokenIdentifierType.EVM_ADDRESS,
    "cronos": TokenIdentifierType.EVM_ADDRESS,
    "oasis": TokenIdentifierType.EVM_ADDRESS,

    # Non-EVM chains
    "solana": TokenIdentifierType.BASE58_PUBKEY,
    "aptos": TokenIdentifierType.TYPE_TAG,
    "sui": TokenIdentifierType.TYPE_TAG,
    "cosmos": TokenIdentifierType.BECH32,
    "osmosis": TokenIdentifierType.BECH32,
    "ton": TokenIdentifierType.BECH32,  # TON uses bech32-like addresses
}


# ============================================================================
# Chain-Aware Validation Functions
# ============================================================================

def validate_evm_address(addr: str) -> bool:
    """Validate EVM-style address (0x followed by 40 hex chars)."""
    if not addr or not addr.startswith("0x") or len(addr) != 42:
        return False
    try:
        int(addr[2:], 16)
        return True
    except ValueError:
        return False


def validate_base58_pubkey(pubkey: str) -> bool:
    """Validate Solana-style base58 pubkey (32-44 chars)."""
    if not pubkey or len(pubkey) < 32 or len(pubkey) > 44:
        return False
    base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(c in base58_chars for c in pubkey)


def validate_bech32_address(addr: str) -> bool:
    """Validate Bech32-style address."""
    if not addr or len(addr) < 10:
        return False
    # Basic bech32 validation - starts with prefix and contains '1'
    return "1" in addr and not addr.startswith("0x")


def validate_type_tag(tag: str) -> bool:
    """Validate type tag (for Aptos/Sui)."""
    if not tag or len(tag) < 5:
        return False
    # Type tags typically contain '::'
    return "::" in tag


def validate_ibc_denom(denom: str) -> bool:
    """Validate IBC denomination."""
    if not denom or not denom.startswith("ibc/"):
        return False
    # IBC denoms are ibc/ followed by hex
    try:
        int(denom[4:], 16)
        return True
    except ValueError:
        return False


def validate_identifier(identifier: TokenIdentifier) -> None:
    """Validate identifier against its expected type."""
    expected_type = CHAIN_IDENTIFIER_TYPES.get(identifier.chain)
    if expected_type is None:
        # For unknown chains, just validate the address format for its detected type
        logger.debug(f"Validating address for unknown chain '{identifier.chain}' with detected type {identifier.id_type.value}")
    else:
        # For known chains, we can be more strict but still allow mismatches
        if identifier.id_type != expected_type:
            logger.debug(f"Identifier type mismatch for {identifier.chain}: expected {expected_type.value}, got {identifier.id_type.value}")

    # Type-specific validation (always validate the address format)
    if identifier.id_type == TokenIdentifierType.EVM_ADDRESS:
        if not validate_evm_address(identifier.value):
            raise ValueError(f"Invalid EVM address: {identifier.value}")
    elif identifier.id_type == TokenIdentifierType.BASE58_PUBKEY:
        if not validate_base58_pubkey(identifier.value):
            raise ValueError(f"Invalid base58 pubkey: {identifier.value}")
    elif identifier.id_type == TokenIdentifierType.BECH32:
        if not validate_bech32_address(identifier.value):
            raise ValueError(f"Invalid bech32 address: {identifier.value}")
    elif identifier.id_type == TokenIdentifierType.TYPE_TAG:
        if not validate_type_tag(identifier.value):
            raise ValueError(f"Invalid type tag: {identifier.value}")
    elif identifier.id_type == TokenIdentifierType.IBC_DENOM:
        if not validate_ibc_denom(identifier.value):
            raise ValueError(f"Invalid IBC denom: {identifier.value}")


def detect_address_type(address: str) -> TokenIdentifierType:
    """Auto-detect address type based on format."""
    if validate_evm_address(address):
        return TokenIdentifierType.EVM_ADDRESS
    elif validate_base58_pubkey(address):
        return TokenIdentifierType.BASE58_PUBKEY
    elif validate_bech32_address(address):
        return TokenIdentifierType.BECH32
    elif validate_type_tag(address):
        return TokenIdentifierType.TYPE_TAG
    elif validate_ibc_denom(address):
        return TokenIdentifierType.IBC_DENOM
    else:
        # Default to EVM address for backwards compatibility
        logger.warning(f"Could not detect address type for {address[:10]}..., defaulting to EVM_ADDRESS")
        return TokenIdentifierType.EVM_ADDRESS


def is_address_compatible_with_chain(address: str, chain: str) -> bool:
    """Check if address format is compatible with the expected chain type."""
    expected_type = CHAIN_IDENTIFIER_TYPES.get(chain)
    if expected_type is None:
        return True  # Unknown chain, assume compatible
    
    if expected_type == TokenIdentifierType.EVM_ADDRESS:
        return validate_evm_address(address)
    elif expected_type == TokenIdentifierType.BASE58_PUBKEY:
        return validate_base58_pubkey(address)
    elif expected_type == TokenIdentifierType.BECH32:
        return validate_bech32_address(address)
    elif expected_type == TokenIdentifierType.TYPE_TAG:
        return validate_type_tag(address)
    elif expected_type == TokenIdentifierType.IBC_DENOM:
        return validate_ibc_denom(address)
    
    return True


def build_token_identifier(chain: str, address: str) -> TokenIdentifier:
    """Build a validated TokenIdentifier from chain and address."""
    normalized_chain = normalize_chain(chain)
    id_type = CHAIN_IDENTIFIER_TYPES.get(normalized_chain)

    # Auto-detect address type if chain is not supported or ambiguous
    if id_type is None:
        id_type = detect_address_type(address.strip())
        logger.warning(f"Auto-detected address type {id_type.value} for address {address.strip()[:10]}... on unknown chain '{chain}'")
    
    # If we have a known chain but the address doesn't match the expected type, 
    # try to auto-detect and warn about the mismatch
    elif not is_address_compatible_with_chain(address.strip(), normalized_chain):
        detected_type = detect_address_type(address.strip())
        logger.warning(f"Address type mismatch for chain {normalized_chain}: expected {CHAIN_IDENTIFIER_TYPES[normalized_chain].value}, detected {detected_type.value}")
        # Use the detected type for better compatibility
        id_type = detected_type

    identifier = TokenIdentifier(
        chain=normalized_chain,
        value=address.strip(),
        id_type=id_type
    )

    validate_identifier(identifier)
    return identifier


# ============================================================================
# Known Chains Registry
# ============================================================================

# All supported chains (both ID and name formats)
KNOWN_CHAINS: TypingSet[str] = {
    # Mainnets by ID
    "1",
    "56",
    "137",
    "42161",
    "10",
    "43114",
    "250",
    "42220",
    "42262",
    "25",
    "100",
    "1284",
    "1088",
    "2222",
    "1313161554",
    "1666600000",
    "8217",
    "122",
    "9001",
    "288",
    "235",
    "40",
    "19",
    "11297108109",
    "534352",
    "169",
    "5000",
    "1101",
    "204",
    "81457",
    "59144",
    "560350",
    "128",
    "324",
    "42170",
    "8453",
    # Mainnets by name
    "ethereum",
    "bsc",
    "polygon",
    "arbitrum",
    "optimism",
    "avalanche",
    "fantom",
    "celo",
    "oasis",
    "cronos",
    "linea",
    "base",
    "scroll",
    "mantle",
    "blast",
    "fuse",
    "evmos",
    "gnosis",
    "moonbeam",
    "moonriver",
    "metis",
    "kava",
    "aurora",
    "harmony",
    "klaytn",
    "boba",
    "telos",
    "thundercore",
    "palm",
    "manta",
    "polygonzkevm",
    "opbnb",
    "syscoin",
    "velas",
    "zksync",
    "arbitrumnova",
    "cronos",
    "oasis",
    "solana",  # Add Solana to known chains
    # Testnets
    "sepolia",
    "goerli",
    "testnet",
    "bsc_testnet",
    "mumbai",
    "arbitrum_sepolia",
    "optimism_sepolia",
    "avalanche_fuji",
}

# Chain ID to name mapping
CHAIN_ID_TO_NAME: Dict[str, str] = {
    "1": "ethereum",
    "56": "bsc",
    "137": "polygon",
    "42161": "arbitrum",
    "10": "optimism",
    "43114": "avalanche",
    "250": "fantom",
    "42220": "celo",
    "42262": "oasis",
    "25": "cronos",
    "59144": "linea",
    "8453": "base",
    "534352": "scroll",
    "5000": "mantle",
    "81457": "blast",
    "122": "fuse",
    "9001": "evmos",
    "100": "gnosis",
    "1284": "moonbeam",
    "1285": "moonriver",
    "1088": "metis",
    "2222": "kava",
}

# Valid chain prefixes for MEV addresses
MEV_CHAINS: TypingSet[str] = {
    "linea",
    "oasis",
    "fuse",
    "mantle",
    "evmos",
    "scroll",
    "polygon",
    "bsc",
    "blast",
    "ethereum",
    "arbitrum",
    "optimism",
    "base",
    "celo",
}

# Valid symbol characters (alphanumeric and common symbols)
VALID_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9$]+$")

# Maximum lengths
MAX_SYMBOL_LENGTH = 20
MAX_NAME_LENGTH = 100
MAX_ADDRESS_LENGTH = 100


# ============================================================================
# Validation Utilities
# ============================================================================

def is_valid_evm_address(address: str) -> bool:
    """Validate EVM-style address (0x followed by 40 hex chars)."""
    if not address:
        return False
    pattern = r"^0x[a-fA-F0-9]{40}$"
    return bool(re.match(pattern, address))


def is_valid_mev_address(address: str) -> bool:
    """Validate MEV-style address (mev_chain-token-timestamp format)."""
    if not address:
        return False

    # Expected: mev_<chain>-<token>-<timestamp>
    # Example: mev_front-ethereum-0xabc...-1670000000
    pattern = r"^mev_[a-zA-Z0-9_]+-[a-zA-Z0-9]+-\d+$"
    if not re.match(pattern, address):
        return False

    # Validate chain part separately for stricter validation
    parts = address.split("-")
    if len(parts) != 3:
        return False

    chain_part = parts[0].replace("mev_", "")
    return chain_part in MEV_CHAINS


def is_valid_solana_address(address: str) -> bool:
    """Validate Solana-style address (base58 encoded, 32-44 chars)."""
    if not address:
        return False
    if len(address) < 32 or len(address) > 44:
        return False
    base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(c in base58_chars for c in address)


def is_valid_address(address: str) -> bool:
    """Validate token address in any supported format."""
    if not address:
        return False

    normalized = address.strip()

    if is_valid_evm_address(normalized):
        return True

    if is_valid_mev_address(normalized):
        return True

    if is_valid_solana_address(normalized):
        return True

    # Fallback: allow non-standard addresses that are reasonably long to avoid false rejects
    if 8 <= len(normalized) <= MAX_ADDRESS_LENGTH:
        logger.warning(f"Non-standard address format accepted: {normalized[:20]}...")
        return True

    return False


def is_valid_chain(chain: str) -> bool:
    """Validate chain name against known registry."""
    if not chain:
        return False

    normalized = chain.strip().lower()

    # Direct match
    if normalized in KNOWN_CHAINS:
        return True

    # Chain ID conversion match
    if normalized in CHAIN_ID_TO_NAME:
        return True

    return False


def normalize_chain(chain: str) -> str:
    """Normalize chain name to canonical form."""
    if not chain:
        return ""

    normalized = chain.strip().lower()

    if normalized in CHAIN_ID_TO_NAME:
        return CHAIN_ID_TO_NAME[normalized]

    return normalized


def is_valid_symbol(symbol: str) -> bool:
    """Validate token symbol."""
    if not symbol:
        return False

    normalized = symbol.strip().upper()

    if len(normalized) < 1 or len(normalized) > MAX_SYMBOL_LENGTH:
        return False

    if not VALID_SYMBOL_PATTERN.match(normalized):
        return False

    return True


def normalize_symbol(symbol: str) -> str:
    """Normalize token symbol to uppercase."""
    if not symbol:
        return ""
    return symbol.strip().upper()


def is_valid_price(price: Optional[float]) -> bool:
    """Validate price value."""
    if price is None:
        return True
    if isinstance(price, (int, float)):
        return price > 0 and price < 1_000_000
    return False


def is_valid_liquidity(liquidity: Optional[float]) -> bool:
    """Validate liquidity value."""
    if liquidity is None:
        return True
    if isinstance(liquidity, (int, float)):
        return liquidity >= 0
    return False


def is_valid_volume(volume: Optional[float]) -> bool:
    """Validate 24h volume value."""
    if volume is None:
        return True
    if isinstance(volume, (int, float)):
        return volume >= 0
    return False


def is_valid_market_cap(market_cap: Optional[float]) -> bool:
    """Validate market cap value."""
    if market_cap is None:
        return True
    if isinstance(market_cap, (int, float)):
        return market_cap >= 0
    return False


def is_valid_confidence(confidence: float) -> bool:
    """Validate confidence score is in valid range [0, 1]."""
    return isinstance(confidence, (int, float)) and 0 <= confidence <= 1


def normalize_confidence(confidence: float) -> float:
    """Normalize confidence to [0, 1] range with warning for out-of-bounds values."""
    if not isinstance(confidence, (int, float)):
        return 0.0

    normalized = max(0.0, min(1.0, float(confidence)))

    if confidence < 0 or confidence > 1:
        logger.warning(f"Confidence {confidence} out of bounds [0, 1], normalized to {normalized}")

    return normalized


def is_valid_decimals(decimals: Any) -> bool:
    """Validate decimals (must be int >= 0 and <= 36)."""
    if not isinstance(decimals, int):
        return False
    return 0 <= decimals <= 36


# ============================================================================
# TokenCandidate Class
# ============================================================================

@dataclass
class TokenCandidate:
    """Canonical token contract - non-negotiable structure."""

    # Core identity (required)
    chain: str
    address: str
    symbol: str
    name: str
    decimals: int  # Token decimals - REQUIRED for validation
    source: str  # "dexscreener", "cmc", "mempool", etc
    discovered_at: datetime

    # Market data (can be None)
    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None

    # Metadata with defaults
    confidence: float = 0.0  # pre-AI score
    enrichment_only: bool = False  # True for CMC tokens during transition
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional data fields
    
    # Distributed tracing
    trace_ctx: TraceContext = field(default_factory=TraceContext)

    def __post_init__(self):
        """Validate token candidate after initialization and normalize fields."""
        self.chain = normalize_chain(self.chain)
        self.address = self.address.strip().lower()
        self.symbol = normalize_symbol(self.symbol)
        self.name = self.name.strip() if self.name else self.symbol
        self.confidence = normalize_confidence(self.confidence)

        # Strict chain-aware validation - no more lenient fallbacks
        try:
            build_token_identifier(self.chain, self.address)
        except ValueError as e:
            raise ValueError(f"TokenCandidate validation failed: {e}")

        # Additional field validations
        errors = self.get_validation_errors(raise_on_error=False)
        critical_errors = [e for e in errors if e["severity"] == "error"]

        if critical_errors:
            error_messages = "; ".join(e["message"] for e in critical_errors)
            raise ValueError(f"TokenCandidate validation failed: {error_messages}")

    def get_validation_errors(self, raise_on_error: bool = False) -> List[Dict[str, str]]:
        """
        Get detailed validation errors.

        Args:
            raise_on_error: If True, raise ValueError on first error

        Returns:
            List of error dictionaries with 'field', 'message', and 'severity'
        """
        errors: List[Dict[str, str]] = []

        # 1. Address validation
        if not self.address:
            errors.append({"field": "address", "message": "Address is required", "severity": "error"})
        elif not is_valid_address(self.address):
            errors.append(
                {"field": "address", "message": f"Invalid address format: {self.address[:20]}...", "severity": "error"}
            )

        # 2. Chain validation
        if not self.chain:
            errors.append({"field": "chain", "message": "Chain is required", "severity": "error"})
        elif not is_valid_chain(self.chain):
            errors.append({"field": "chain", "message": f"Unknown chain: {self.chain}", "severity": "error"})

        # 3. Symbol validation
        if not self.symbol:
            errors.append({"field": "symbol", "message": "Symbol is required", "severity": "error"})
        elif len(self.symbol) > MAX_SYMBOL_LENGTH:
            errors.append(
                {"field": "symbol", "message": f"Symbol too long (max {MAX_SYMBOL_LENGTH} chars): {self.symbol}", "severity": "error"}
            )
        elif not VALID_SYMBOL_PATTERN.match(self.symbol):
            errors.append({"field": "symbol", "message": f"Invalid symbol characters: {self.symbol}", "severity": "error"})

        # 4. Name validation
        if not self.name:
            errors.append({"field": "name", "message": "Name is required", "severity": "error"})
        elif len(self.name) > MAX_NAME_LENGTH:
            errors.append({"field": "name", "message": f"Name too long (max {MAX_NAME_LENGTH} chars)", "severity": "error"})

        # 5. Source validation
        if not self.source:
            errors.append({"field": "source", "message": "Source is required", "severity": "error"})

        # 6. Decimals validation
        if not is_valid_decimals(self.decimals):
            errors.append({"field": "decimals", "message": f"Invalid decimals: {self.decimals}", "severity": "error"})

        # 7. Numeric field validations
        if not is_valid_price(self.price_usd):
            errors.append({"field": "price_usd", "message": f"Invalid price: {self.price_usd}", "severity": "error"})

        if not is_valid_liquidity(self.liquidity_usd):
            errors.append({"field": "liquidity_usd", "message": f"Invalid liquidity: {self.liquidity_usd}", "severity": "error"})

        if not is_valid_volume(self.volume_24h):
            errors.append({"field": "volume_24h", "message": f"Invalid volume: {self.volume_24h}", "severity": "error"})

        if not is_valid_market_cap(self.market_cap):
            errors.append({"field": "market_cap", "message": f"Invalid market cap: {self.market_cap}", "severity": "error"})

        # 8. Confidence validation
        if not is_valid_confidence(self.confidence):
            errors.append(
                {"field": "confidence", "message": f"Confidence out of bounds [0, 1]: {self.confidence}", "severity": "error"}
            )

        # 9. datetime validation
        if not isinstance(self.discovered_at, datetime):
            errors.append({"field": "discovered_at", "message": "discovered_at must be a datetime object", "severity": "error"})

        if raise_on_error and errors:
            error_messages = "; ".join(e["message"] for e in errors)
            raise ValueError(f"TokenCandidate validation failed: {error_messages}")

        return errors

    def is_valid_candidate(self) -> bool:
        """Check if token meets basic validation criteria."""
        try:
            if not self.chain or not self.address or not self.symbol or not self.name or not self.source:
                return False
            if not isinstance(self.discovered_at, datetime):
                return False
            if not is_valid_address(self.address):
                return False
            if not is_valid_chain(self.chain):
                return False
            if not is_valid_symbol(self.symbol):
                return False
            if not is_valid_decimals(self.decimals):
                return False
            if self.price_usd is not None and not is_valid_price(self.price_usd):
                return False
            if self.liquidity_usd is not None and not is_valid_liquidity(self.liquidity_usd):
                return False
            if self.volume_24h is not None and not is_valid_volume(self.volume_24h):
                return False
            if self.market_cap is not None and not is_valid_market_cap(self.market_cap):
                return False
            if not is_valid_confidence(self.confidence):
                return False
            return True
        except Exception:
            return False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "chain": self.chain,
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            "source": self.source,
            "discovered_at": self.discovered_at.isoformat(),
            "price_usd": self.price_usd,
            "liquidity_usd": self.liquidity_usd,
            "volume_24h": self.volume_24h,
            "market_cap": self.market_cap,
            "confidence": self.confidence,
            "enrichment_only": self.enrichment_only,
        }

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of the token candidate for logging."""
        return {
            "chain": self.chain,
            "address": f"{self.address[:10]}...{self.address[-6:]}" if len(self.address) > 20 else self.address,
            "symbol": self.symbol,
            "name": self.name[:30] if len(self.name) > 30 else self.name,
            "source": self.source,
            "price_usd": self.price_usd,
            "liquidity_usd": self.liquidity_usd,
            "volume_24h": self.volume_24h,
            "confidence": self.confidence,
            "is_valid": self.is_valid_candidate(),
            "validation_errors": len(self.get_validation_errors()),
        }

    def to_frozen(self) -> "FrozenTokenCandidate":
        """Create an immutable snapshot for queueing to prevent downstream mutation."""
        return FrozenTokenCandidate(
            chain=self.chain,
            address=self.address,
            symbol=self.symbol,
            name=self.name,
            decimals=self.decimals,
            source=self.source,
            discovered_at=self.discovered_at,
            price_usd=self.price_usd,
            liquidity_usd=self.liquidity_usd,
            volume_24h=self.volume_24h,
            market_cap=self.market_cap,
            confidence=self.confidence,
            enrichment_only=self.enrichment_only,
            trace_ctx=self.trace_ctx,
        )


@dataclass(frozen=True)
class FrozenTokenCandidate:
    """Immutable snapshot of TokenCandidate for safe queueing."""
    chain: str
    address: str
    symbol: str
    name: str
    decimals: int
    source: str
    discovered_at: datetime
    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    confidence: float = 0.0
    enrichment_only: bool = False
    trace_ctx: TraceContext = field(default_factory=TraceContext)


def create_token_candidate(
    chain: str,
    address: str,
    symbol: str,
    name: str,
    decimals: int,
    source: str,
    discovered_at: datetime,
    price_usd: Optional[float] = None,
    liquidity_usd: Optional[float] = None,
    volume_24h: Optional[float] = None,
    market_cap: Optional[float] = None,
    confidence: float = 0.0,
    enrichment_only: bool = False,
) -> TokenCandidate:
    """Factory function to create TokenCandidate with validation."""
    return TokenCandidate(
        chain=chain,
        address=address,
        symbol=symbol,
        name=name,
        decimals=decimals,
        source=source,
        discovered_at=discovered_at,
        price_usd=price_usd,
        liquidity_usd=liquidity_usd,
        volume_24h=volume_24h,
        market_cap=market_cap,
        confidence=confidence,
        enrichment_only=enrichment_only,
    )

