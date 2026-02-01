"""
Rugpull Detector
----------------
Detects potential rugpull risks by analyzing smart contract properties.
Checks contract ownership, liquidity locks, and token characteristics.
"""

import logging
from typing import Dict, Optional, Tuple
from web3 import Web3
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk assessment levels."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RugpullDetector:
    """
    Detect potential rugpull and honeypot risks in tokens.
    """
    
    def __init__(self, w3: Web3):
        """
        Initialize rugpull detector.
        
        Args:
            w3: Web3 instance
        """
        self.w3 = w3
        
        # Common rugpull patterns
        self.suspicious_functions = [
            "emergencyWithdraw",
            "withdraw",
            "sweep",
            "drain",
            "pause",
            "burn"
        ]
    
    async def check_token_contract(self, token_address: str) -> Tuple[RiskLevel, Dict]:
        """
        Check token contract for rugpull indicators.
        
        Args:
            token_address: Token contract address
            
        Returns:
            Tuple of (risk_level, details_dict)
        """
        details = {
            "token": token_address,
            "checks": {}
        }
        
        risk_score = 0  # 0-10 scale
        
        try:
            token_address = Web3.to_checksum_address(token_address)
        except Exception as e:
            logger.error(f"Invalid token address: {e}")
            return RiskLevel.CRITICAL, {"error": "Invalid address", **details}
        
        # Check 1: Contract code existence
        code = await self.w3.eth.get_code(token_address)
        if code == b"":
            logger.warning(f"❌ Token {token_address} is not a contract (EOA)")
            risk_score += 3
            details["checks"]["is_contract"] = False
        else:
            details["checks"]["is_contract"] = True
        
        # Check 2: Owner renounced
        renounced = await self._check_ownership_renounced(token_address)
        if renounced is None:
            details["checks"]["ownership_renounced"] = "unknown"
        elif not renounced:
            logger.warning(f"⚠️ Token {token_address} has active owner - rugpull risk")
            risk_score += 2
            details["checks"]["ownership_renounced"] = False
        else:
            details["checks"]["ownership_renounced"] = True
        
        # Check 3: Liquidity locked
        locked = await self._check_liquidity_locked(token_address)
        if locked is None:
            details["checks"]["liquidity_locked"] = "unknown"
        elif not locked:
            logger.warning(f"⚠️ Token {token_address} liquidity may not be locked - rugpull risk")
            risk_score += 2
            details["checks"]["liquidity_locked"] = False
        else:
            details["checks"]["liquidity_locked"] = True
        
        # Check 4: Honeypot detection (buy/sell tax)
        honeypot = await self._check_honeypot_tax(token_address)
        if honeypot:
            logger.error(f"❌ Token {token_address} appears to be a honeypot (high tax/blocks sell)")
            risk_score += 4
            details["checks"]["honeypot"] = True
        else:
            details["checks"]["honeypot"] = False
        
        # Check 5: Suspicious functions
        suspicious = await self._check_suspicious_functions(token_address)
        if suspicious:
            logger.warning(f"⚠️ Token {token_address} has suspicious functions: {suspicious}")
            risk_score += len(suspicious)
            details["checks"]["suspicious_functions"] = suspicious
        else:
            details["checks"]["suspicious_functions"] = []
        
        # Check 6: High concentration risk
        concentration = await self._check_holder_concentration(token_address)
        if concentration is not None and concentration > 0.5:
            logger.warning(f"⚠️ Token {token_address} has high holder concentration: {concentration:.1%}")
            risk_score += 2
            details["checks"]["holder_concentration"] = concentration
        else:
            details["checks"]["holder_concentration"] = concentration
        
        # Determine risk level
        if risk_score >= 9:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 7:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 5:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 2:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.SAFE
        
        details["risk_score"] = risk_score
        details["risk_level"] = risk_level.value
        
        logger.info(f"Token {token_address} risk assessment: {risk_level.value.upper()} (score: {risk_score}/10)")
        
        return risk_level, details
    
    async def _check_ownership_renounced(self, token_address: str) -> Optional[bool]:
        """
        Check if token ownership is renounced.
        
        Args:
            token_address: Token contract address
            
        Returns:
            True if renounced, False if active owner, None if unknown
        """
        try:
            # Common owner check patterns
            owner_abi = [
                {
                    "name": "owner",
                    "type": "function",
                    "inputs": [],
                    "outputs": [{"type": "address"}],
                    "stateMutability": "view"
                }
            ]
            
            contract = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=owner_abi)
            
            try:
                owner = await contract.functions.owner().call()
                # Check if owner is null address
                if owner == "0x" + "0" * 40:
                    return True  # Renounced
                else:
                    return False  # Active owner
            except Exception:
                return None  # Unknown
        
        except Exception as e:
            logger.debug(f"Ownership check failed: {e}")
            return None
    
    async def _check_liquidity_locked(self, token_address: str) -> Optional[bool]:
        """
        Check if liquidity appears to be locked.
        
        Args:
            token_address: Token contract address
            
        Returns:
            True if likely locked, False if likely not locked, None if unknown
        """
        try:
            # Simplified check - in production would verify lock contracts
            # For now, return None (unknown) to allow trading with warning
            logger.debug(f"Liquidity lock status unknown for {token_address}")
            return None
        except Exception as e:
            logger.debug(f"Liquidity check failed: {e}")
            return None
    
    async def _check_honeypot_tax(self, token_address: str) -> bool:
        """
        Detect if token is a honeypot (blocks sells or has extreme tax).
        
        Args:
            token_address: Token contract address
            
        Returns:
            True if honeypot detected, False otherwise
        """
        try:
            # Simplified honeypot detection
            # In production would simulate buy/sell transactions
            logger.debug(f"Honeypot check for {token_address}: simulated (would require transaction simulation)")
            return False
        except Exception as e:
            logger.debug(f"Honeypot check failed: {e}")
            return False
    
    async def _check_suspicious_functions(self, token_address: str) -> list:
        """
        Check for suspicious functions in contract.
        
        Args:
            token_address: Token contract address
            
        Returns:
            List of suspicious function names found
        """
        suspicious = []
        try:
            # In production would decode contract bytecode and check for suspicious patterns
            # For now, return empty list
            logger.debug(f"Suspicious function check for {token_address}: simplified")
            return suspicious
        except Exception as e:
            logger.debug(f"Suspicious function check failed: {e}")
            return suspicious
    
    async def _check_holder_concentration(self, token_address: str) -> Optional[float]:
        """
        Check if token has high holder concentration (rug pull risk).
        
        Args:
            token_address: Token contract address
            
        Returns:
            Concentration ratio (0-1) or None if unknown
        """
        try:
            # Simplified concentration check
            # In production would analyze top holder balances from blockchain
            logger.debug(f"Holder concentration check for {token_address}: simplified")
            return None
        except Exception as e:
            logger.debug(f"Holder concentration check failed: {e}")
            return None
    
    def get_risk_message(self, risk_level: RiskLevel) -> str:
        """
        Get human-readable risk message.
        
        Args:
            risk_level: Risk level enum
            
        Returns:
            Risk message
        """
        messages = {
            RiskLevel.SAFE: "✅ Token appears safe",
            RiskLevel.LOW: "🟡 Low risk detected",
            RiskLevel.MEDIUM: "🟠 Medium risk - verify carefully before trading",
            RiskLevel.HIGH: "🔴 High risk - consider avoiding or use small size",
            RiskLevel.CRITICAL: "❌ CRITICAL RISK - do not trade"
        }
        return messages.get(risk_level, "Unknown risk")
