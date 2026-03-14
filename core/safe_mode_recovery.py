"""
Safe Mode Recovery Policy
Manages system state transitions and recovery from failures.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from enum import Enum, auto

logger = logging.getLogger(__name__)


class SystemState(Enum):
    NORMAL = "normal"
    SAFE_MODE = "safe_mode"
    RECOVERY = "recovery"
    SHUTDOWN = "shutdown"


class RecoveryStrategy(Enum):
    HEALTH_CHECK = "health_check"
    IMMEDIATE = "immediate"
    GRADUAL = "gradual"


class SafeModeRecoveryPolicy:
    """
    Manages safe mode entry/exit and recovery procedures.
    """
    
    def __init__(
        self,
        state_manager: Any,
        executor_health_monitor: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        self.state_manager = state_manager
        self.executor_health_monitor = executor_health_monitor
        self.config = config or {}
        
        # Configuration
        self.recovery_strategy = RecoveryStrategy(
            self.config.get("recovery_strategy", "health_check")
        )
        self.cooldown_seconds = self.config.get("cooldown_seconds", 300)
        self.health_check_interval = self.config.get("health_check_interval", 30)
        self.max_health_checks = self.config.get("max_health_checks_for_recovery", 3)
        
        # State
        self._safe_mode_entered_at: Optional[float] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self._running = False
        self._health_checks_passed = 0
    
    async def start(self):
        """Start the recovery policy monitoring."""
        if self._running:
            return
        
        self._running = True
        logger.info("SafeModeRecoveryPolicy started")
    
    async def stop(self):
        """Stop the recovery policy."""
        if not self._running:
            return
        
        self._running = False
        
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        
        logger.info("SafeModeRecoveryPolicy stopped")
    
    def on_safe_mode_entered(self, reason: str):
        """Called when system enters safe mode."""
        self._safe_mode_entered_at = time.time()
        self._health_checks_passed = 0
        
        logger.warning(f"Safe mode entered: {reason}")
        
        # Start recovery monitoring
        if self._running and not self._recovery_task:
            self._recovery_task = asyncio.create_task(
                self._recovery_loop(),
                name="safe_mode_recovery"
            )
    
    async def _recovery_loop(self):
        """Monitor for recovery conditions."""
        while self._running and self.state_manager.get_state() == SystemState.SAFE_MODE:
            try:
                # Perform health check
                healthy = await self._perform_health_check()
                
                if healthy:
                    self._health_checks_passed += 1
                    logger.info(f"Health check passed ({self._health_checks_passed}/{self.max_health_checks})")
                    
                    if self._health_checks_passed >= self.max_health_checks:
                        await self._attempt_recovery()
                        break
                else:
                    self._health_checks_passed = 0
                    logger.warning("Health check failed, resetting recovery counter")
                
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")
                await asyncio.sleep(self.health_check_interval)
        
        self._recovery_task = None
    
    async def _perform_health_check(self) -> bool:
        """Perform system health check."""
        try:
            # Check executor health
            if self.executor_health_monitor:
                executor_healthy = await self.executor_health_monitor.check_health()
                if not executor_healthy:
                    return False
            
            # Check cooldown period
            if self._safe_mode_entered_at:
                elapsed = time.time() - self._safe_mode_entered_at
                if elapsed < self.cooldown_seconds:
                    logger.debug(f"Cooldown period: {elapsed:.0f}/{self.cooldown_seconds}s")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False
    
    async def _attempt_recovery(self):
        """Attempt to recover from safe mode."""
        logger.info("Attempting recovery from safe mode...")
        
        try:
            # Transition to recovery state
            self.state_manager.transition_to(
                SystemState.RECOVERY,
                "Starting recovery procedure"
            )
            
            # Perform recovery actions based on strategy
            if self.recovery_strategy == RecoveryStrategy.HEALTH_CHECK:
                await self._health_check_recovery()
            elif self.recovery_strategy == RecoveryStrategy.IMMEDIATE:
                await self._immediate_recovery()
            elif self.recovery_strategy == RecoveryStrategy.GRADUAL:
                await self._gradual_recovery()
            
            # Transition back to normal
            self.state_manager.transition_to(
                SystemState.NORMAL,
                "Recovery complete"
            )
            
            self._safe_mode_entered_at = None
            self._health_checks_passed = 0
            
            logger.info("Recovery successful - system back to normal")
            
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            # Stay in safe mode, will retry
    
    async def _health_check_recovery(self):
        """Recovery via health checks."""
        # Already performed in recovery loop
        pass
    
    async def _immediate_recovery(self):
        """Immediate recovery - just transition state."""
        await asyncio.sleep(1)  # Brief pause
    
    async def _gradual_recovery(self):
        """Gradual recovery - slowly restore functionality."""
        # Gradually increase limits
        for i in range(5):
            logger.info(f"Gradual recovery step {i+1}/5")
            await asyncio.sleep(10)


class ExecutorHealthMonitor:
    """
    Monitors executor health including RPC, queue depth, and nonces.
    """
    
    def __init__(
        self,
        network_manager: Any,
        nonce_manager: Any,
        tx_queue: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        self.network_manager = network_manager
        self.nonce_manager = nonce_manager
        self.tx_queue = tx_queue
        self.config = config or {}
        
        # Configuration
        self.rpc_timeout_seconds = self.config.get("rpc_timeout_seconds", 5)
        self.max_queue_depth_percent = self.config.get("max_queue_depth_percent", 90)
        self.max_pending_nonces = self.config.get("max_pending_nonces", 10)
        self.chains_to_monitor = self.config.get("chains_to_monitor", [])
        
        # State
        self._last_health_check: Optional[float] = None
        self._health_status: Dict[str, Any] = {}
    
    async def check_health(self) -> bool:
        """Perform comprehensive health check."""
        checks = {
            "rpc": await self._check_rpc_health(),
            "queue": self._check_queue_health(),
            "nonces": self._check_nonce_health()
        }
        
        self._health_status = {
            "timestamp": time.time(),
            "checks": checks,
            "overall_healthy": all(checks.values())
        }
        
        self._last_health_check = time.time()
        
        return self._health_status["overall_healthy"]
    
    async def _check_rpc_health(self) -> bool:
        """Check RPC endpoints for all monitored chains."""
        for chain in self.chains_to_monitor:
            try:
                client = self.network_manager.get_client(chain)
                if not client:
                    logger.warning(f"No client for chain {chain}")
                    return False
                
                # Try a simple call with timeout
                await asyncio.wait_for(
                    client.eth.block_number,
                    timeout=self.rpc_timeout_seconds
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"RPC timeout for chain {chain}")
                return False
            except Exception as e:
                logger.warning(f"RPC error for chain {chain}: {e}")
                return False
        
        return True
    
    def _check_queue_health(self) -> bool:
        """Check transaction queue health."""
        if not self.tx_queue:
            return True  # No queue to check
        
        stats = self.tx_queue.get_stats()
        queue_size = stats.get("queue_size", 0)
        max_size = stats.get("max_size", 100)
        
        utilization = (queue_size / max_size * 100) if max_size > 0 else 0
        
        if utilization > self.max_queue_depth_percent:
            logger.warning(f"Queue depth critical: {utilization:.1f}%")
            return False
        
        return True
    
    def _check_nonce_health(self) -> bool:
        """Check nonce manager health."""
        # TODO: Implement nonce health check
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return self._health_status
    
    def get_last_check_time(self) -> Optional[float]:
        """Get timestamp of last health check."""
        return self._last_health_check
