import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

class FailureTracker:
    """Simple failure tracker for scanners and components.

    Tracks consecutive failures and disables a component for a cooldown period
    after exceeding a configurable threshold.
    """
    def __init__(self, max_failures: int = 3, cooldown_period: float = 300.0):
        self.max_failures = max_failures
        self.cooldown_period = cooldown_period
        self.scanner_health: Dict[str, Dict] = {}

    def record_failure(self, scanner_name: str) -> None:
        """Record a failure for a scanner and disable if threshold reached."""
        health = self.scanner_health.get(scanner_name, {
            'consecutive_failures': 0,
            'disabled': False,
            'last_failure': 0.0,
            'disabled_until': 0.0
        })

        health['consecutive_failures'] += 1
        health['last_failure'] = time.time()

        if health['consecutive_failures'] >= self.max_failures:
            health['disabled'] = True
            health['disabled_until'] = time.time() + self.cooldown_period
            logger.warning(
                f"Disabling scanner {scanner_name} after {health['consecutive_failures']} failures"
            )

        self.scanner_health[scanner_name] = health

    def is_disabled(self, scanner_name: str) -> bool:
        """Return True if scanner is currently disabled due to failures."""
        health = self.scanner_health.get(scanner_name)
        if not health:
            return False
        if health.get('disabled') and time.time() < health.get('disabled_until', 0):
            return True
        # If cooldown expired, reset the health
        if health.get('disabled') and time.time() >= health.get('disabled_until', 0):
            self.reset(scanner_name)
            return False
        return False

    def reset(self, scanner_name: str) -> None:
        """Reset failure state for a scanner."""
        self.scanner_health.pop(scanner_name, None)
