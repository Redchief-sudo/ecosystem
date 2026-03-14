"""
Portfolio Persistence Manager
Handles saving and loading portfolio state with automatic backups.
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)


class PortfolioPersistenceManager:
    """
    Manages portfolio state persistence with automatic saving.
    """
    
    def __init__(
        self,
        portfolio_manager: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        self.portfolio = portfolio_manager
        self.config = config or {}
        
        # Configuration
        self.auto_save_enabled = self.config.get("auto_save_enabled", True)
        self.min_save_interval_seconds = self.config.get("min_save_interval_seconds", 1)
        self.data_dir = Path(self.config.get("data_dir", "data/portfolio"))
        
        # State
        self._last_save_time: Optional[float] = None
        self._running = False
        self._save_task: Optional[asyncio.Task] = None
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("PortfolioPersistenceManager initialized")
    
    async def start(self):
        """Start the persistence manager."""
        if self._running:
            return
        
        self._running = True
        
        if self.auto_save_enabled:
            self._save_task = asyncio.create_task(
                self._auto_save_loop(),
                name="portfolio_auto_save"
            )
        
        logger.info("PortfolioPersistenceManager started")
    
    async def stop(self):
        """Stop the persistence manager."""
        if not self._running:
            return
        
        self._running = False
        
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        
        # Final save
        await self.force_save()
        
        logger.info("PortfolioPersistenceManager stopped")
    
    async def save_after_execution(self, order_id: str):
        """Save portfolio after an execution."""
        if not self._should_save():
            return
        
        await self._save_state(f"execution_{order_id}")
    
    async def save_after_reconciliation(self):
        """Save portfolio after reconciliation."""
        if not self._should_save():
            return
        
        await self._save_state("reconciliation")
    
    async def save_after_wallet_sync(self):
        """Save portfolio after wallet sync."""
        if not self._should_save():
            return
        
        await self._save_state("wallet_sync")
    
    async def force_save(self) -> bool:
        """Force immediate save."""
        return await self._save_state("forced")
    
    def _should_save(self) -> bool:
        """Check if save should be performed based on rate limiting."""
        if not self.auto_save_enabled:
            return False
        
        if self._last_save_time is None:
            return True
        
        elapsed = time.time() - self._last_save_time
        return elapsed >= self.min_save_interval_seconds
    
    async def _save_state(self, trigger: str) -> bool:
        """Save current portfolio state."""
        try:
            if not self.portfolio or not hasattr(self.portfolio, 'get_portfolio_state'):
                return False
            
            state = self.portfolio.get_portfolio_state()
            
            # Add metadata
            save_data = {
                "timestamp": time.time(),
                "trigger": trigger,
                "state": state
            }
            
            # Save to file
            filename = f"portfolio_{int(time.time())}.json"
            filepath = self.data_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            self._last_save_time = time.time()
            
            logger.debug(f"Portfolio saved to {filepath} (trigger: {trigger})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save portfolio: {e}")
            return False
    
    async def _auto_save_loop(self):
        """Background auto-save loop."""
        while self._running:
            try:
                await asyncio.sleep(self.min_save_interval_seconds)
                
                if self._should_save():
                    await self._save_state("auto")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")
    
    async def load_latest(self) -> Optional[Dict[str, Any]]:
        """Load the most recent portfolio state."""
        try:
            # Find most recent file
            files = sorted(
                self.data_dir.glob("portfolio_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if not files:
                return None
            
            latest = files[0]
            
            with open(latest, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loaded portfolio state from {latest}")
            return data.get("state")
            
        except Exception as e:
            logger.error(f"Failed to load portfolio: {e}")
            return None


class BackupManager:
    """
    Manages automated backups of system state.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Configuration
        self.backup_dir = Path(self.config.get("backup_dir", "data/backups"))
        self.backup_interval_hours = self.config.get("backup_interval_hours", 6)
        self.max_backups = self.config.get("max_backups", 168)  # 1 week at 6hr intervals
        
        # State
        self._running = False
        self._backup_task: Optional[asyncio.Task] = None
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("BackupManager initialized")
    
    async def start(self, portfolio_manager: Any, journal: Any):
        """Start the backup manager."""
        if self._running:
            return
        
        self._running = True
        self._portfolio = portfolio_manager
        self._journal = journal
        
        self._backup_task = asyncio.create_task(
            self._backup_loop(),
            name="backup_manager"
        )
        
        logger.info("BackupManager started")
    
    async def stop(self):
        """Stop the backup manager."""
        if not self._running:
            return
        
        self._running = False
        
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("BackupManager stopped")
    
    async def _backup_loop(self):
        """Background backup loop."""
        while self._running:
            try:
                await asyncio.sleep(self.backup_interval_hours * 3600)
                
                await self._create_backup()
                
                # Cleanup old backups
                await self._cleanup_old_backups()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup error: {e}")
    
    async def _create_backup(self):
        """Create a backup of current system state."""
        try:
            timestamp = int(time.time())
            backup_subdir = self.backup_dir / f"backup_{timestamp}"
            backup_subdir.mkdir(parents=True, exist_ok=True)
            
            # Backup portfolio if available
            if self._portfolio and hasattr(self._portfolio, 'get_portfolio_state'):
                portfolio_state = self._portfolio.get_portfolio_state()
                with open(backup_subdir / "portfolio.json", 'w') as f:
                    json.dump(portfolio_state, f, indent=2)
            
            # Backup journal if available
            if self._journal and hasattr(self._journal, 'export_summary'):
                self._journal.export_summary(backup_subdir / "journal_summary.json")
            
            logger.info(f"Backup created: {backup_subdir}")
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
    
    async def _cleanup_old_backups(self):
        """Remove old backups beyond max_backups limit."""
        try:
            backups = sorted(
                self.backup_dir.glob("backup_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if len(backups) > self.max_backups:
                for old_backup in backups[self.max_backups:]:
                    import shutil
                    shutil.rmtree(old_backup)
                    logger.debug(f"Removed old backup: {old_backup}")
                    
        except Exception as e:
            logger.error(f"Backup cleanup error: {e}")
