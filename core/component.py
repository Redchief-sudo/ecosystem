import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)

class Component(ABC):
    """Base class for all system components"""
    
    def __init__(self, name: str, dependencies: Optional[Dict[str, Type['Component']]] = None):
        self.name = name
        self.dependencies = dependencies or {}
        self._initialized = False
        self._started = False
        
    async def initialize(self) -> bool:
        """Initialize the component and its dependencies"""
        if self._initialized:
            return True
            
        logger.info(f"Initializing {self.name}...")
        
        # Initialize dependencies first
        for dep_name, dep in self.dependencies.items():
            if not dep._initialized:
                logger.debug(f"Initializing dependency {dep_name} for {self.name}")
                if not await dep.initialize():
                    logger.error(f"Dependency {dep_name} failed to initialize")
                    return False
        
        # Initialize this component
        try:
            await self._initialize()
            self._initialized = True
            logger.info(f"Component {self.name} initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}", exc_info=True)
            return False
    
    async def start(self) -> bool:
        """Start the component"""
        if not self._initialized:
            logger.error(f"Cannot start {self.name}: not initialized")
            return False
            
        if self._started:
            return True
            
        logger.info(f"Starting {self.name}...")
        
        # Start dependencies first
        for dep_name, dep in self.dependencies.items():
            if not dep._started:
                logger.debug(f"Starting dependency {dep_name} for {self.name}")
                if not await dep.start():
                    logger.error(f"Dependency {dep_name} failed to start")
                    return False
        
        # Start this component
        try:
            await self._start()
            self._started = True
            logger.info(f"Component {self.name} started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}", exc_info=True)
            return False
    
    async def stop(self) -> None:
        """Stop the component"""
        if not self._started:
            return
            
        logger.info(f"Stopping {self.name}...")
        
        try:
            await self._stop()
            self._started = False
            logger.info(f"Component {self.name} stopped")
        except Exception as e:
            logger.error(f"Error stopping {self.name}: {e}", exc_info=True)
    
    async def shutdown(self) -> None:
        """Shutdown the component and its dependencies"""
        await self.stop()
        
        if self._initialized:
            try:
                await self._shutdown()
                logger.info(f"Component {self.name} shut down")
            except Exception as e:
                logger.error(f"Error shutting down {self.name}: {e}", exc_info=True)
            finally:
                self._initialized = False
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Component-specific initialization"""
        pass
        
    @abstractmethod
    async def _start(self) -> None:
        """Start the component's operation"""
        pass
        
    async def _stop(self) -> None:
        """Stop the component's operation"""
        pass
        
    async def _shutdown(self) -> None:
        """Component-specific shutdown logic"""
        pass
