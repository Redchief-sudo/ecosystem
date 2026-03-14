"""
Core foundation classes for the trading system.

This module provides base classes and common patterns used throughout
the codebase to reduce duplication and improve maintainability.
"""

def _import_classes():
    """Import foundation classes with delayed imports to avoid circular dependencies."""
    # Removed broken imports: health_checkable, logged_component, singleton, database_manager
    # These files had import failures and are not used anywhere in the codebase
    # If needed in the future, use:
    # - core.health_check.HealthStatus for health checks
    # - Standard Python logging module for logging
    # - No singleton pattern needed (no usage found)
    # - No database_manager needed (empty file)
    return None

# Initialize classes when module is first imported
try:
    _import_classes()
except ImportError:
    # If imports fail due to circular dependencies, classes will be available after first use
    pass

__all__ = [
    # Removed broken exports - these classes are not used and imports fail
    # Use core.health_check, core.metrics, and standard logging instead
]
