#!/usr/bin/env python3
"""
Token Score Tracker
------------------
Tracks and stores token scores over time for analysis and decision making.
"""
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.score_engine import EnhancedScoreEngine
from bootstrap.path_manager import get_path_manager
from data_sources import DataManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/token_scoring.log')
    ]
)
logger = logging.getLogger('token_scoring')

class TokenScoreTracker:
    """Tracks and stores token scores over time."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the token score tracker."""
        if config_path is None:
            path_manager = get_path_manager()
            config_file = path_manager.get_config_path('ai')
            if not config_file:
                raise FileNotFoundError("AI config file not found")
        else:
            config_file = config_path
            
        self.config = self._load_config(str(config_file))
        
        path_manager = get_path_manager()
        db_path = path_manager.get_database_path()
        self.data_manager = DataManager(str(db_path))
        self.score_engine = EnhancedScoreEngine(self.config, self.data_manager)
        
        # Ensure logs directory exists using path manager
        logs_path = path_manager.project_root / 'logs'
        logs_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize database tables if they don't exist
        self._init_database()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        import yaml
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _init_database(self):
        """Initialize the database tables if they don't exist."""
        with self.data_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create token_scores table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id INTEGER NOT NULL,
                score REAL NOT NULL,
                score_components TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token_id) REFERENCES tokens (id),
                UNIQUE(token_id, timestamp)
            )
            ''')
            
            # Create index for faster lookups
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_token_scores_token_id 
            ON token_scores(token_id)
            ''')
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_token_scores_timestamp 
            ON token_scores(timestamp)
            ''')
            
            conn.commit()
    
    def get_active_tokens(self, min_liquidity: float = 10000.0) -> List[Dict[str, Any]]:
        """Get a list of active tokens with sufficient liquidity."""
        query = """
        SELECT t.id, t.chain, t.address, t.symbol, t.name, t.decimals,
               s.price, s.volume_24h, s.liquidity, s.market_cap,
               s.price_change_24h, s.volatility, s.social_sentiment
        FROM tokens t
        JOIN (
            SELECT token_id, MAX(timestamp) as latest
            FROM token_snapshots
            WHERE timestamp > datetime('now', '-1 day')
            GROUP BY token_id
        ) latest_snap ON t.id = latest_snap.token_id
        JOIN token_snapshots s ON s.token_id = latest_snap.token_id 
                             AND s.timestamp = latest_snap.latest
        WHERE s.liquidity >= ?
        ORDER BY s.liquidity DESC
        """
        
        with self.data_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (min_liquidity,))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def score_token(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score a single token and return the results."""
        try:
            # Format token data for scoring
            token_for_scoring = {
                'chain': token_data['chain'],
                'token_address': token_data['address'],
                'symbol': token_data['symbol'],
                'price': token_data['price'],
                'liquidity': token_data['liquidity'],
                'volume_24h': token_data['volume_24h'],
                'decimals': token_data.get('decimals', 18),
                'price_change_24h': token_data.get('price_change_24h', 0),
                'market_cap': token_data.get('market_cap', 0),
                'volatility': token_data.get('volatility', 0.1),
                'sentiment': token_data.get('social_sentiment', 0.5)
            }
            
            # Get the score
            scored = self.score_engine.score_opportunities([token_for_scoring])
            if not scored:
                logger.warning(f"No score returned for {token_data['symbol']}")
                return None
                
            result = scored[0]
            
            # Store the score in the database
            self._store_score(
                token_id=token_data['id'],
                score=result['score'],
                components=result.get('score_components', {})
            )
            
            logger.info(
                f"✅ Scored {token_data['symbol']}: {result['score']:.4f} | "
                f"Liq: ${token_data['liquidity']:,.2f}M | "
                f"Vol: ${token_data['volume_24h']/1_000_000:.2f}M | "
                f"24h: {token_data.get('price_change_24h', 0):+.2f}%"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error scoring token {token_data.get('symbol')}: {str(e)}", 
                        exc_info=True)
            return None
    
    def _store_score(self, token_id: int, score: float, components: Dict[str, float]):
        """Store a token score in the database."""
        try:
            with self.data_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR IGNORE INTO token_scores 
                (token_id, score, score_components, timestamp)
                VALUES (?, ?, ?, datetime('now'))
                ''', (token_id, score, json.dumps(components)))
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing score for token {token_id}: {str(e)}")
    
    def run(self, interval_minutes: int = 15, min_liquidity: float = 10000.0):
        """Run the token scoring process on a schedule."""
        logger.info("🚀 Starting token score tracker...")
        
        try:
            while True:
                start_time = time.time()
                
                # Get active tokens
                tokens = self.get_active_tokens(min_liquidity=min_liquidity)
                logger.info(f"🔍 Found {len(tokens)} active tokens with sufficient liquidity")
                
                # Score each token
                scores = []
                for token in tokens:
                    score = self.score_token(token)
                    if score:
                        scores.append((token['symbol'], score['score']))
                
                # Log summary
                if scores:
                    avg_score = sum(s[1] for s in scores) / len(scores)
                    top_5 = sorted(scores, key=lambda x: x[1], reverse=True)[:5]
                    logger.info(
                        f"📊 Scored {len(scores)} tokens | "
                        f"Avg: {avg_score:.3f} | "
                        f"Top: {', '.join(f'{s[0]}={s[1]:.3f}' for s in top_5)}"
                    )
                
                # Sleep until next interval
                elapsed = time.time() - start_time
                sleep_time = max(0, (interval_minutes * 60) - elapsed)
                logger.info(f"⏳ Next update in {sleep_time/60:.1f} minutes")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Received exit signal, shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Track and store token scores over time.')
    parser.add_argument('--interval', type=int, default=15,
                       help='Scoring interval in minutes (default: 15)')
    parser.add_argument('--min-liquidity', type=float, default=10000.0,
                       help='Minimum liquidity in USD (default: 10000)')
    parser.add_argument('--config', default='config/ai_config.yaml',
                       help='Path to config file (default: config/ai_config.yaml)')
    
    args = parser.parse_args()
    
    try:
        tracker = TokenScoreTracker(args.config)
        tracker.run(
            interval_minutes=args.interval,
            min_liquidity=args.min_liquidity
        )
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
