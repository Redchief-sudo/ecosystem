"""
Example implementation using core foundation classes.

This module demonstrates how to use the core foundation classes
to create consistent, maintainable components.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core import (AsyncHealthCheckable, ContextLogger, DatabaseManager,
                  HealthCheckable, LoggedComponent, Singleton)
from core.health_check import HealthStatus


class ExampleDatabaseManager(DatabaseManager):
    """
    Example implementation of DatabaseManager for trading data.
    
    This class demonstrates how to extend DatabaseManager with
    domain-specific functionality.
    """
    
    def __init__(self, db_path: str = "data/example.db"):
        super().__init__(db_path, name="ExampleDatabaseManager")
        self.logger.info("ExampleDatabaseManager initialized")
    
    async def _apply_migrations(self) -> None:
        """Apply database migrations for the example."""
        migrations = [
            """
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                decimals INTEGER DEFAULT 18,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token_address) REFERENCES tokens (address)
            )
            """
        ]
        
        async with self.transaction() as tx_id:
            for migration in migrations:
                await self.execute_command(migration)
        
        self.logger.info(f"Applied {len(migrations)} migrations")
    
    async def _perform_health_check(self) -> HealthStatus:
        """Perform database-specific health check."""
        try:
            # Test basic connectivity
            await self.execute_query("SELECT 1 as test")
            
            # Test table access
            tables = await self.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            
            metrics = {
                "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
                "tables_count": len(tables),
                "connection_count": self._connection_count
            }
            
            return HealthStatus(
                component=self.name,
                status=True,
                message="Database is healthy",
                metrics=metrics
            )
            
        except Exception as e:
            return HealthStatus(
                component=self.name,
                status=False,
                message=f"Database health check failed: {str(e)}",
                metrics={"error_type": type(e).__name__}
            )


class ExampleScannerComponent(AsyncHealthCheckable, LoggedComponent):
    """
    Example scanner component using foundation classes.
    
    This demonstrates how to combine multiple foundation classes
    to create a comprehensive, maintainable component.
    """
    
    def __init__(self, name: str = "ExampleScanner"):
        # Initialize foundation classes
        AsyncHealthCheckable.__init__(self, name, check_interval=30, auto_monitor=True)
        LoggedComponent.__init__(self, logger_name=f"scanner.{name.lower()}")
        
        # Component-specific state
        self.scanned_tokens: Dict[str, Dict[str, Any]] = {}
        self.scan_count = 0
        self.last_scan_time: Optional[datetime] = None
        
        self.logger.info(f"ExampleScanner initialized with monitoring")
    
    async def scan_tokens(self) -> List[Dict[str, Any]]:
        """
        Perform a token scan operation.
        
        Returns:
            List of scanned tokens
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.logger.debug("Starting token scan")
            
            # Simulate token scanning
            await asyncio.sleep(0.1)  # Simulate async operation
            
            # Generate example tokens
            new_tokens = [
                {
                    "address": f"0x{i:040x}",
                    "symbol": f"TOKEN{i}",
                    "name": f"Token {i}",
                    "score": 0.5 + (i % 10) * 0.05
                }
                for i in range(3)
            ]
            
            # Update internal state
            for token in new_tokens:
                self.scanned_tokens[token["address"]] = token
            
            self.scan_count += 1
            self.last_scan_time = start_time
            
            # Log performance
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.log_performance("token_scan", duration, {
                "tokens_found": len(new_tokens),
                "total_scanned": self.scan_count,
                "cache_size": len(self.scanned_tokens)
            })
            
            self.logger.info(f"Scan completed: {len(new_tokens)} tokens found")
            return new_tokens
            
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.log_error_with_context(e, {
                "operation": "scan_tokens",
                "duration": duration,
                "scan_count": self.scan_count
            })
            raise
    
    async def _perform_health_check(self) -> HealthStatus:
        """
        Perform scanner-specific health check.
        
        Returns:
            HealthStatus indicating scanner health
        """
        try:
            # Check if scanner is responsive
            if not hasattr(self, 'scanned_tokens'):
                return HealthStatus(
                    component=self.name,
                    status=False,
                    message="Scanner state not initialized"
                )
            
            # Check if scanner is monitoring
            if not self._is_monitoring:
                return HealthStatus(
                    component=self.name,
                    status=False,
                    message="Background monitoring not active"
                )
            
            # Get scanner metrics
            metrics = {
                "scanned_tokens_count": len(self.scanned_tokens),
                "scan_count": self.scan_count,
                "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
                "is_monitoring": self._is_monitoring,
                "monitoring_task_done": self._monitoring_task.done() if self._monitoring_task else None
            }
            
            return HealthStatus(
                component=self.name,
                status=True,
                message="Scanner is healthy and operational",
                metrics=metrics
            )
            
        except Exception as e:
            return HealthStatus(
                component=self.name,
                status=False,
                message=f"Scanner health check failed: {str(e)}",
                metrics={"error_type": type(e).__name__}
            )
    
    async def process_scan_results(self, tokens: List[Dict[str, Any]]) -> None:
        """
        Process scan results with logging and context.
        
        Args:
            tokens: List of tokens to process
        """
        context_logger = self.create_context_logger({
            "operation": "process_scan_results",
            "tokens_count": len(tokens)
        })
        
        try:
            high_score_tokens = [t for t in tokens if t.get("score", 0) > 0.7]
            
            context_logger.info("Processing scan results", extra={
                "high_score_count": len(high_score_tokens),
                "avg_score": sum(t.get("score", 0) for t in tokens) / len(tokens) if tokens else 0
            })
            
            # Process each token
            for token in tokens:
                token_context = self.create_context_logger({
                    "token_address": token["address"],
                    "token_symbol": token["symbol"]
                })
                
                if token.get("score", 0) > 0.8:
                    token_context.warning("High score token detected", extra={
                        "score": token["score"],
                        "recommendation": "monitor_closely"
                    })
                else:
                    token_context.debug("Token processed", extra={
                        "score": token["score"]
                    })
            
            # Log trade event example
            if high_score_tokens:
                self.log_trade_event("token_scan_completed", "MULTIPLE", 
                                   amount=len(high_score_tokens),
                                   additional_context={
                                       "high_score_tokens": [t["symbol"] for t in high_score_tokens]
                                   })
            
        except Exception as e:
            self.log_error_with_context(e, {
                "operation": "process_scan_results",
                "tokens_count": len(tokens)
            })
            raise


