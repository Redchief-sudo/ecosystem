"""
System State Manager
Manages system state transitions and operational modes.
"""

import logging
import time
from typing import Dict, Any, Optional
from enum import Enum, auto

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """System operational states."""
    WARMUP = "warmup"
    LIVE = "live"
    SAFE_MODE = "safe_mode"
    RECOVERY = "recovery"
    SHUTDOWN = "shutdown"


class SystemStateManager:
    """
    Manages system state transitions with validation.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        SystemState.WARMUP: [SystemState.LIVE, SystemState.SHUTDOWN],
        SystemState.LIVE: [SystemState.SAFE_MODE, SystemState.SHUTDOWN],
        SystemState.SAFE_MODE: [SystemState.RECOVERY, SystemState.SHUTDOWN],
        SystemState.RECOVERY: [SystemState.LIVE, SystemState.SAFE_MODE, SystemState.SHUTDOWN],
        SystemState.SHUTDOWN: []  # Terminal state
    }
    
    # Operations allowed in each state
    ALLOWED_OPERATIONS = {
        SystemState.WARMUP: ["initialization", "health_checks"],
        SystemState.LIVE: ["scanning", "ai_decisions", "execution", "all_operations"],
        SystemState.SAFE_MODE: ["health_checks", "monitoring", "read_only"],
        SystemState.RECOVERY: ["health_checks", "limited_execution"],
        SystemState.SHUTDOWN: []
    }
    
    def __init__(self):
        self._state = SystemState.WARMUP
        self._state_history: list = []
        self._lock = False
    
    @property
    def current_state(self) -> SystemState:
        """Get current system state."""
        return self._state
    
    def get_state(self) -> SystemState:
        """Get current system state (alias)."""
        return self._state
    
    def transition_to(self, new_state: SystemState, reason: Optional[str] = None) -> bool:
        """
        Transition to a new state.
        Returns True if transition was successful.
        """
        if self._lock:
            logger.warning("State transition locked, cannot transition")
            return False
        
        # Idempotent: already in target state is a no-op
        if self._state == new_state:
            logger.debug(f"Already in state {new_state.value}, skipping transition")
            return True
        
        # Validate transition
        if new_state not in self.VALID_TRANSITIONS.get(self._state, []):
            logger.error(
                f"Invalid state transition: {self._state.value} -> {new_state.value}"
            )
            return False
        
        # Record transition
        old_state = self._state
        self._state = new_state
        self._state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": time.time()
        })
        
        logger.info(
            f"State transition: {old_state.value} -> {new_state.value}"
            + (f" ({reason})" if reason else "")
        )
        
        return True
    
    def can_perform(self, operation: str) -> bool:
        """Check if an operation is allowed in current state."""
        allowed = self.ALLOWED_OPERATIONS.get(self._state, [])
        return operation in allowed or "all_operations" in allowed
    
    def enter_safe_mode(self, reason: str):
        """Enter safe mode."""
        return self.transition_to(SystemState.SAFE_MODE, reason)
    
    def exit_safe_mode(self):
        """Exit safe mode to recovery."""
        return self.transition_to(SystemState.RECOVERY, "Exiting safe mode")
    
    def get_state_history(self) -> list:
        """Get state transition history."""
        return self._state_history.copy()
    
    def lock_transitions(self):
        """Lock state transitions."""
        self._lock = True
    
    def unlock_transitions(self):
        """Unlock state transitions."""
        self._lock = False
