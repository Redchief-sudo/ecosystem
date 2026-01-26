import logging
from typing import Dict

logger = logging.getLogger(__name__)

class SuccessTracker:
    """Simple tracker to record successful scanner runs and reset failure counts."""
    def __init__(self):
        self.scanner_health: Dict[str, Dict] = {}

    def record_success(self, scanner_name: str) -> None:
        health = self.scanner_health.get(scanner_name, {
            'consecutive_failures': 0,
            'disabled': False,
            'last_failure': 0.0,
            'disabled_until': 0.0
        })

        if health.get('consecutive_failures', 0) > 0:
            health['consecutive_failures'] = 0
            logger.info(f"Reset failure count for scanner {scanner_name}")

        self.scanner_health[scanner_name] = health

    def get_health(self, scanner_name: str) -> Dict:
        return self.scanner_health.get(scanner_name, {})
