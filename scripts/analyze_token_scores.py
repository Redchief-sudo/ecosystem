#!/usr/bin/env python3
"""
Token Score Analyzer
-------------------
Analyzes and visualizes token score data for better decision making.
"""
import argparse
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger('score_analyzer')

class TokenScoreAnalyzer:
    """Analyzes and visualizes token score data."""
    
    def __init__(self, db_path: str = 'data/ecosystem.db'):
        """Initialize the analyzer with database path."""
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Establish a database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            
    def get_score_history(self, symbol: str = None, days: int = 7) -> pd.DataFrame:
        """Get historical score data for tokens.
        
        Args:
            symbol: Filter by token symbol (None for all tokens)
            days: Number of days of history to retrieve
            
        Returns:
            DataFrame with score history
        """
        query = """
        SELECT 
            t.symbol,
            ts.score,
            ts.score_components,
            ts.timestamp
        FROM token_scores ts
        JOIN tokens t ON ts.token_id = t.id
        WHERE ts.timestamp > datetime('now', ?)
        """
        
        params = [f'-{days} days']
        if symbol:
            query += " AND t.symbol = ?"
            params.append(symbol)
            
        query += " ORDER BY ts.timestamp"
        
        df = pd.read_sql_query(query, self.conn, params=params)
        
        if not df.empty:
            # Parse score components
            df['score_components'] = df['score_components'].apply(json.loads)
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Set timestamp as index
            df.set_index('timestamp', inplace=True)
            
        return df
    
    def analyze_score_components(self, df: pd.DataFrame) -> pd.DataFrame:
        """Analyze score components from the score history."""
        if df.empty:
            return pd.DataFrame()
            
        # Extract components into separate columns
        components = pd.json_normalize(df['score_components'])
        df = pd.concat([df, components], axis=1)
        
        # Calculate statistics
        stats = components.describe().T
        stats['mean_rank'] = stats['mean'].rank(ascending=False)
        
        return stats
    
    def plot_score_trend(self, df: pd.DataFrame, symbol: str = None):
        """Plot the score trend over time."""
        if df.empty:
            logger.warning("No data to plot")
            return
            
        plt.figure(figsize=(12, 6))
        
        if 'symbol' in df.columns and len(df['symbol'].unique()) > 1:
            # Multiple tokens
            for symbol, group in df.groupby('symbol'):
                plt.plot(group.index, group['score'], label=symbol)
            plt.title('Token Scores Over Time')
        else:
            # Single token
            plt.plot(df.index, df['score'])
            symbol = symbol or df['symbol'].iloc[0]
            plt.title(f'{symbol} Score Over Time')
        
        plt.xlabel('Time')
        plt.ylabel('Score')
        plt.ylim(0, 1)
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        # Save the plot
        os.makedirs('analysis', exist_ok=True)
        filename = f"analysis/score_trend_{symbol or 'all'}_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(filename, bbox_inches='tight', dpi=300)
        plt.close()
        logger.info(f"Saved score trend plot to {filename}")
    
    def plot_component_distribution(self, df: pd.DataFrame, symbol: str = None):
        """Plot the distribution of score components."""
        if df.empty:
            return
            
        # Extract components
        components = pd.json_normalize(df['score_components'])
        
        # Melt for plotting
        melted = components.melt(var_name='Component', value_name='Score')
        
        plt.figure(figsize=(12, 6))
        sns.boxplot(x='Component', y='Score', data=melted)
        plt.title(f'Score Component Distribution{f" - {symbol}" if symbol else ""}')
        plt.xticks(rotation=45)
        
        # Save the plot
        os.makedirs('analysis', exist_ok=True)
        filename = f"analysis/component_dist_{symbol or 'all'}_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(filename, bbox_inches='tight', dpi=300)
        plt.close()
        logger.info(f"Saved component distribution plot to {filename}")
    
    def generate_report(self, symbol: str = None, days: int = 7):
        """Generate a comprehensive analysis report."""
        self.connect()
        
        try:
            # Get score history
            df = self.get_score_history(symbol=symbol, days=days)
            
            if df.empty:
                logger.warning("No score data found")
                return
                
            # Generate plots
            self.plot_score_trend(df, symbol)
            self.plot_component_distribution(df, symbol)
            
            # Calculate statistics
            stats = self.analyze_score_components(df)
            
            # Print summary
            print("\n=== Token Score Analysis ===")
            print(f"Period: Last {days} days")
            print(f"Tokens: {df['symbol'].nunique() if 'symbol' in df.columns else 1}")
            print(f"Total scores: {len(df)}")
            
            if not stats.empty:
                print("\nScore Component Statistics:")
                print(stats[['mean', 'std', 'min', '25%', '50%', '75%', 'max', 'mean_rank']])
            
            # Save raw data
            os.makedirs('analysis', exist_ok=True)
            filename = f"analysis/score_data_{symbol or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
            df.to_csv(filename)
            logger.info(f"Saved raw score data to {filename}")
            
        finally:
            self.close()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze token score data.')
    parser.add_argument('--symbol', type=str, help='Token symbol to analyze (default: all)')
    parser.add_argument('--days', type=int, default=7, 
                       help='Number of days of history to analyze (default: 7)')
    parser.add_argument('--db', default='data/ecosystem.db',
                       help='Path to database file (default: data/ecosystem.db)')
    
    args = parser.parse_args()
    
    analyzer = TokenScoreAnalyzer(args.db)
    analyzer.generate_report(symbol=args.symbol, days=args.days)

if __name__ == "__main__":
    main()
