import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Track if logging has been configured
_LOGGING_CONFIGURED = False

# Color codes for terminal output
COLORS = {
    'DEBUG': '\033[94m',    # Blue
    'INFO': '\033[92m',     # Green
    'WARNING': '\033[93m',  # Yellow
    'ERROR': '\033[91m',    # Red
    'CRITICAL': '\033[91m', # Red (bold)
    'RESET': '\033[0m',     # Reset to default
}

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""
    
    def format(self, record):
        # Save original format
        original_fmt = self._style._fmt
        
        # Add color to the level name if it exists in COLORS
        if record.levelname in COLORS:
            record.levelname = f"{COLORS[record.levelname]}{record.levelname}{COLORS['RESET']}"
        
        # Format the message with the original formatter
        result = super().format(record)
        
        # Restore original format
        self._style._fmt = original_fmt
        
        return result

def _configure_root_logger(log_level: int = logging.INFO, 
                         log_file: Optional[Union[str, Path]] = None,
                         clear_handlers: bool = True) -> None:
    """Internal function to configure the root logger."""
    global _LOGGING_CONFIGURED
    
    if _LOGGING_CONFIGURED and not clear_handlers:
        return
    
    root_logger = logging.getLogger()
    
    if clear_handlers:
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
    
    # Set log level
    root_logger.setLevel(log_level)
    
    # Skip if we've already configured and not clearing handlers
    if _LOGGING_CONFIGURED and not clear_handlers:
        return
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler if log_file is provided
    if log_file:
        try:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_format = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            root_logger.addHandler(file_handler)
            root_logger.info(f"Logging to file: {log_file.absolute()}")
        except Exception as e:
            root_logger.error(f"Failed to set up file logging: {e}")

    # Configure third-party loggers
    for logger_name in ['web3', 'urllib3', 'asyncio', 'aiohttp', 'websockets']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    _LOGGING_CONFIGURED = True

def setup_logging(
    log_level: Union[int, str] = logging.INFO,
    log_file: Optional[Union[str, Path]] = None,
    clear_handlers: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure logging for the application with enhanced debugging.
    
    Args:
        log_level: Logging level (e.g., logging.DEBUG, 'INFO')
        log_file: Path to log file. If None, file logging will be disabled
        clear_handlers: Whether to clear existing handlers
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
    """
    global _LOGGING_CONFIGURED
    
    if _LOGGING_CONFIGURED and not clear_handlers:
        return
    
    # Convert string log level to int if needed
    if isinstance(log_level, str):
        log_level = getattr(logging, log_level.upper(), logging.DEBUG)
    
    # CRITICAL FIX: Actually configure the handlers!
    _configure_root_logger(log_level=log_level, log_file=log_file, clear_handlers=clear_handlers)
    
    # Get root logger and mark as configured
    root_logger = logging.getLogger()
    root_logger._ecosystem_logging_configured = True
    
    # Log configuration
    logger = logging.getLogger(__name__)
    logger.info("Logging configured")
    logger.debug(f"Log level set to: {logging.getLevelName(log_level)}")
    if log_file:
        logger.debug(f"Logging to file: {log_file}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    This ensures the root logger is configured before returning a logger.
    
    Args:
        name: Name of the logger (usually __name__)
        
    Returns:
        Configured logger instance
    """
    if not _LOGGING_CONFIGURED:
        setup_logging()
    return logging.getLogger(name)

# Configure default logging when module is imported
if not _LOGGING_CONFIGURED:
    setup_logging()

# Set up global exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions in the application."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Call the default excepthook for keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Log the exception
    logger = get_logger('unhandled')
    logger.critical("Uncaught exception", 
                   exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception
