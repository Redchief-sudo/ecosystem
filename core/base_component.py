"""
Base Component Module
===================

Provides common base classes and patterns for ecosystem components.
Reduces code duplication and standardizes initialization patterns.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from functools import wraps

from core.logging import get_logger


def with_logger(cls):
    """
    Decorator to automatically add logger to class.
    
    Eliminates the need for repetitive logger setup in each class.
    """
    # Add logger attribute to class
    logger_name = f"{cls.__module__}.{cls.__name__}"
    setattr(cls, 'logger', get_logger(logger_name))
    return cls


class BaseComponent(ABC):
    """
    Abstract base class for all ecosystem components.
    
    Provides standardized initialization, lifecycle management, and logging.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize base component.
        
        Args:
            name: Component name for logging and identification
            config: Optional configuration dictionary
        """
        self.name = name
        self.config = config or {}
        self.logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._initialized = False
        self._started = False
        self._shutdown = False
        
        # Prevent duplicate initialization
        if hasattr(self, '_initializing') and self._initializing:
            self.logger.warning(f"Component {self.name} already initializing, skipping")
            return
        self._initializing = True
    
    @abstractmethod
    async def _do_initialize(self) -> bool:
        """
        Component-specific initialization logic.
        
        Must be implemented by subclasses.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    async def initialize(self) -> bool:
        """
        Standardized initialization with error handling and state management.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            self.logger.warning(f"Component {self.name} already initialized")
            return True
            
        self.logger.info(f"Initializing component: {self.name}")
        
        try:
            success = await self._do_initialize()
            if success:
                self._initialized = True
                self.logger.info(f"✅ Component {self.name} initialized successfully")
            else:
                self.logger.error(f"❌ Component {self.name} initialization failed")
            return success
        except Exception as e:
            self.logger.error(f"❌ Component {self.name} initialization error: {e}", exc_info=True)
            return False
        finally:
            self._initializing = False
    
    @abstractmethod
    async def _do_start(self) -> bool:
        """
        Component-specific start logic.
        
        Must be implemented by subclasses.
        
        Returns:
            True if start successful, False otherwise
        """
        pass
    
    async def start(self) -> bool:
        """
        Standardized start with error handling and state management.
        
        Returns:
            True if start successful, False otherwise
        """
        if not self._initialized:
            self.logger.error(f"Component {self.name} not initialized, cannot start")
            return False
            
        if self._started:
            self.logger.warning(f"Component {self.name} already started")
            return True
            
        self.logger.info(f"Starting component: {self.name}")
        
        try:
            success = await self._do_start()
            if success:
                self._started = True
                self.logger.info(f"✅ Component {self.name} started successfully")
            else:
                self.logger.error(f"❌ Component {self.name} start failed")
            return success
        except Exception as e:
            self.logger.error(f"❌ Component {self.name} start error: {e}", exc_info=True)
            return False
    
    @abstractmethod
    async def _do_shutdown(self) -> None:
        """
        Component-specific shutdown logic.
        
        Must be implemented by subclasses.
        """
        pass
    
    async def shutdown(self) -> None:
        """
        Standardized shutdown with error handling and state management.
        """
        if self._shutdown:
            self.logger.warning(f"Component {self.name} already shutdown")
            return
            
        self.logger.info(f"Shutting down component: {self.name}")
        
        try:
            await self._do_shutdown()
            self._shutdown = True
            self._started = False
            self.logger.info(f"✅ Component {self.name} shutdown successfully")
        except Exception as e:
            self.logger.error(f"❌ Component {self.name} shutdown error: {e}", exc_info=True)
    
    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        return self._initialized
    
    def is_started(self) -> bool:
        """Check if component is started."""
        return self._started
    
    def is_shutdown(self) -> bool:
        """Check if component is shutdown."""
        return self._shutdown


class BaseManager(BaseComponent):
    """
    Base class for manager components.
    
    Extends BaseComponent with manager-specific functionality.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._managed_items: Dict[str, Any] = {}
    
    def register_item(self, key: str, item: Any) -> None:
        """
        Register an item with this manager.
        
        Args:
            key: Unique identifier for the item
            item: The item to register
        """
        if key in self._managed_items:
            existing_item = self._managed_items[key]
            # Only warn if the value is actually changing
            if existing_item is not item:
                # For empty dict/list initialization, allow idempotent registration
                if isinstance(existing_item, dict) and isinstance(item, dict) and not existing_item and not item:
                    # Both are empty dicts, idempotent operation - no warning needed
                    self.logger.debug(f"Item {key} already registered with same value (empty dict), skipping")
                    return
                elif isinstance(existing_item, list) and isinstance(item, list) and not existing_item and not item:
                    # Both are empty lists, idempotent operation - no warning needed
                    self.logger.debug(f"Item {key} already registered with same value (empty list), skipping")
                    return
                else:
                    self.logger.warning(f"Item {key} already registered, overwriting")
        
        self._managed_items[key] = item
        self.logger.debug(f"Registered item: {key}")
    
    def get_item(self, key: str) -> Optional[Any]:
        """
        Get a registered item.
        
        Args:
            key: Identifier of the item to retrieve
            
        Returns:
            The item if found, None otherwise
        """
        return self._managed_items.get(key)
    
    def list_items(self) -> Dict[str, Any]:
        """Get all registered items."""
        return self._managed_items.copy()
    
    def remove_item(self, key: str) -> bool:
        """
        Remove a registered item.
        
        Args:
            key: Identifier of the item to remove
            
        Returns:
            True if item was removed, False if not found
        """
        if key in self._managed_items:
            del self._managed_items[key]
            self.logger.debug(f"Removed item: {key}")
            return True
        return False


# Export main classes for easy importing
__all__ = [
    'with_logger',
    'BaseComponent', 
    'BaseManager'
]
