import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from core.health_check import HealthStatus, standard_health_check

logger = logging.getLogger(__name__)

class TradingModeManager:
    """
    Universal mode controller that supports:
    - live mode
    - paper mode
    - paper-trade tracking (required by main.py)
    """

    def __init__(self, config):
        # Extract mode (normalize: "simulation" is treated as "paper")
        if isinstance(config, dict):
            trading_config = config.get("trading", {})
            mode_raw = str(trading_config.get("mode", "paper")).lower()
        else:
            mode_raw = str(config).lower()
        self._current_mode = "paper" if mode_raw in ("simulation", "paper") else mode_raw

        # Paper-trade tracking (REQUIRED by main.py)
        self.paper_trades = 0
        self.successful_trades = 0
        self.total_pnl = 0.0

        # Load configuration
        self.trading_config = trading_config if isinstance(config, dict) else {}
        self.paper_trading_config = config.get("paper_trading", {}) if isinstance(config, dict) else {}

        # Trading parameters
        self.min_paper_trades = self.trading_config.get("min_paper_trades", 20)
        self.min_success_rate = self.trading_config.get("min_success_rate", 0.60)
        self.require_paper_promotion = self.trading_config.get("require_paper_promotion", True)
        
        # Paper trading parameters (replaces simulation)
        self.paper_start_date = None
        self.simulation_start_date = None
        self.simulation_days = self.trading_config.get("simulation_days", 30)  # Updated to 30 days as requested
        # Auto-switch configuration - respect config file setting
        self.auto_switch = self.trading_config.get("auto_switch", False)  # Default to False for safety
        
        # Load persisted paper trade data
        self._load_paper_trade_data()

        # Initialize paper mode timeline if in paper
        if self.is_paper():
            self._init_simulation()

        logger.info(f"Initialized TradingModeManager in '{self._current_mode}' mode")

    # --------------------------
    # MODE PROPERTIES
    # --------------------------
    @property
    def mode(self):
        return self._current_mode.upper()

    def is_live(self):
        return self._current_mode == "live"

    def is_simulation(self):
        """Deprecated: alias to paper for backward compatibility."""
        return self.is_paper()

    def is_paper(self):
        return self._current_mode == "paper"

    # --------------------------
    # PAPER TRADE RECORDING
    # --------------------------
    def record_paper_trade(self, success: bool):
        self.paper_trades += 1
        if success:
            self.successful_trades += 1

        # Persist the updated data
        self._save_paper_trade_data()

    @property
    def success_rate(self):
        if self.paper_trades == 0:
            return 0.0
        return self.successful_trades / self.paper_trades

    # --------------------------
    # STATUS FOR main.py
    # --------------------------
    def _init_simulation(self):
        """Initialize paper trading mode with start time and config."""
        self.paper_start_date = datetime.now(timezone.utc)
        # Backwards-compatible alias used elsewhere
        self.simulation_start_date = self.paper_start_date
        logger.info(
            f"🚀 Starting paper trading mode. "
            f"Minimum {self.min_paper_trades} paper trades required before live trading."
        )

    def _is_simulation_period_over(self):
        """Check if paper trading requirements are met."""
        if not self.require_paper_promotion:
            return True
            
        if self.paper_trades < self.min_paper_trades:
            return False
            
        # Check success rate
        if self.success_rate < self.min_success_rate:
            return False
            
        # Check 30-day period requirement
        if self.auto_switch and self.paper_start_date:
            days_elapsed = (datetime.now(timezone.utc) - self.paper_start_date).days
            if days_elapsed < self.simulation_days:
                logger.debug(f"Paper trading period not reached: {days_elapsed}/{self.simulation_days} days")
                return False
            
        return True

    def is_allowed_to_trade(self):
        """Check if trading is allowed based on current mode and conditions."""
        if self.is_live():
            if self.require_paper_promotion:
                # If promotion is required, ensure paper metrics are sufficient
                if not self._promotion_ready():
                    logger.warning(
                        "⚠️ Live trading blocked: paper promotion criteria not met "
                        f"({self.paper_trades}/{self.min_paper_trades} trades, "
                        f"success {self.success_rate:.1%}/{self.min_success_rate:.0%})"
                    )
                    return False
            return True
            
        if self.is_paper():
            # Check if auto-switch period is complete
            if self.auto_switch and not self._is_simulation_period_over():
                days_elapsed = (datetime.now(timezone.utc) - self.paper_start_date).days if self.paper_start_date else 0
                logger.info(
                    f"🎯 Paper trading period completed: {days_elapsed} days elapsed"
                )
                logger.info(
                    f"📊 Performance: {self.paper_trades} trades, {self.success_rate:.1%} success rate"
                )
                return False  # Block further paper trading
            
            # Never auto-promote; collect paper stats
            if self.paper_trades < self.min_paper_trades:
                logger.debug(f"Not enough paper trades: {self.paper_trades}/{self.min_paper_trades}")
                return True
            
            if self.success_rate < self.min_success_rate:
                logger.debug(
                    f"Success rate too low: {self.success_rate:.1%} < {self.min_success_rate:.0%}"
                )
                logger.warning("Continuing in paper mode due to low success rate")
            
            return True
            
        return False

    def _promotion_ready(self) -> bool:
        """Determine if paper trading performance is sufficient to promote to live."""
        if self.paper_trades < self.min_paper_trades:
            return False
        if self.success_rate < self.min_success_rate:
            return False
        return True

    def get_status(self):
        """
        Return current trading status including simulation information.
        """
        status = {
            "mode": self._current_mode,
            "live": self.is_live(),
            "simulation": self.is_simulation(),
            "allowed_to_trade": self.is_allowed_to_trade(),
            
            # Paper trading metrics
            "paper_trades": self.paper_trades,
            "successful_trades": self.successful_trades,
            "success_rate": self.success_rate,
            "total_pnl": self.total_pnl,
            
            # Configuration
            "min_paper_trades": self.min_paper_trades,
            "min_success_rate": self.min_success_rate,
        }
        
        # Add simulation-specific status
        if self.is_simulation():
            status.update({
                "simulation_days": self.simulation_days,
                "simulation_start_date": self.simulation_start_date.isoformat() if self.simulation_start_date else None,
                "days_elapsed": (datetime.now(timezone.utc) - self.simulation_start_date).days if self.simulation_start_date else 0,
                "days_remaining": max(0, self.simulation_days - (datetime.now(timezone.utc) - self.simulation_start_date).days) 
                                if self.simulation_start_date else self.simulation_days,
                "auto_switch_enabled": self.auto_switch,
            })
            
        return status

    def __str__(self):
        return f"TradingModeManager(mode={self._current_mode})"


    @standard_health_check("Trading Mode")
    async def health_check(self) -> HealthStatus:
        """Check trading mode health and consistency."""
        current_mode = self.mode
        is_healthy = True
        issues = []
        
        # Check if in paper mode when it shouldn't be
        if current_mode == "PAPER" and not self.is_paper():
            is_healthy = False
            issues.append("Mode mismatch: PAPER vs is_paper()")
        
        # Check paper trading requirements if in paper mode
        if self.is_paper() and self.require_paper_promotion:
            success_rate = (self.successful_trades / self.paper_trades) if self.paper_trades > 0 else 0
            if success_rate < self.min_success_rate:
                is_healthy = False
                issues.append(f"Paper trading success rate too low: {success_rate:.1%} < {self.min_success_rate:.1%}")
        
        return HealthStatus(
            component="Trading Mode",
            status=is_healthy,
            message=(
                f"Mode: {current_mode}" if is_healthy 
                else f"Issues in {current_mode} mode: {', '.join(issues)}"
            ),
            metrics={
                "status": "healthy" if is_healthy else "degraded",
                "mode": current_mode,
                "paper_trades": self.paper_trades,
                "successful_trades": self.successful_trades,
                "success_rate": (self.successful_trades / self.paper_trades) if self.paper_trades > 0 else 0,
                "issues": issues
            }
        )

    def _get_paper_trade_file(self) -> Path:
        """Get the file path for storing paper trade data."""
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        return data_dir / "paper_trades.json"

    def _save_paper_trade_data(self) -> None:
        """Save paper trade data to persistent storage."""
        try:
            data = {
                "paper_trades": self.paper_trades,
                "successful_trades": self.successful_trades,
                "total_pnl": self.total_pnl,
                "paper_start_date": self.paper_start_date.isoformat() if self.paper_start_date else None,
                "simulation_days": self.simulation_days,
                "auto_switch": self.auto_switch,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

            file_path = self._get_paper_trade_file()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"💾 Saved paper trade data: {self.paper_trades} trades, {self.successful_trades} successful")

        except Exception as e:
            logger.error(f"Failed to save paper trade data: {e}")

    def _load_paper_trade_data(self) -> None:
        """Load paper trade data from persistent storage."""
        try:
            file_path = self._get_paper_trade_file()
            if not file_path.exists():
                logger.debug("No existing paper trade data file found")
                return

            with open(file_path, 'r') as f:
                data = json.load(f)

            # Restore paper trade counts
            self.paper_trades = data.get("paper_trades", 0)
            self.successful_trades = data.get("successful_trades", 0)
            self.total_pnl = data.get("total_pnl", 0.0)

            # Restore paper start date if available
            if data.get("paper_start_date"):
                self.paper_start_date = datetime.fromisoformat(data["paper_start_date"])
                self.simulation_start_date = self.paper_start_date

            # Restore configuration
            self.simulation_days = data.get("simulation_days", 30)
            self.auto_switch = data.get("auto_switch", True)

            logger.info(f"📚 Loaded paper trade data: {self.paper_trades} trades, {self.successful_trades} successful")

        except Exception as e:
            logger.error(f"Failed to load paper trade data: {e}")
            # Initialize with defaults if loading fails
            self.paper_trades = 0
            self.successful_trades = 0
            self.total_pnl = 0.0
