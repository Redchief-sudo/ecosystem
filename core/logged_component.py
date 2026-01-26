"""
Logged component base classes for the trading system.

This module provides standardized logging patterns used throughout
the codebase to ensure consistent logging across all components.
"""

import logging
from typing import Any, Dict, Optional


class LoggedComponent:
    """
    Base class for components that require standardized logging.
    
    This class provides consistent logging setup and management across
    all system components. Subclasses can customize logging behavior
    while maintaining a consistent interface.
    
    Features:
    - Standardized logger initialization
    - Component-specific logging configuration
    - Support for structured logging
    - Logging level management
    - Context-aware logging
    
    Usage:
        class MyComponent(LoggedComponent):
            def __init__(self):
                super().__init__()
                self.logger.info("Component initialized")
            
            def do_something(self):
                self.logger.debug("Doing something...")
                self.logger.warning("This is a warning")
                self.logger.error("This is an error")
    """
    
    def __init__(self, logger_name: Optional[str] = None, 
                 log_level: int = logging.INFO,
                 enable_structured_logging: bool = True):
        """
        Initialize the logged component.
        
        Args:
            logger_name: Custom logger name (defaults to class module)
            log_level: Initial logging level
            enable_structured_logging: Whether to enable structured logging features
        """
        self.enable_structured_logging = enable_structured_logging
        self.log_level = log_level
        
        # Set up logger
        if logger_name:
            self.logger = logging.getLogger(logger_name)
        else:
            # Use the module name of the current class
            self.logger = logging.getLogger(self.__class__.__module__)
        
        # Configure logger if not already configured
        self._setup_logger()
        
        # Log initialization
        self.logger.debug(f"LoggedComponent initialized: {self.__class__.__name__}")
    
    def _setup_logger(self) -> None:
        """
        Configure the logger with default settings.
        
        This method can be overridden by subclasses to customize
        logger configuration (e.g., adding custom formatters, handlers).
        """
        # Set logging level if not already set
        if self.logger.level == logging.NOTSET:
            self.logger.setLevel(self.log_level)
        
        # Add handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def set_log_level(self, level: int) -> None:
        """
        Set the logging level for this component.
        
        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        self.logger.setLevel(level)
        self.log_level = level
        self.logger.debug(f"Log level set to {logging.getLevelName(level)}")
    
    def log_performance(self, operation: str, duration: float, 
                       additional_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log performance metrics for an operation.
        
        Args:
            operation: Name of the operation being performed
            duration: Time taken for the operation (seconds)
            additional_context: Additional context to log
        """
        context = {
            "operation": operation,
            "duration_seconds": duration,
            "duration_ms": duration * 1000
        }
        
        if additional_context:
            context.update(additional_context)
        
        if self.enable_structured_logging:
            self.logger.info(f"Performance: {operation} completed", extra=context)
        else:
            self.logger.info(f"Performance: {operation} completed in {duration:.3f}s")
    
    def log_api_call(self, api_name: str, endpoint: str, status_code: Optional[int] = None,
                    response_time: Optional[float] = None,
                    additional_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log API call details.
        
        Args:
            api_name: Name of the API being called
            endpoint: API endpoint being accessed
            status_code: HTTP status code returned
            response_time: Time taken for the API call (seconds)
            additional_context: Additional context to log
        """
        context = {
            "api_call": api_name,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_seconds": response_time
        }
        
        if additional_context:
            context.update(additional_context)
        
        level = logging.INFO if (status_code and 200 <= status_code < 300) else logging.WARNING
        
        if self.enable_structured_logging:
            self.logger.log(level, f"API call: {api_name} {endpoint}", extra=context)
        else:
            status_str = f" (status: {status_code})" if status_code else ""
            time_str = f" in {response_time:.3f}s" if response_time else ""
            self.logger.log(level, f"API call: {api_name} {endpoint}{status_str}{time_str}")
    
    def log_trade_event(self, event_type: str, symbol: str, amount: Optional[float] = None,
                       price: Optional[float] = None,
                       additional_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log trading-related events.
        
        Args:
            event_type: Type of trading event (e.g., 'buy', 'sell', 'order_placed')
            symbol: Trading symbol/token
            amount: Trade amount
            price: Trade price
            additional_context: Additional context to log
        """
        context = {
            "trade_event": event_type,
            "symbol": symbol,
            "amount": amount,
            "price": price
        }
        
        if additional_context:
            context.update(additional_context)
        
        if self.enable_structured_logging:
            self.logger.info(f"Trade event: {event_type} {symbol}", extra=context)
        else:
            details = []
            if amount:
                details.append(f"amount: {amount}")
            if price:
                details.append(f"price: {price}")
            detail_str = f" ({', '.join(details)})" if details else ""
            self.logger.info(f"Trade event: {event_type} {symbol}{detail_str}")
    
    def log_health_event(self, component: str, status: str, message: str,
                        additional_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log health check events.
        
        Args:
            component: Name of the component being checked
            status: Health status (e.g., 'healthy', 'unhealthy', 'degraded')
            message: Health check message
            additional_context: Additional context to log
        """
        context = {
            "health_component": component,
            "health_status": status,
            "health_message": message
        }
        
        if additional_context:
            context.update(additional_context)
        
        level = logging.INFO if status in ['healthy', 'ok'] else logging.WARNING
        
        if self.enable_structured_logging:
            self.logger.log(level, f"Health check: {component}", extra=context)
        else:
            self.logger.log(level, f"Health check: {component} - {status} - {message}")
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Log an error with additional context information.
        
        Args:
            error: The exception that occurred
            context: Additional context information
        """
        if self.enable_structured_logging:
            self.logger.error(
                f"Error: {type(error).__name__}: {str(error)}", 
                extra=context,
                exc_info=True
            )
        else:
            self.logger.error(
                f"Error: {type(error).__name__}: {str(error)} - Context: {context}",
                exc_info=True
            )
    
    def create_context_logger(self, context: Dict[str, Any]) -> 'ContextLogger':
        """
        Create a context-aware logger with additional context.
        
        Args:
            context: Context information to include in all log messages
            
        Returns:
            ContextLogger instance with the additional context
        """
        return ContextLogger(self.logger, context)


class ContextLogger:
    """
    Context-aware logger that automatically includes context in all log messages.
    
    This class provides a convenient way to log messages with additional
    context that should be included in all log entries from this logger.
    """
    
    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        """
        Initialize the context logger.
        
        Args:
            logger: Base logger to use
            context: Context information to include in all messages
        """
        self.logger = logger
        self.context = context
    
    def _log_with_context(self, level: int, message: str, **kwargs) -> None:
        """
        Log a message with the context included.
        
        Args:
            level: Logging level
            message: Log message
            **kwargs: Additional arguments for the logger
        """
        if 'extra' in kwargs and kwargs['extra']:
            # Merge context with existing extra data
            kwargs['extra'].update(self.context)
        else:
            kwargs['extra'] = self.context.copy()
        
        self.logger.log(level, message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log a debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log an info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log a warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log an error message with context."""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log a critical message with context."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def add_context(self, additional_context: Dict[str, Any]) -> 'ContextLogger':
        """
        Create a new ContextLogger with additional context.
        
        Args:
            additional_context: Additional context to merge
            
        Returns:
            New ContextLogger with merged context
        """
        merged_context = self.context.copy()
        merged_context.update(additional_context)
        return ContextLogger(self.logger, merged_context)

