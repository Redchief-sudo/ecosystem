#!/usr/bin/env python3
"""
TradeIntent Validator - Guardrail Stage

This module provides validation for TradeIntents before they reach execution.
It enforces hard stops for invalid trades to prevent admission rejections.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from trading.models import TradeIntent, TradeSide

logger = logging.getLogger("trade_validator")


class TradeIntentValidationError(Exception):
    """Raised when TradeIntent fails validation"""
    pass


class TradeIntentValidator:
    """
    Validates TradeIntents with strict enforcement.

    This is the guardrail stage that prevents invalid trades
    from reaching the admission controller.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_trade_amount = config.get("min_trade_amount", 5.0)
        self.max_trade_amount = config.get("max_trade_amount", 10000.0)

        supported = config.get("supported_chains", [])
        self.supported_chains = {str(c).lower() for c in supported}

        logger.info("TradeIntentValidator initialized")
        logger.info("Min trade amount: $%s", self.min_trade_amount)
        logger.info("Max trade amount: $%s", self.max_trade_amount)
        logger.info("Supported chains: %s", sorted(self.supported_chains))

    def validate(self, trade_intent: TradeIntent) -> bool:
        """
        Validate TradeIntent with hard stops.

        Args:
            trade_intent: TradeIntent to validate

        Returns:
            True if valid

        Raises:
            TradeIntentValidationError: If invalid
        """
        self._validate_side(trade_intent)
        self._validate_amount(trade_intent)
        self._validate_chain(trade_intent)
        self._validate_token_address(trade_intent)
        self._validate_prices(trade_intent)

        logger.info(
            "TradeIntent validated: %s %s",
            getattr(trade_intent, "symbol", "UNKNOWN"),
            getattr(trade_intent, "side", "UNKNOWN"),
        )
        return True

    def _validate_side(self, trade_intent: TradeIntent) -> None:
        """Validate trade side is present and valid"""
        side = getattr(trade_intent, "side", None)
        if side is None:
            raise TradeIntentValidationError("TradeIntent missing side")

        if not isinstance(side, TradeSide):
            raise TradeIntentValidationError(f"Invalid side type: {type(side)}")

        if side not in {TradeSide.BUY, TradeSide.SELL}:
            raise TradeIntentValidationError(f"Invalid side value: {side}")

    def _validate_amount(self, trade_intent: TradeIntent) -> None:
        """Validate trade amount is within bounds"""

        # Prefer amount_usd if present, otherwise use amount_in
        amount_usd = getattr(trade_intent, "amount_usd", None)
        amount_in = getattr(trade_intent, "amount_in", None)

        if amount_usd is not None:
            amount = amount_usd
        elif amount_in is not None:
            amount = amount_in
        else:
            raise TradeIntentValidationError("TradeIntent missing amount_usd or amount_in")

        try:
            amount = float(amount)
        except Exception:
            raise TradeIntentValidationError(f"Invalid amount type: {type(amount)}")

        if amount <= 0:
            raise TradeIntentValidationError(f"Invalid amount: {amount}")

        if amount < self.min_trade_amount:
            raise TradeIntentValidationError(
                f"Amount ${amount:.2f} below minimum ${self.min_trade_amount:.2f}"
            )

        if amount > self.max_trade_amount:
            raise TradeIntentValidationError(
                f"Amount ${amount:.2f} above maximum ${self.max_trade_amount:.2f}"
            )

    def _validate_chain(self, trade_intent: TradeIntent) -> None:
        """Validate chain is supported"""
        chain = getattr(trade_intent, "chain", None)
        if not chain:
            raise TradeIntentValidationError("TradeIntent missing chain")

        if self.supported_chains and str(chain).lower() not in self.supported_chains:
            raise TradeIntentValidationError(
                f"Chain '{chain}' not supported: {sorted(self.supported_chains)}"
            )

    def _validate_token_address(self, trade_intent: TradeIntent) -> None:
        """Validate token address format"""

        token_address = getattr(trade_intent, "token_address", None)
        token_out = getattr(trade_intent, "token_out", None)

        if token_address:
            address = token_address
        elif token_out:
            address = token_out
        else:
            raise TradeIntentValidationError("TradeIntent missing token_address or token_out")

        address = str(address).lower()

        # EVM address validation
        if address.startswith("0x"):
            if len(address) != 42:
                raise TradeIntentValidationError(f"Invalid EVM address length: {address}")
            try:
                int(address[2:], 16)
            except ValueError:
                raise TradeIntentValidationError(f"Invalid EVM address hex: {address}")
        else:
            if len(address) < 8:
                raise TradeIntentValidationError(f"Invalid address format: {address}")

    def _validate_prices(self, trade_intent: TradeIntent) -> None:
        """Validate prices are reasonable"""
        entry_price = getattr(trade_intent, "entry_price", None)
        stop_loss = getattr(trade_intent, "stop_loss", None)
        take_profit = getattr(trade_intent, "take_profit", None)

        if entry_price is None or entry_price <= 0:
            raise TradeIntentValidationError(f"Invalid entry price: {entry_price}")

        if stop_loss is not None and stop_loss <= 0:
            raise TradeIntentValidationError(f"Invalid stop loss: {stop_loss}")

        if take_profit is not None and take_profit <= 0:
            raise TradeIntentValidationError(f"Invalid take profit: {take_profit}")

        side = getattr(trade_intent, "side", None)

        if side == TradeSide.BUY:
            if stop_loss is not None and stop_loss >= entry_price:
                raise TradeIntentValidationError("BUY stop loss must be below entry price")
            if take_profit is not None and take_profit <= entry_price:
                raise TradeIntentValidationError("BUY take profit must be above entry price")

        if side == TradeSide.SELL:
            if stop_loss is not None and stop_loss <= entry_price:
                raise TradeIntentValidationError("SELL stop loss must be above entry price")
            if take_profit is not None and take_profit >= entry_price:
                raise TradeIntentValidationError("SELL take profit must be below entry price")


# Global validator instance
_validator: Optional[TradeIntentValidator] = None


def initialize_validator(config: Dict[str, Any]) -> TradeIntentValidator:
    """Initialize the global validator"""
    global _validator
    _validator = TradeIntentValidator(config)
    return _validator


def validate_trade_intent(trade_intent: TradeIntent) -> bool:
    """
    Validate a TradeIntent using the global validator.

    Args:
        trade_intent: TradeIntent to validate

    Returns:
        True if valid

    Raises:
        RuntimeError: If validator not initialized
        TradeIntentValidationError: If invalid
    """
    if _validator is None:
        raise RuntimeError("TradeIntentValidator not initialized")

    return _validator.validate(trade_intent)