# Example usage and testing
async def main():
    """Main function demonstrating the foundation classes."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=== Example Foundation Classes Usage ===")
    
    # Example 1: Database Manager
    print("\n1. Testing Database Manager:")
    db_manager = ExampleDatabaseManager("data/example.db")
    
    try:
        await db_manager.initialize()
        health = await db_manager.health_check()
        print(f"Database Health: {health.status} - {health.message}")
        
        # Insert some test data
        await db_manager.execute_command(
            "INSERT INTO tokens (address, symbol, name) VALUES (?, ?, ?)",
            {"address": "0x123", "symbol": "TEST", "name": "Test Token"}
        )
        
        # Query data
        tokens = await db_manager.execute_query("SELECT * FROM tokens")
        print(f"Tokens in database: {len(tokens)}")
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        await db_manager.close()
    
    # Example 2: Scanner Component
    print("\n2. Testing Scanner Component:")
    scanner = ExampleScannerComponent("TestScanner")
    
    try:
        # Perform scan
        tokens = await scanner.scan_tokens()
        print(f"Scanned tokens: {len(tokens)}")
        
        # Process results
        await scanner.process_scan_results(tokens)
        
        # Check health
        health = await scanner.health_check()
        print(f"Scanner Health: {health.status} - {health.message}")
        
        # Get scanner summary
        summary = scanner.get_health_summary()
        print(f"Scanner Summary: {summary}")
        
    except Exception as e:
        print(f"Scanner error: {e}")
    finally:
        scanner.stop_monitoring()
    
    # Example 3: Context Logger
    print("\n3. Testing Context Logger:")
    logger = LoggedComponent("example")
    
    # Create context logger
    context_logger = logger.create_context_logger({
        "user_id": "12345",
        "session_id": "abc-def"
    })
    
    context_logger.info("User action performed", extra={
        "action": "token_scan",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # Add more context
    extended_logger = context_logger.add_context({"operation": "scan"})
    extended_logger.warning("Operation completed with warnings", extra={
        "warning_count": 2,
        "details": "Some warnings occurred during processing"
    })
    
    print("=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

