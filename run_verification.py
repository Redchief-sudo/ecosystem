#!/usr/bin/env python3
"""
System Verification Runner

Executes the system in safe verification mode:
- Health checks all modules
- Validates fingerprints
- Checks for errors/warnings
- Reports full status
"""

import sys
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('verification_run.log')
    ]
)
logger = logging.getLogger(__name__)

class VerificationRunner:
    """Runs system verification checks."""
    
    def __init__(self):
        self.results = {}
        self.errors = []
        self.warnings = []
        
    def log_result(self, module: str, status: str, details: str = ""):
        """Log a verification result."""
        self.results[module] = {'status': status, 'details': details}
        symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        logger.info(f"{symbol} {module}: {status} - {details}")
    
    def check_imports(self) -> bool:
        """Verify all critical imports work."""
        logger.info("=" * 70)
        logger.info("STEP 1: CHECKING CRITICAL IMPORTS")
        logger.info("=" * 70)
        
        imports = {
            'config': 'from config import load_config',
            'fingerprint': 'from core.fingerprint import generate_fingerprint, validate_fingerprint',
            'ai_controller': 'from ai.elite_async_ai_controller import EliteAsyncAIController',
            'task_manager': 'from core.task_manager import task_manager',
            'network_manager': 'from networks.universal_network_manager import UniversalNetworkManager',
            'trade_executor': 'from trading.execution.trade_executor import HybridTradeExecutor',
            'models': 'from core.models import TradeOpportunity, TokenInfo, MarketData',
        }
        
        all_passed = True
        for name, import_stmt in imports.items():
            try:
                exec(import_stmt)
                self.log_result(f"Import: {name}", "PASS", "Module imports successfully")
            except Exception as e:
                self.log_result(f"Import: {name}", "FAIL", str(e))
                self.errors.append(f"Import {name} failed: {e}")
                all_passed = False
        
        return all_passed
    
    def check_config(self) -> bool:
        """Verify configuration loads correctly."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 2: CHECKING CONFIGURATION")
        logger.info("=" * 70)
        
        try:
            from config import load_config
            config = load_config()
            
            # Check required sections
            required_sections = ['trading', 'networks', 'strategies', 'ai']
            for section in required_sections:
                if section not in config:
                    self.log_result(f"Config: {section}", "FAIL", "Section missing")
                    self.errors.append(f"Config section '{section}' missing")
                    return False
                else:
                    self.log_result(f"Config: {section}", "PASS", f"Section present")
            
            # Check network and strategy counts
            network_count = len(config.get('networks', {}))
            strategy_count = len(config.get('strategies', {}))
            
            self.log_result("Config: networks", "PASS", f"{network_count} networks configured")
            self.log_result("Config: strategies", "PASS", f"{strategy_count} strategies configured")
            
            return True
            
        except Exception as e:
            self.log_result("Config: load", "FAIL", str(e))
            self.errors.append(f"Config load failed: {e}")
            return False
    
    def check_fingerprints(self) -> bool:
        """Verify fingerprint system."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 3: VALIDATING FINGERPRINTS")
        logger.info("=" * 70)
        
        try:
            from core.fingerprint import (
                generate_fingerprint,
                validate_fingerprint,
                FingerprintGenerator,
                FingerprintValidator
            )
            from config import load_config
            
            config = load_config()
            
            # Generate fingerprint
            fingerprint = generate_fingerprint(config)
            self.log_result("Fingerprint: generation", "PASS", 
                          f"Hash: {fingerprint.composite_hash[:16]}...")
            
            # Validate fingerprint
            is_valid = validate_fingerprint(fingerprint)
            if is_valid:
                self.log_result("Fingerprint: validation", "PASS", "Fingerprint is valid")
            else:
                self.log_result("Fingerprint: validation", "FAIL", "Validation failed")
                self.errors.append("Fingerprint validation failed")
                return False
            
            # Check integrity
            if fingerprint.verify_integrity():
                self.log_result("Fingerprint: integrity", "PASS", "Integrity verified")
            else:
                self.log_result("Fingerprint: integrity", "FAIL", "Integrity check failed")
                self.errors.append("Fingerprint integrity check failed")
                return False
            
            # Check components
            if fingerprint.creator:
                self.log_result("Fingerprint: creator", "PASS", 
                              f"System ID: {fingerprint.creator.system_id}")
            else:
                self.log_result("Fingerprint: creator", "FAIL", "Creator missing")
                return False
            
            if fingerprint.guardian:
                self.log_result("Fingerprint: guardian", "PASS",
                              f"Security: {fingerprint.guardian.security_level}")
            else:
                self.log_result("Fingerprint: guardian", "FAIL", "Guardian missing")
                return False
            
            if fingerprint.behavioral:
                self.log_result("Fingerprint: behavioral", "PASS",
                              f"Mode: {fingerprint.behavioral.execution_mode}")
            else:
                self.log_result("Fingerprint: behavioral", "FAIL", "Behavioral missing")
                return False
            
            # Log fingerprint details
            logger.info("")
            logger.info("Fingerprint Details:")
            fp_dict = fingerprint.to_dict()
            logger.info(f"  Version: {fp_dict['fingerprint_version']}")
            logger.info(f"  System ID: {fp_dict['creator']['system_id']}")
            logger.info(f"  Networks: {fp_dict['creator']['network_count']}")
            logger.info(f"  Strategies: {fp_dict['creator']['strategy_count']}")
            logger.info(f"  Security Level: {fp_dict['guardian']['security_level']}")
            logger.info(f"  Paper Trading: {fp_dict['guardian']['paper_trading_mode']}")
            logger.info(f"  Execution Mode: {fp_dict['behavioral']['execution_mode']}")
            logger.info(f"  Composite Hash: {fp_dict['composite_hash']}")
            
            return True
            
        except Exception as e:
            self.log_result("Fingerprint: system", "FAIL", str(e))
            self.errors.append(f"Fingerprint check failed: {e}")
            return False
    
    async def check_async_components(self) -> bool:
        """Verify async components initialize correctly."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 4: CHECKING ASYNC COMPONENTS")
        logger.info("=" * 70)
        
        try:
            from ai.elite_async_ai_controller import EliteAsyncAIController
            from config import load_config
            
            config = load_config()
            
            # Create AI controller
            controller = EliteAsyncAIController(config={'ai': config.get('ai', {})})
            self.log_result("AsyncComponent: AI Controller creation", "PASS", "Created successfully")
            
            # Check fingerprint
            if controller.ecosystem_fingerprint:
                self.log_result("AsyncComponent: AI Controller fingerprint", "PASS",
                              f"Hash: {controller.ecosystem_fingerprint.composite_hash[:16]}...")
            else:
                self.log_result("AsyncComponent: AI Controller fingerprint", "WARN",
                              "Fingerprint not generated")
                self.warnings.append("AI Controller fingerprint not generated")
            
            # Initialize
            await controller.async_initialize()
            self.log_result("AsyncComponent: AI Controller init", "PASS", "Initialized successfully")
            
            # Check readiness
            is_ready = await controller.is_ready()
            if is_ready:
                self.log_result("AsyncComponent: AI Controller ready", "PASS", "Controller is ready")
            else:
                self.log_result("AsyncComponent: AI Controller ready", "WARN", "Controller not ready")
                self.warnings.append("AI Controller not ready after init")
            
            # Shutdown
            await controller.shutdown()
            self.log_result("AsyncComponent: AI Controller shutdown", "PASS", "Shutdown successfully")
            
            return True
            
        except Exception as e:
            self.log_result("AsyncComponent: AI Controller", "FAIL", str(e))
            self.errors.append(f"Async component check failed: {e}")
            return False
    
    def check_test_suite(self) -> bool:
        """Verify test suite status."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 5: CHECKING TEST SUITE STATUS")
        logger.info("=" * 70)
        
        try:
            import subprocess
            
            # Run pytest in collect-only mode
            result = subprocess.run(
                ['pytest', '--collect-only', '-q'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            # Parse output for test count
            for line in output.split('\n'):
                if 'test collected' in line or 'tests collected' in line:
                    self.log_result("TestSuite: collection", "PASS", line.strip())
                    break
            else:
                self.log_result("TestSuite: collection", "WARN", "Could not parse test count")
            
            return True
            
        except Exception as e:
            self.log_result("TestSuite: collection", "WARN", f"Could not check: {e}")
            self.warnings.append(f"Test suite check failed: {e}")
            return True  # Non-critical
    
    def generate_report(self):
        """Generate final verification report."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 70)
        
        # Count results
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r['status'] == 'PASS')
        failed = sum(1 for r in self.results.values() if r['status'] == 'FAIL')
        warned = sum(1 for r in self.results.values() if r['status'] == 'WARN')
        
        logger.info(f"Total Checks: {total}")
        logger.info(f"Passed: {passed} ✅")
        logger.info(f"Failed: {failed} ❌")
        logger.info(f"Warnings: {warned} ⚠️")
        logger.info("")
        
        if self.errors:
            logger.error("ERRORS:")
            for error in self.errors:
                logger.error(f"  - {error}")
            logger.info("")
        
        if self.warnings:
            logger.warning("WARNINGS:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
            logger.info("")
        
        # Overall status
        if failed == 0:
            logger.info("=" * 70)
            logger.info("✅ VERIFICATION PASSED")
            logger.info("=" * 70)
            logger.info("System is healthy and ready for operation")
            return True
        else:
            logger.info("=" * 70)
            logger.error("❌ VERIFICATION FAILED")
            logger.info("=" * 70)
            logger.error(f"{failed} critical checks failed")
            return False
    
    async def run_all(self) -> bool:
        """Run all verification checks."""
        logger.info("=" * 70)
        logger.info("ECOSYSTEM VERIFICATION RUN")
        logger.info(f"Started: {datetime.now(timezone.utc).isoformat()}")
        logger.info("=" * 70)
        logger.info("")
        
        # Run checks
        results = []
        results.append(self.check_imports())
        results.append(self.check_config())
        results.append(self.check_fingerprints())
        results.append(await self.check_async_components())
        results.append(self.check_test_suite())
        
        # Generate report
        success = self.generate_report()
        
        logger.info("")
        logger.info(f"Completed: {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"Log file: verification_run.log")
        logger.info("")
        
        return success

async def main():
    """Main entry point."""
    runner = VerificationRunner()
    success = await runner.run_all()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
