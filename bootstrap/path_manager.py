"""
Path management utilities for the trading ecosystem.
"""

import os
from typing import Optional


class PathManager:
    """Manages file paths and directories for the application."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or os.getcwd()

    def get_path(self, *path_components: str) -> str:
        """Get a path relative to the base path."""
        return os.path.join(self.base_path, *path_components)

    def ensure_directory(self, path: str) -> None:
        """Ensure a directory exists."""
        os.makedirs(path, exist_ok=True)


def get_path_manager(base_path: Optional[str] = None) -> PathManager:
    """Get a PathManager instance."""
    return PathManager(base_path)
