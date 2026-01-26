#!/usr/bin/env python3
"""
End-to-End System Verification
==============================
Comprehensive verification of the entire system flow.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple

class EndToEndVerifier:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def check_imports(self):
        """Check that all required imports are available."""
        try:
            from core.models import TradeOpportunity, MarketData, TokenInfo
            from trading.token_pipeline.token_candidate import TokenCandidate, FrozenTokenCandidate
            from ai.elite_async_ai_controller import EliteAsyncAIController
            print("✅ All imports successful")
        except ImportError as e:
            self.errors.append(f"Import error: {e}")
    
    def check_data_flow(self):
        """Verify data flow through the system."""
        # Check TokenCandidate -> TradeOpportunity conversion
        ai_file = self.project_root / "ai" / "elite_async_ai_controller.py"
        with open(ai_file, 'r') as f:
            content = f.read()
        
        # Check _candidate_to_opportunity
        if "_candidate_to_opportunity" not in content:
            self.errors.append("_candidate_to_opportunity method missing")
        else:
            # Check it creates TradeOpportunity correctly
            if "TradeOpportunity(" not in content:
                self.errors.append("_candidate_to_opportunity doesn't create TradeOpportunity")
            if "MarketData(" not in content:
                self.errors.append("_candidate_to_opportunity doesn't create MarketData")
            if "TokenInfo(" not in content:
                self.errors.append("_candidate_to_opportunity doesn't create TokenInfo")
    
    def check_market_data_extraction(self):
        """Verify market data extraction handles MarketData correctly."""
        ai_file = self.project_root / "ai" / "elite_async_ai_controller.py"
        with open(ai_file, 'r') as f:
            content = f.read()
        
        # Check that it doesn't try to update MarketData as dict
        if "market_data.update(" in content:
            self.errors.append("_extract_market_data still tries to update MarketData as dict")
        
        # Check that it extracts fields properly
        if "opportunity.market_data.price" not in content:
            self.errors.append("_extract_market_data doesn't extract price from MarketData")
        if "opportunity.market_data.volume_24h" not in content:
            self.errors.append("_extract_market_data doesn't extract volume_24h from MarketData")
    
    def check_queue_connections(self):
        """Verify queue connections."""
        main_file = self.project_root / "main.py"
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check decision_queue
        if "decision_queue" not in content:
            self.errors.append("decision_queue not found in main.py")
        if "'decision_queue'" not in content and '"decision_queue"' not in content:
            self.warnings.append("decision_queue may not be in composition.components")
        
        # Check opportunity_queue
        if "opportunity_queue" not in content:
            self.errors.append("opportunity_queue not found in main.py")
        if "'opportunity_queue'" not in content and '"opportunity_queue"' not in content:
            self.warnings.append("opportunity_queue may not be in composition.components")
        
        # Check AI controller gets both queues
        if "decision_queue=decision_queue" not in content:
            self.errors.append("AI controller not passed decision_queue")
        if "opportunity_queue=opportunity_queue" not in content:
            self.errors.append("AI controller not passed opportunity_queue")
    
    def check_consumer_loop(self):
        """Verify token consumer loop implementation."""
        ai_file = self.project_root / "ai" / "elite_async_ai_controller.py"
        with open(ai_file, 'r') as f:
            content = f.read()
        
        # Check required methods
        required = [
            "_token_consumer_loop",
            "select_strategy",
            "_extract_market_data",
            "_candidate_to_opportunity"
        ]
        
        for method in required:
            if f"def {method}" not in content and f"async def {method}" not in content:
                self.errors.append(f"Missing method: {method}")
        
        # Check consumer loop logic
        if "self.decision_queue.get()" not in content:
            self.errors.append("Consumer loop doesn't get from decision_queue")
        if "self.opportunity_queue.put_nowait" not in content:
            self.errors.append("Consumer loop doesn't put to opportunity_queue")
        if "while self._running" not in content:
            self.errors.append("Consumer loop doesn't check _running flag")
    
    def check_trading_loop(self):
        """Verify trading loop consumes opportunities."""
        main_file = self.project_root / "main.py"
        with open(main_file, 'r') as f:
            content = f.read()
        
        if "opportunity_queue.get()" not in content:
            self.errors.append("Trading loop doesn't consume from opportunity_queue")
        if "composition.opportunity_queue" not in content:
            self.errors.append("Trading loop doesn't access opportunity_queue correctly")
    
    def check_error_handling(self):
        """Check for proper error handling."""
        ai_file = self.project_root / "ai" / "elite_async_ai_controller.py"
        with open(ai_file, 'r') as f:
            content = f.read()
        
        # Check consumer loop has error handling
        if "_token_consumer_loop" in content:
            loop_start = content.find("async def _token_consumer_loop")
            if loop_start != -1:
                loop_section = content[loop_start:loop_start+2000]
                if "except Exception" not in loop_section and "except" not in loop_section:
                    self.warnings.append("Consumer loop may lack error handling")
    
    def check_type_compatibility(self):
        """Check type compatibility between components."""
        # Check that FrozenTokenCandidate can be used like TokenCandidate
        candidate_file = self.project_root / "trading" / "token_pipeline" / "token_candidate.py"
        with open(candidate_file, 'r') as f:
            content = f.read()
        
        # Check FrozenTokenCandidate has same fields
        if "class FrozenTokenCandidate" not in content:
            self.errors.append("FrozenTokenCandidate class not found")
        else:
            # Check it has required fields
            required_fields = ["chain", "address", "symbol", "name", "decimals", "price_usd", "volume_24h"]
            for field in required_fields:
                if f"{field}:" not in content:
                    self.warnings.append(f"FrozenTokenCandidate may be missing field: {field}")
    
    def run_all_checks(self):
        """Run all verification checks."""
        print("=" * 80)
        print("END-TO-END SYSTEM VERIFICATION")
        print("=" * 80)
        
        print("\n1. Checking imports...")
        self.check_imports()
        
        print("2. Checking data flow...")
        self.check_data_flow()
        
        print("3. Checking market data extraction...")
        self.check_market_data_extraction()
        
        print("4. Checking queue connections...")
        self.check_queue_connections()
        
        print("5. Checking consumer loop...")
        self.check_consumer_loop()
        
        print("6. Checking trading loop...")
        self.check_trading_loop()
        
        print("7. Checking error handling...")
        self.check_error_handling()
        
        print("8. Checking type compatibility...")
        self.check_type_compatibility()
        
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        else:
            print("\n✅ No errors found")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        else:
            print("\n✅ No warnings")
        
        print("=" * 80)
        
        return len(self.errors) == 0

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    verifier = EndToEndVerifier(project_root)
    success = verifier.run_all_checks()
    sys.exit(0 if success else 1)
