"""
Singleton pattern implementation for the trading system.

This module provides a centralized singleton metaclass that can be used
by any class requiring singleton behavior throughout the codebase.
"""

import threading
from typing import Any, Dict, Type, TypeVar

T = TypeVar('T')

class Singleton(type):
    """
    Thread-safe singleton metaclass.
    
    This metaclass ensures that only one instance of a class exists at any time,
    while being thread-safe. It provides consistent singleton behavior across
    all components that use it.
    
    Usage:
        class MyClass(metaclass=Singleton):
            def __init__(self):
                # initialization code
                pass
    """
    
    _instances: Dict[Type[Any], Any] = {}
    _lock: threading.Lock = threading.Lock()
    _initialized: Dict[Type[Any], bool] = {}
    
    def __call__(cls: Type[T], *args, **kwargs) -> T:
        """
        Create or return the singleton instance.
        
        Args:
            cls: The class being instantiated
            *args: Positional arguments for class initialization
            **kwargs: Keyword arguments for class initialization
            
        Returns:
            The singleton instance of the class
        """
        # Double-checked locking pattern for thread safety
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    # Create the instance
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
                    cls._initialized[cls] = False
        
        return cls._instances[cls]
    
    def is_initialized(cls) -> bool:
        """Check if the singleton instance has been initialized."""
        return cls._initialized.get(cls, False)
    
    def mark_initialized(cls) -> None:
        """Mark the singleton instance as initialized."""
        cls._initialized[cls] = True
    
    def reset(cls) -> None:
        """
        Reset the singleton instance (mainly for testing).
        
        Warning: This should only be used in testing scenarios as it
        can break the singleton contract.
        """
        with cls._lock:
            if cls in cls._instances:
                instance = cls._instances[cls]
                # Call cleanup if the instance has a cleanup method
                if hasattr(instance, 'cleanup') and callable(instance.cleanup):
                    try:
                        instance.cleanup()
                    except Exception:
                        pass  # Ignore cleanup errors
                
                del cls._instances[cls]
                if cls in cls._initialized:
                    del cls._initialized[cls]
