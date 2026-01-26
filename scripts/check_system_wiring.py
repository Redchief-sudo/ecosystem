#!/usr/bin/env python3
"""
System Wiring Checker
=====================
Comprehensive end-to-end check of system components and data flow.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

class SystemChecker:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[str] = []
        self.warnings: List[str] = []
        
    def check_file(self, file_path: Path) -> Tuple[List[str], List[str]]:
        """Check a single file for issues."""
        issues = []
        warnings = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            issues.append(f"Failed to parse {file_path}: {e}")
            return issues, warnings
        
        # Check for common issues
        for node in ast.walk(tree):
            # Check for undefined attributes
            if isinstance(node, ast.Attribute):
                # This is a basic check - more sophisticated analysis needed
                pass
            
            # Check for missing imports
            if isinstance(node, ast.ImportFrom):
                # Check if module exists
                pass
        
        return issues, warnings
    
    def check_main_flow(self):
        """Check the main execution flow."""
        main_file = self.project_root / "main.py"
        
        if not main_file.exists():
            self.issues.append("main.py not found")
            return
        
        # Check key components
        checks = [
            ("decision_queue", "Queue creation and wiring"),
            ("opportunity_queue", "Queue creation and wiring"),
            ("ai_controller", "AI controller initialization"),
            ("scan_director", "Scan director initialization"),
            ("ingestion_pipeline", "Ingestion pipeline initialization"),
            ("trading_loop", "Trading loop implementation"),
            ("scanner_loop", "Scanner loop implementation"),
        ]
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        for check_name, description in checks:
            if check_name not in content:
                self.warnings.append(f"{description}: '{check_name}' not found in main.py")
    
    def check_queue_wiring(self):
        """Check queue connections."""
        main_file = self.project_root / "main.py"
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check decision_queue wiring
        if "decision_queue" in content:
            if "decision_queue=decision_queue" not in content:
                self.issues.append("decision_queue not passed to ai_controller")
            if "'decision_queue'" not in content and '"decision_queue"' not in content:
                self.warnings.append("decision_queue may not be added to composition.components")
        
        # Check opportunity_queue wiring
        if "opportunity_queue" in content:
            if "opportunity_queue=opportunity_queue" not in content:
                self.issues.append("opportunity_queue not passed to ai_controller")
            if "'opportunity_queue'" not in content and '"opportunity_queue"' not in content:
                self.warnings.append("opportunity_queue may not be added to composition.components")
    
    def check_ai_controller(self):
        """Check AI controller implementation."""
        ai_file = self.project_root / "ai" / "elite_async_ai_controller.py"
        
        if not ai_file.exists():
            self.issues.append("elite_async_ai_controller.py not found")
            return
        
        with open(ai_file, 'r') as f:
            content = f.read()
        
        required_methods = [
            "_token_consumer_loop",
            "_health_monitor_loop",
            "_regime_monitor_loop",
            "start_background_tasks",
            "start",
            "stop",
        ]
        
        for method in required_methods:
            if f"def {method}" not in content and f"async def {method}" not in content:
                self.issues.append(f"AI controller missing method: {method}")
        
        # Check _running flag usage
        if "self._running = True" not in content:
            self.issues.append("AI controller may not set _running flag correctly")
        
        if "while self._running" not in content:
            self.warnings.append("AI controller loops may not check _running flag")
    
    def check_ingestion_pipeline(self):
        """Check ingestion pipeline."""
        ingestion_file = self.project_root / "trading" / "token_pipeline" / "token_ingestion.py"
        
        if not ingestion_file.exists():
            self.issues.append("token_ingestion.py not found")
            return
        
        with open(ingestion_file, 'r') as f:
            content = f.read()
        
        if "decision_queue.put_nowait" not in content and "decision_queue.put" not in content:
            self.issues.append("Ingestion pipeline may not enqueue to decision_queue")
    
    def check_scanner_flow(self):
        """Check scanner to ingestion flow."""
        scan_director_file = self.project_root / "scanners" / "scan_director.py"
        
        if not scan_director_file.exists():
            self.warnings.append("scan_director.py not found")
            return
        
        with open(scan_director_file, 'r') as f:
            content = f.read()
        
        # Check if scan_all handles ingestion
        if "ingest_scan_results" in content:
            # Good - scan_director handles ingestion
            pass
        else:
            self.warnings.append("scan_director.scan_all() may not handle ingestion")
        
        # Check main.py scanner_loop
        main_file = self.project_root / "main.py"
        with open(main_file, 'r') as f:
            main_content = f.read()
        
        # Check for double ingestion
        if "ingest_scan_results" in main_content and "ingest_scan_results" in content:
            # Check if scanner_loop also ingests
            if "await composition.ingestion_pipeline.ingest_scan_results" in main_content:
                if "ingest_scan_results" in content:
                    self.warnings.append("Potential double ingestion: scan_director.scan_all() already ingests, but scanner_loop also ingests")
    
    def check_trading_loop(self):
        """Check trading loop implementation."""
        main_file = self.project_root / "main.py"
        
        with open(main_file, 'r') as f:
            content = f.read()
        
        # Check opportunity_queue consumption
        if "opportunity_queue.get()" not in content:
            self.issues.append("Trading loop may not consume from opportunity_queue")
        
        # Check component access
        if "composition.opportunity_queue" not in content:
            self.issues.append("Trading loop may not access opportunity_queue correctly")
    
    def run_all_checks(self):
        """Run all system checks."""
        print("=" * 80)
        print("SYSTEM END-TO-END WIRING CHECK")
        print("=" * 80)
        
        self.check_main_flow()
        self.check_queue_wiring()
        self.check_ai_controller()
        self.check_ingestion_pipeline()
        self.check_scanner_flow()
        self.check_trading_loop()
        
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
    checker = SystemChecker(project_root)
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
