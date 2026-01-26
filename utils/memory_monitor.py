# utils/memory_monitor.py
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger('memory.monitor')

class MemoryMonitor:
    """Monitors and reports on memory usage and token statistics."""
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.stats = {
            'last_updated': None,
            'total_tokens': 0,
            'tokens_by_chain': {},
            'score_distribution': {'0-0.2': 0, '0.2-0.4': 0, '0.4-0.6': 0, '0.6-0.8': 0, '0.8-1.0': 0}
        }
        
    def update_stats(self):
        """Update memory statistics."""
        tokens = self.memory.get_all_tokens()
        self.stats = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'total_tokens': len(tokens),
            'tokens_by_chain': {},
            'score_distribution': {'0-0.2': 0, '0.2-0.4': 0, '0.4-0.6': 0, '0.6-0.8': 0, '0.8-1.0': 0}
        }
        
        for token in tokens:
            # Count by chain - using direct attribute access for TokenMetadata
            chain = getattr(token, 'chain', 'unknown')
            self.stats['tokens_by_chain'][chain] = self.stats['tokens_by_chain'].get(chain, 0) + 1
            
            # Score distribution - using direct attribute access for TokenMetadata
            score = getattr(token, 'ai_score', 0)
            if score < 0.2:
                self.stats['score_distribution']['0-0.2'] += 1
            elif score < 0.4:
                self.stats['score_distribution']['0.2-0.4'] += 1
            elif score < 0.6:
                self.stats['score_distribution']['0.4-0.6'] += 1
            elif score < 0.8:
                self.stats['score_distribution']['0.6-0.8'] += 1
            else:
                self.stats['score_distribution']['0.8-1.0'] += 1
                
        return self.stats
        
    def get_memory_report(self) -> str:
        """Generate a human-readable memory report."""
        self.update_stats()
        report = [
            f"Memory Report - {self.stats['last_updated']}",
            f"Total Tokens: {self.stats['total_tokens']}",
            "\nTokens by Chain:"
        ]
        
        for chain, count in sorted(self.stats['tokens_by_chain'].items(), key=lambda x: x[1], reverse=True):
            report.append(f"  {chain.upper()}: {count}")
            
        report.append("\nAI Score Distribution:")
        for range_, count in self.stats['score_distribution'].items():
            pct = (count / self.stats['total_tokens'] * 100) if self.stats['total_tokens'] > 0 else 0
            report.append(f"  {range_}: {count} tokens ({pct:.1f}%)")
            
        return "\n".join(report)
