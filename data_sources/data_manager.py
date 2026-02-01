# data_sources/data_manager.py
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.health_check import HealthStatus, standard_health_check

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, db_path="database/trades.db", network_manager=None, **kwargs):
        """
        Unified DataManager for storing trades, positions, states, etc.
        Ensures SQLite connection is always created safely.
        
        Args:
            db_path: Path to the SQLite database file
            network_manager: Optional NetworkManager instance for network operations
            **kwargs: Additional keyword arguments (ignored for backward compatibility)
        """
        import sqlite3
        from pathlib import Path

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.network_manager = network_manager

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self._ensure_tables()

    def _ensure_tables(self):
        """Create required tables if missing."""
        # Trades table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            network TEXT,
            token TEXT,
            amount REAL,
            buy_price REAL,
            sell_price REAL,
            pnl REAL,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # First, check if tokens table exists and get its schema
        self.cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tokens'")
        tokens_schema = self.cursor.fetchone()
        
        # Check if we need to migrate the tokens table from old schema (address as primary key) to new schema (id as primary key)
        if tokens_schema and 'address TEXT PRIMARY KEY' in tokens_schema[0]:
            try:
                logger.info("Migrating tokens table from address-based PK to id-based PK...")
                
                # Start transaction
                self.cursor.execute("BEGIN TRANSACTION")
                
                # Get the current time for default timestamps
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                
                # Create a new table with the updated schema
                self.cursor.execute("""
                CREATE TABLE tokens_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    decimals INTEGER,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chain, address) ON CONFLICT IGNORE
                )
                """)
                
                # Copy data from old table to new table
                self.cursor.execute("""
                INSERT INTO tokens_new (chain, address, symbol, name, decimals, first_seen, last_updated)
                SELECT chain, address, symbol, name, decimals, 
                       COALESCE(created_at, ?) as first_seen,
                       COALESCE(updated_at, ?) as last_updated
                FROM tokens
                """, (current_time, current_time))
                
                # Get list of indexes to recreate
                self.cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='tokens'")
                indexes = self.cursor.fetchall()
                
                # Drop the old table and rename the new one
                self.cursor.execute("DROP TABLE tokens")
                self.cursor.execute("ALTER TABLE tokens_new RENAME TO tokens")
                
                # Recreate the indexes
                for index in indexes:
                    if not index[0].startswith('sqlite_autoindex_'):  # Skip auto-indexes
                        try:
                            self.cursor.execute(index[1])
                        except Exception as e:
                            logger.warning(f"Could not recreate index {index[0]}: {e}")
                
                # Commit the transaction
                self.conn.commit()
                logger.info("Successfully migrated tokens table to id-based primary key")
                
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error migrating tokens table: {e}")
                raise
        else:
            # Create the tokens table if it doesn't exist (new schema)
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                decimals INTEGER,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chain, address) ON CONFLICT IGNORE
            )
            """)
        
        # Check if last_updated column exists, if not migrate the table
        self.cursor.execute("PRAGMA table_info(tokens)")
        columns = [column[1] for column in self.cursor.fetchall()]
        
        if 'last_updated' not in columns:
            try:
                logger.info("Migrating tokens table to add last_updated column...")
                
                # Start transaction
                self.cursor.execute("BEGIN TRANSACTION")
                
                # Get the current time for default timestamps
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                
                # Check if first_seen column exists
                has_first_seen = 'first_seen' in columns
                
                # Create a new table with the updated schema
                self.cursor.execute("""
                CREATE TABLE tokens_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    decimals INTEGER,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chain, address) ON CONFLICT IGNORE
                )
                """)
                
                # Copy data from old table to new table
                if has_first_seen:
                    self.cursor.execute("""
                    INSERT INTO tokens_new (id, chain, address, symbol, name, decimals, first_seen, last_updated)
                    SELECT id, chain, address, symbol, name, decimals, first_seen, first_seen 
                    FROM tokens
                    """)
                else:
                    # If first_seen doesn't exist, use current time for both timestamps
                    self.cursor.execute("""
                    INSERT INTO tokens_new (id, chain, address, symbol, name, decimals, first_seen, last_updated)
                    SELECT id, chain, address, symbol, name, decimals, ?, ?
                    FROM tokens
                    """, (current_time, current_time))
                
                # Get list of indexes to recreate
                self.cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='tokens'")
                indexes = self.cursor.fetchall()
                
                # Drop the old table and rename the new one
                self.cursor.execute("DROP TABLE tokens")
                self.cursor.execute("ALTER TABLE tokens_new RENAME TO tokens")
                
                # Recreate the indexes
                for index in indexes:
                    if not index[0].startswith('sqlite_autoindex_'):  # Skip auto-indexes
                        try:
                            self.cursor.execute(index[1])
                        except Exception as e:
                            logger.warning(f"Could not recreate index {index[0]}: {e}")
                
                # Commit the transaction
                self.conn.commit()
                logger.info("Successfully migrated tokens table to include last_updated column")
                
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error migrating tokens table: {e}")
                raise
        
        # Token snapshots table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            price REAL,
            price_change_24h REAL,
            volume_24h REAL,
            liquidity REAL,
            market_cap REAL,
            volatility REAL,
            social_sentiment REAL,
            FOREIGN KEY(token_id) REFERENCES tokens(id)
        )
        """)
        
        # Check if volatility and social_sentiment columns exist in token_snapshots
        self.cursor.execute("PRAGMA table_info(token_snapshots)")
        columns = [column[1] for column in self.cursor.fetchall()]
        
        if 'volatility' not in columns:
            try:
                logger.info("Adding volatility column to token_snapshots table...")
                self.cursor.execute("""
                ALTER TABLE token_snapshots 
                ADD COLUMN volatility REAL
                """)
                self.conn.commit()
                logger.info("Successfully added volatility column to token_snapshots table")
            except Exception as e:
                logger.error(f"Error adding volatility column to token_snapshots: {e}")
                self.conn.rollback()
                raise
                
        if 'social_sentiment' not in columns:
            try:
                logger.info("Adding social_sentiment column to token_snapshots table...")
                self.cursor.execute("""
                ALTER TABLE token_snapshots 
                ADD COLUMN social_sentiment REAL
                """)
                self.conn.commit()
                logger.info("Successfully added social_sentiment column to token_snapshots table")
            except Exception as e:
                logger.error(f"Error adding social_sentiment column to token_snapshots: {e}")
                self.conn.rollback()
                raise
        
        # Create indexes for performance
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_snapshots_token_id 
        ON token_snapshots(token_id, timestamp)
        """)
        
        # Check if positions table exists and get its schema
        self.cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='positions'")
        positions_schema = self.cursor.fetchone()
        
        # Check if we need to migrate the positions table from old schema (token_address) to new schema (token_id)
        if positions_schema and 'token_address TEXT NOT NULL' in positions_schema[0]:
            try:
                logger.info("Migrating positions table from token_address to token_id...")
                
                # Start transaction
                self.cursor.execute("BEGIN TRANSACTION")
                
                # Create a new table with the updated schema
                self.cursor.execute("""
                CREATE TABLE positions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    pnl REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'OPEN',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(token_id) REFERENCES tokens(id)
                )
                """)
                
                # Copy data from old table to new table, joining with tokens to get token_id
                self.cursor.execute("""
                INSERT INTO positions_new (token_id, amount, entry_price, current_price, pnl, status, created_at, updated_at)
                SELECT t.id, p.amount, p.entry_price, p.current_price, p.pnl, p.status, p.created_at, p.updated_at
                FROM positions p
                JOIN tokens t ON p.token_address = t.address AND p.chain = t.chain
                """)
                
                # Get list of indexes to recreate
                self.cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='positions'")
                indexes = self.cursor.fetchall()
                
                # Drop the old table and rename the new one
                self.cursor.execute("DROP TABLE positions")
                self.cursor.execute("ALTER TABLE positions_new RENAME TO positions")
                
                # Recreate the indexes
                for index in indexes:
                    if not index[0].startswith('sqlite_autoindex_'):  # Skip auto-indexes
                        try:
                            self.cursor.execute(index[1])
                        except Exception as e:
                            logger.warning(f"Could not recreate index {index[0]}: {e}")
                
                # Commit the transaction
                self.conn.commit()
                logger.info("Successfully migrated positions table to use token_id")
                
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error migrating positions table: {e}")
                raise
        else:
            # Positions table for tracking open positions
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                pnl REAL DEFAULT 0.0,
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(token_id) REFERENCES tokens(id)
            )
        """)
        
        # Create indexes for positions table
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_positions_token_id 
        ON positions(token_id)
        """)
        
        self.cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_positions_status 
        ON positions(status)
        """)
        
        self.conn.commit()

    def close(self):
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
            except Exception:
                pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
    
    # Trade methods
    def get_trade_history(self, status=None):
        """
        Returns trade rows. If status provided, filters by OPEN / CLOSED.
        """
        query = "SELECT * FROM trades"
        params = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        with self.conn:
            cur = self.conn.execute(query, params)
            rows = cur.fetchall()

        return rows
        
    # Token methods
    def get_or_create_token(self, chain: str, address: str, symbol: str, 
                           name: str = None, decimals: int = None) -> str:
        """
        Get or create a token in database.
    
        Args:
             chain: Blockchain network (e.g., 'ethereum', 'arbitrum')
             address: Token contract address
             symbol: Token symbol
             name: Token name (optional)
             decimals: Token decimals (optional)
        
        Returns:
             str: Token ID (database integer ID, not address)
        """
        # Try to get existing token
        self.cursor.execute(
            "SELECT id FROM tokens WHERE chain = ? AND LOWER(address) = LOWER(?)",
            (chain, address)
        )
        token = self.cursor.fetchone()
    
        if token:
            token_id = token[0]  # Get integer ID
            # Update token info if needed
            self.cursor.execute(
                """
                UPDATE tokens 
                SET symbol = ?, name = ?, decimals = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (symbol, name, decimals, token_id)
            )
        else:
            # Create new token
            self.cursor.execute(
                """
                INSERT INTO tokens (chain, address, symbol, name, decimals)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chain, address, symbol, name, decimals)
            )
            token_id = self.cursor.lastrowid  # Get integer ID
        
        self.conn.commit()
        return str(token_id)

    def get_token_by_address(self, chain: str, address: str) -> dict:
        """
        Get token data by address.
    
        Args:
            chain: Blockchain network
            address: Token contract address
        
        Returns:
            dict: Token data or None if not found
        """
        self.cursor.execute(
            "SELECT * FROM tokens WHERE chain = ? AND LOWER(address) = LOWER(?)",
            (chain, address)
        )
        token = self.cursor.fetchone()
        if not token:
            return None
        
        columns = [d[0] for d in self.cursor.description]
        return dict(zip(columns, token))

    def save_token_snapshot(self, token_id: str, **kwargs) -> int:
        """
        Save a snapshot of token data.
    
        Args:
            token_id: Token ID (integer, from get_or_create_token)
            **kwargs: Token data fields to save
        
        Returns:
            int: Snapshot ID or None if failed
        """
        # Only include valid columns
        valid_columns = [
            'price', 'price_change_24h', 'volume_24h', 'liquidity',
            'market_cap', 'volatility', 'social_sentiment'
        ]
    
        # Filter and prepare data
        data = {k: v for k, v in kwargs.items() if k in valid_columns and v is not None}
    
        if not data:
            return None
        
        try:
            # Convert token_id to integer
            token_id_int = int(token_id)
            
            # Add current timestamp with millisecond precision to ensure uniqueness
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
            # Prepare the data for insertion
            columns = ['token_id', 'timestamp'] + list(data.keys())
            placeholders = ['?'] * len(columns)
            values = [token_id_int, timestamp] + [data[k] for k in columns[2:]]
        
            # First, try to update existing record for this timestamp if it exists
            set_clause = ', '.join([f"{col} = ?" for col in columns[2:]])
            update_values = [data[k] for k in columns[2:]] + [token_id_int, timestamp]
        
            self.cursor.execute(
                f"""
                UPDATE token_snapshots 
                SET {set_clause}
                WHERE token_id = ? AND timestamp = ?
                """,
                update_values
            )
        
            # If no rows were updated, insert a new record
            if self.cursor.rowcount == 0:
                query = f"""
                INSERT INTO token_snapshots ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                """
                self.cursor.execute(query, values)
        
            self.conn.commit()
            return self.cursor.lastrowid
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error saving token snapshot: {e}")
            return None

    def get_token_history(self, token_id: str, limit: int = 100) -> list:
        """
        Get historical snapshots for a token.
    
        Args:
            token_id: Token ID
            limit: Maximum number of snapshots to return
        
        Returns:
            list: List of token snapshots
        """
        self.cursor.execute(
            """
            SELECT * FROM token_snapshots 
            WHERE token_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (token_id, limit)
        )
        rows = self.cursor.fetchall()
    
        if not rows:
            return []
    
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_price_history(self, token_address: str, chain: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical price and volume data for a token.
        
        Fetches from token_snapshots table which is continuously updated by scanners
        and other data sources with price, volume, liquidity, etc.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
            limit: Maximum number of historical points to return
            
        Returns:
            List of snapshots with price, volume_24h, liquidity, timestamp, etc.
            Ordered from oldest to newest (ascending by timestamp).
        """
        try:
            # Get token ID from address and chain
            self.cursor.execute(
                """
                SELECT id FROM tokens 
                WHERE address = ? AND chain = ?
                """,
                (token_address, chain)
            )
            result = self.cursor.fetchone()
            
            if not result:
                logger.debug(f"No token found for {token_address} on {chain}")
                return []
            
            token_id = result[0]
            
            # Fetch historical snapshots, ordered oldest to newest
            self.cursor.execute(
                """
                SELECT * FROM token_snapshots 
                WHERE token_id = ? 
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (token_id, limit)
            )
            
            rows = self.cursor.fetchall()
            
            if not rows:
                logger.debug(f"No historical data found for token {token_id}")
                return []
            
            columns = [d[0] for d in self.cursor.description]
            snapshots = [dict(zip(columns, row)) for row in rows]
            
            logger.debug(f"Retrieved {len(snapshots)} historical snapshots for {token_address} on {chain}")
            return snapshots
        
        except Exception as e:
            logger.error(f"Error fetching price history for {token_address} on {chain}: {e}")
            return []

    @standard_health_check("Data Manager")
    async def health_check(self) -> HealthStatus:
        """Check database connection and basic functionality."""
        try:
            # Test connection with a simple query
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = self.cursor.fetchall()
            
            # Check if required tables exist
            required_tables = {'trades', 'positions'}
            existing_tables = {t[0] for t in tables}
            missing_tables = required_tables - existing_tables
            
            is_healthy = not missing_tables
            return HealthStatus(
                component="Data Manager",
                status=is_healthy,
                message=(
                    "Database connection healthy" if is_healthy 
                    else f"Missing required tables: {', '.join(missing_tables)}"
                ),
                metrics={
                    "status": "healthy" if is_healthy else "degraded",
                    "tables_found": len(tables),
                    "missing_tables": list(missing_tables),
                    "db_path": str(self.db_path),
                    "connection_active": True
                }
            )
        except Exception as e:
            return HealthStatus(
                component="Data Manager",
                status=False,
                message=f"Database error: {str(e)}",
                metrics={
                    "status": "unhealthy",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
