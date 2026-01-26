#!/usr/bin/env python3
"""
Comprehensive Wiring Discrepancy Checker
========================================
Checks for wiring issues, missing connections, and method signature mismatches.
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Set

class WiringChecker:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[str] = []
        self.warnings: List[str] = []
        
    def check_method_signatures(self):
        """Check for method signature mismatches."""
        main_file = self.project_root / "main.py"
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check position manager call
        if "assess_position(opportunity, entry)" in content:
            # Check if position manager has overloaded method
            position_file = self.project_root / "position" / "position.py"
            with open(position_file, 'r') as pf:
                pos_content = pf.read()
            
            # Check for method that takes opportunity and entry
            if "def assess_position(self, opportunity" not in pos_content:
                if "def assess_position(self, position_id: str, position_data" in pos_content:
                    self.issues.append(
                        "CRITICAL: position_manager.assess_position() called with (opportunity, entry) "
                        "but method signature expects (position_id: str, position_data: Dict)"
                    )
    
    def check_none_parameters(self):
        """Check for None parameters that might cause issues."""
        main_file = self.project_root / "main.py"
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check TradingEngine
        if "TradingEngine(" in content:
            if "ai=None" in content and "risk=None" in content:
                # Check if these are actually used
                engine_file = self.project_root / "trading" / "execution" / "trade_engine.py"
                with open(engine_file, 'r') as ef:
                    engine_content = ef.read()
                
                if "self.ai" in engine_content or "self.risk" in engine_content:
                    # Check if they're actually used (not just stored)
                    if "if self.ai" in engine_content or "if self.risk" in engine_content:
                        self.warnings.append(
                            "TradingEngine initialized with ai=None and risk=None, "
                            "but these may be checked/used in the code"
                        )
        
        # Check ScanDirector
        if "ScanDirector(" in content:
            if "ai_controller=None" in content:
                scan_file = self.project_root / "scanners" / "scan_director.py"
                with open(scan_file, 'r') as sf:
                    scan_content = sf.read()
                
                if "self.ai_controller" in scan_content:
                    if "if self.ai_controller" in scan_content or "if not self.ai_controller" in scan_content:
                        # It's checked, so None might be okay
                        pass
                    elif "init_kwargs['ai'] = self.ai_controller" in scan_content:
                        self.warnings.append(
                            "ScanDirector initialized with ai_controller=None, "
                            "but it's passed to scanner init_kwargs - scanners may fail if they require ai"
                        )
    
    def check_component_dependencies(self):
        """Check if components have all required dependencies."""
        main_file = self.project_root / "main.py"
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check if all components are initialized before use
        components = [
            'strategy_manager', 'entry_manager', 'position_manager', 
            'risk_manager', 'trading_engine', 'trade_executor'
        ]
        
        for component in components:
            if f"composition.{component}" in content:
                # Check if it's in composition.components
                if f"'{component}'" not in content and f'"{component}"' not in content:
                    self.issues.append(f"Component {component} used but may not be in composition.components")
    
    def check_queue_usage(self):
        """Check queue usage patterns."""
        main_file = self.project_root / "main.py"
        ai_file = self.project_root / "ai" / "elite_async_ai_controller.py"
        
        with open(main_file, 'r') as f:
            main_content = f.read()
        
        with open(ai_file, 'r') as f:
            ai_content = f.read()
        
        # Check decision_queue
        if "decision_queue.get()" in ai_content:
            if "decision_queue.put" not in main_content and "decision_queue.put" not in ai_content:
                # Check ingestion pipeline
                ingestion_file = self.project_root / "trading" / "token_pipeline" / "token_ingestion.py"
                if ingestion_file.exists():
                    with open(ingestion_file, 'r') as f:
                        ingestion_content = f.read()
                    if "decision_queue.put" not in ingestion_content:
                        self.issues.append("decision_queue is consumed but never populated")
        
        # Check opportunity_queue
        if "opportunity_queue.get()" in main_content:
            if "opportunity_queue.put" not in ai_content:
                self.issues.append("opportunity_queue is consumed but never populated by AI controller")
    
    def check_data_flow(self):
        """Check data flow between components."""
        main_file = self.project_root / "main.py"
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check if entry manager gets proper data
        if "entry_manager.assess_opportunity" in content:
            # We already fixed this, but verify
            if "entry_data = {" in content:
                self.warnings.append("Entry manager data preparation exists - verify all required fields are provided")
        
        # Check if position manager gets proper data
        if "position_manager.assess_position" in content:
            if "assess_position(opportunity, entry)" in content:
                self.issues.append("Position manager called with wrong signature - needs position_id and position_data dict")
    
    def run_all_checks(self):
        """Run all wiring checks."""
        print("=" * 80)
        print("COMPREHENSIVE WIRING DISCREPANCY CHECK")
        print("=" * 80)
        
        print("\n1. Checking method signatures...")
        self.check_method_signatures()
        
        print("2. Checking None parameters...")
        self.check_none_parameters()
        
        print("3. Checking component dependencies...")
        self.check_component_dependencies()
        
        print("4. Checking queue usage...")
        self.check_queue_usage()
        
        print("5. Checking data flow...")
        self.check_data_flow()
        
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        
        if self.issues:
            print(f"\n❌ CRITICAL ISSUES ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  • {issue}")
        else:
            print("\n✅ No critical issues found")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        else:
            print("\n✅ No warnings")
        
        print("=" * 80)
        
        return len(self.issues) == 0

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    checker = WiringChecker(project_root)
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
