"""
Core foundation classes for the trading system.

This module provides base classes and common patterns used throughout
the codebase to reduce duplication and improve maintainability.
"""

def _import_classes():
    """Import foundation classes with delayed imports to avoid circular dependencies."""
    from .database_manager import DatabaseManager
    from .health_checkable import AsyncHealthCheckable, HealthCheckable
    from .logged_component import ContextLogger, LoggedComponent
    from .singleton import Singleton

    # Make classes available at module level
    globals().update({
        'Singleton': Singleton,
        'HealthCheckable': HealthCheckable,
        'AsyncHealthCheckable': AsyncHealthCheckable,
        'DatabaseManager': DatabaseManager,
        'LoggedComponent': LoggedComponent,
        'ContextLogger': ContextLogger
    })
    
    return Singleton, HealthCheckable, AsyncHealthCheckable, DatabaseManager, LoggedComponent, ContextLogger

# Initialize classes when module is first imported
try:
    Singleton, HealthCheckable, AsyncHealthCheckable, DatabaseManager, LoggedComponent, ContextLogger = _import_classes()
except ImportError:
    # If imports fail due to circular dependencies, classes will be available after first use
    pass

__all__ = [
    'Singleton',
    'HealthCheckable',
    'AsyncHealthCheckable', 
    'DatabaseManager',
    'LoggedComponent',
    'ContextLogger'
]
