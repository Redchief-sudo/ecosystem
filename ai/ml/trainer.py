# /home/damien/ecosystem/ml/trainer.py
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MLTrainer")

@dataclass
class TrainingConfig:
    """Configuration for model training."""
    test_size: float = 0.2
    n_splits: int = 5
    random_state: int = 42
    n_trials: int = 50
    early_stopping_rounds: int = 50
    feature_importance_threshold: float = 0.01
    models_dir: str = str(Path(__file__).parent.parent / "models")
    data_dir: str = str(Path(__file__).parent.parent / "data")

class ModelTrainer:
    """Handles model training, evaluation, and persistence for the ecosystem."""
    
    def __init__(self, config: TrainingConfig = None):
        self.config = config or TrainingConfig()
        self.model = None
        self.features = None
        self.scaler = None
        self.best_params = None
        self.metrics = {}
        self.feature_importances_ = None
        
        # Ensure directories exist
        Path(self.config.models_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
    
    def prepare_data(self, token_data: List[Dict]) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare token data for training."""
        logger.info("Preparing training data...")
        
        # Convert to DataFrame
        df = pd.DataFrame(token_data)
        
        # Feature engineering
        df = self._engineer_features(df)
        
        # Define features based on required fields
        self.features = [
            'price', 'volume_24h', 'liquidity_usd', 
            'price_change_5m', 'price_change_1h',
            'strength', 'zscore', 'ai_score', 'momentum'
        ]
        
        # Ensure all features are present
        for feature in self.features:
            if feature not in df.columns:
                df[feature] = 0
                logger.warning(f"Missing feature in training data: {feature}")
        
        # Handle missing values
        df = df.fillna(0)
        
        # Define target (next period price movement)
        df['target'] = df['price'].pct_change().shift(-1)
        df = df.dropna(subset=['target'])
        
        return df[self.features], df['target']
    
    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Train the model with cross-validation."""
        logger.info("Starting model training...")
        
        try:
            import numpy as np
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.metrics import mean_squared_error, r2_score
            from sklearn.model_selection import (TimeSeriesSplit,
                                                 cross_val_score)
            from sklearn.preprocessing import StandardScaler
            from xgboost import XGBRegressor
        except ImportError as e:
            logger.error(f"Required packages not found: {e}")
            raise
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Initialize model
        model = XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.01,
            subsample=0.8,
            colsample_bytree=0.8,
            n_jobs=-1,
            random_state=self.config.random_state
        )
        
        # Cross-validation
        tscv = TimeSeriesSplit(n_splits=self.config.n_splits)
        cv_scores = cross_val_score(
            model, X_scaled, y,
            cv=tscv,
            scoring='neg_mean_squared_error',
            n_jobs=-1
        )
        
        # Train final model
        model.fit(X_scaled, y)
        self.model = model
        self.feature_importances_ = self._get_feature_importances(model, X.columns)
        
        # Calculate metrics
        y_pred = model.predict(X_scaled)
        self.metrics = {
            'train_r2': r2_score(y, y_pred),
            'train_rmse': np.sqrt(mean_squared_error(y, y_pred)),
            'cv_mean_rmse': np.mean(np.sqrt(-cv_scores)),
            'cv_std_rmse': np.std(np.sqrt(-cv_scores)),
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'n_samples': len(X),
            'n_features': len(self.features)
        }
        
        logger.info(f"Training complete. CV RMSE: {self.metrics['cv_mean_rmse']:.6f}")
        return self.metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using the trained model."""
        if self.model is None or self.scaler is None:
            raise ValueError("Model has not been trained yet")
            
        X_scaled = self.scaler.transform(X[self.features])
        return self.model.predict(X_scaled)
    
    def save_model(self, model_name: str = None) -> str:
        """Save the trained model to disk."""
        if self.model is None:
            raise ValueError("No model has been trained yet")
            
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_name = model_name or f"model_{timestamp}"
        model_path = os.path.join(self.config.models_dir, f"{model_name}.joblib")
        
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'features': self.features,
            'metrics': self.metrics,
            'best_params': self.best_params,
            'feature_importances': self.feature_importances_,
            'config': self.config
        }, model_path)
        
        logger.info(f"Model saved to {model_path}")
        return model_path
    
    @classmethod
    def load_model(cls, model_path: str) -> 'ModelTrainer':
        """Load a trained model from disk."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
            
        data = joblib.load(model_path)
        
        trainer = cls()
        trainer.model = data['model']
        trainer.scaler = data['scaler']
        trainer.features = data['features']
        trainer.metrics = data['metrics']
        trainer.best_params = data.get('best_params')
        trainer.feature_importances_ = data.get('feature_importances')
        trainer.config = data.get('config', TrainingConfig())
        
        return trainer
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create additional features for the model."""
        # Ensure required columns exist
        if 'price' not in df.columns:
            raise ValueError("Input data must contain 'price' column")
            
        # Price-based features
        if 'returns' not in df.columns:
            df['returns'] = df['price'].pct_change()
            
        if 'volatility' not in df.columns:
            df['volatility'] = df['returns'].rolling(window=21).std() * np.sqrt(365)
            
        if 'momentum' not in df.columns:
            df['momentum'] = df['price'] / df['price'].shift(21) - 1
            
        # Volume-based features
        if 'volume_24h' in df.columns and 'volume_ma' not in df.columns:
            df['volume_ma'] = df['volume_24h'].rolling(window=7).mean()
            df['volume_ratio'] = df['volume_24h'] / df['volume_ma']
            
        # Technical indicators if not present
        if 'rsi' not in df.columns and 'returns' in df.columns:
            delta = df['returns'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['rsi'] = 100 - (100 / (1 + (gain / loss)))
            
        return df
    
    @staticmethod
    def _get_feature_importances(model, feature_names) -> Dict[str, float]:
        """Extract and format feature importances."""
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            importances = np.abs(model.coef_)
        else:
            return {}
            
        return dict(zip(feature_names, importances))

# Example usage
if __name__ == "__main__":
    # Example with dummy data
    import numpy as np
    
    np.random.seed(42)
    n_samples = 1000
    data = pd.DataFrame({
        'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=n_samples, freq='H'),
        'price': np.cumsum(np.random.randn(n_samples)) + 100,
        'volume_24h': np.random.lognormal(5, 1, n_samples),
        'liquidity_usd': np.random.lognormal(10, 1, n_samples),
        'price_change_5m': np.random.normal(0, 0.001, n_samples),
        'price_change_1h': np.random.normal(0, 0.005, n_samples),
        'strength': np.random.uniform(0, 1, n_samples),
        'zscore': np.random.normal(0, 1, n_samples),
        'ai_score': np.random.uniform(0, 1, n_samples),
        'momentum': np.random.normal(0, 0.01, n_samples)
    })
    
    try:
        # Initialize and train model
        trainer = ModelTrainer()
        X, y = trainer.prepare_data(data)
        metrics = trainer.train(X, y)
        
        # Save model
        model_path = trainer.save_model()
        print(f"Model trained and saved to {model_path}")
        print(f"Training metrics: {metrics}")
        
        # Example prediction
        sample = X.iloc[:5]  # First 5 samples
        predictions = trainer.predict(sample)
        print(f"Sample predictions: {predictions}")
        
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)

