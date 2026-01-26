import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional, Union

from bootstrap.path_manager import PathManager

logger = logging.getLogger(__name__)


class OwnershipGuard:
    """
    Lightweight ownership + kill-switch guard.

    Goals:
    - Fail-fast on startup if ownership requirements are not met.
    - Allow controlled bypass for dev/paper trading via env.
    - Runtime kill-switch detection (file-based) that can halt trading safely.
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        kill_switch_path: Optional[str] = None,
        on_kill: Optional[Callable[[str], Any]] = None,
        path_manager: Optional[PathManager] = None,
    ):
        self.config = config or {}
        self.path_manager = path_manager  # Store path manager for later use
        self.kill_switch_path = (
            Path(kill_switch_path)
            if kill_switch_path
            else Path(self.config.get("ownership", {}).get("kill_switch_path", "kill.switch"))
        )
        self.on_kill = on_kill
        self._dev_bypass = self.config.get("ownership", {}).get("dev_bypass", False)

    def _fingerprint(self) -> str:
        """
        Machine fingerprint placeholder using project root instead of working directory.

        This ensures the fingerprint is consistent regardless of the current working directory,
        which is critical for deployment scenarios (Docker, services, etc.).
        """
        # Use current working directory as project root since PathManager was removed
        project_root = str(Path.cwd())

        # Create fingerprint from hostname + project root (not working directory)
        data = f"{os.uname().nodename}-{project_root}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def verify_startup(self):
        """
        Enforce ownership checks at startup.
        Raises RuntimeError on failure to stop startup.
        """
        if self._dev_bypass:
            logger.warning("⚠️ OWNERSHIP_BYPASS=true — startup ownership checks skipped (dev mode)")
            return

        ownership_cfg = self.config.get("ownership", {})
        license_key = ownership_cfg.get("license_key") or ownership_cfg.get("license")

        if ownership_cfg.get("require", False) and not license_key:
            raise RuntimeError("Ownership validation failed: missing license key")

        fp = self._fingerprint()
        logger.info(f"🛡️ Ownership validated (fingerprint={fp})")

    def is_runtime_valid(self) -> bool:
        """
        Runtime tamper/kill detection.
        Returns False if kill switch file is present.
        """
        if self.kill_switch_path.exists():
            logger.critical(f"🚨 Kill switch activated via {self.kill_switch_path}")
            return False
        return True

    async def enforce_runtime(self, reason: str = "Ownership invalidated"):
        """
        Trigger runtime kill actions.
        
        Args:
            reason: Reason for the kill action
        """
        logger.critical(f"🔒 Ownership enforcement triggered: {reason}")
        if self.on_kill:
            try:
                result = self.on_kill(reason)
                # Handle both sync and async callbacks
                if result is not None and hasattr(result, "__await__"):
                    await result
                elif result is not None:
                    # If it's not awaitable and not None, it's a sync result
                    logger.debug(f"Kill callback completed with result: {result}")
            except Exception as e:
                logger.error(f"Error during kill callback: {e}")
