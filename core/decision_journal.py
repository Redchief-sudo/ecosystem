"""
Decision Journal
Records all trading decisions and executions for audit and analysis.
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class JournalEntry:
    timestamp: float
    opportunity_id: str
    token_address: str
    chain: str
    decision: str
    execution_success: bool
    execution_time_ms: float
    metadata: Dict[str, Any]


class OpportunityJournal:
    """
    Journal for recording all trading opportunities and decisions.
    Provides audit trail and post-trade analysis.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._entries: list = []
        self._current_session_file: Optional[Path] = None
        
        # Create session file
        session_timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._current_session_file = self.data_dir / f"session_{session_timestamp}.jsonl"
        
        logger.info(f"OpportunityJournal initialized: {self._current_session_file}")
    
    async def record_execution(
        self,
        opportunity: Any,
        execution_result: Any
    ):
        """Record an execution in the journal."""
        try:
            entry = JournalEntry(
                timestamp=time.time(),
                opportunity_id=getattr(opportunity, 'opportunity_id', 'unknown'),
                token_address=getattr(opportunity.token, 'address', ''),
                chain=getattr(opportunity.token, 'chain', 'unknown'),
                decision='execute',
                execution_success=getattr(execution_result, 'success', False),
                execution_time_ms=getattr(execution_result, 'execution_time_ms', 0.0),
                metadata={
                    "transaction_hash": getattr(execution_result, 'transaction_hash', None),
                    "order_id": getattr(execution_result, 'order_id', None)
                }
            )
            
            self._entries.append(entry)
            
            # Write to file
            await self._write_entry(entry)
            
        except Exception as e:
            logger.error(f"Failed to record execution: {e}")
    
    async def _write_entry(self, entry: JournalEntry):
        """Write entry to journal file."""
        if not self._current_session_file:
            logger.error("No session file available for writing")
            return
        
        try:
            with open(self._current_session_file, 'a') as f:
                json.dump(asdict(entry), f)
                f.write('\n')
        except Exception as e:
            logger.error(f"Failed to write journal entry: {e}")
    
    def export_summary(self, output_path: Path):
        """Export summary of journal entries."""
        try:
            summary = {
                "total_entries": len(self._entries),
                "successful_executions": sum(1 for e in self._entries if e.execution_success),
                "failed_executions": sum(1 for e in self._entries if not e.execution_success),
                "average_execution_time_ms": (
                    sum(e.execution_time_ms for e in self._entries) / len(self._entries)
                    if self._entries else 0
                ),
                "session_file": str(self._current_session_file)
            }
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Journal summary exported to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export summary: {e}")
    
    def get_entries(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        chain: Optional[str] = None
    ) -> list:
        """Get journal entries with optional filtering."""
        entries = self._entries
        
        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]
        
        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]
        
        if chain:
            entries = [e for e in entries if e.chain == chain]
        
        return entries
