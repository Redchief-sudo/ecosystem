"""
Base AI Module
--------------
Base class for all AI components in the trading system.
"""
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

from core.health_check import HealthStatus, standard_health_check

logger = logging.getLogger('ai.base')

class BaseAI(ABC):
    """Base class for all AI components with common functionality."""
    
    def __init__(self, config: Dict[str, Any], model_path: str = None):
        """
        Initialize the base AI component.
        
        Args:
            config: Configuration dictionary
            model_path: Optional path to save/load the model
        """
        self.config = config
        self.model = None
        self.model_path = model_path or self._get_default_model_path()
        self.performance_metrics = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'last_retrain': None
        }
        self._load_model()
        
    def _get_default_model_path(self) -> str:
        """Get default model path based on class name."""
        model_dir = self.config.get('ai', {}).get('model_dir', 'models')
        Path(model_dir).mkdir(parents=True, exist_ok=True)
        return str(Path(model_dir) / f"{self.__class__.__name__.lower()}.pkl")
        
    def _load_model(self):
        """Load model from disk if it exists."""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded model from {self.model_path}")
            else:
                self._init_model()
                logger.info(f"Initialized new model (not found at {self.model_path})")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self._init_model()
            
    def _init_model(self):
        """Initialize a new model. Override in subclasses."""
        self.model = None
        
    def save_model(self):
        """Save model to disk."""
        try:
            if self.model is not None:
                Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(self.model, self.model_path)
                logger.info(f"Saved model to {self.model_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False
            
    async def retrain(self, data: Optional[Any] = None):
        """Retrain the model with new data."""
        try:
            logger.info(f"Retraining {self.__class__.__name__}...")
            if data is None:
                data = await self._load_training_data()
                
            if data:
                await self._train_model(data)
                self.save_model()
                self.performance_metrics['last_retrain'] = datetime.now(timezone.utc)
                logger.info(f"Retrained {self.__class__.__name__} successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Error retraining model: {e}", exc_info=True)
            return False
            
    async def _load_training_data(self):
        """Load training data. Override in subclasses."""
        return None
        
    async def _train_model(self, data: Any):
        """Train the model. Override in subclasses."""
        pass
        
    async def evaluate_performance(self, actual: Any, predicted: Any) -> Dict[str, float]:
        """Evaluate prediction performance."""
        self.performance_metrics['total_predictions'] += 1
        if actual == predicted:
            self.performance_metrics['correct_predictions'] += 1
            
        accuracy = (self.performance_metrics['correct_predictions'] / 
                   max(1, self.performance_metrics['total_predictions']))
                   
        return {
            'accuracy': accuracy,
            'total_predictions': self.performance_metrics['total_predictions'],
            'correct_predictions': self.performance_metrics['correct_predictions']
        }
        
    @standard_health_check("AI Component")
    async def health_check(self) -> HealthStatus:
        """Check the health of the AI component.
        
        Returns:
            HealthStatus: Standardized health status with performance metrics
        """
        performance = await self.evaluate_performance(None, None)
        is_healthy = self.model is not None
        
        return HealthStatus(
            component="AI Component",
            status=is_healthy,
            message="AI model is ready" if is_healthy else "AI model not initialized",
            metrics={
                "status": "healthy" if is_healthy else "uninitialized",
                "performance": performance,
                "last_retrain": self.performance_metrics['last_retrain'],
                "model_loaded": self.model is not None,
                "total_predictions": self.performance_metrics['total_predictions'],
                "correct_predictions": self.performance_metrics['correct_predictions']
            }
        )
