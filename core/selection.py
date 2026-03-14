"""
Selection methods for AI strategy selection.

This module defines the selection methods used by the AI controller
to choose trading strategies.
"""

from enum import Enum


class SelectionMethod(str, Enum):
    """Strategy selection methods for AI controller."""
    BEST = "best"
    UCB = "ucb"
    THOMPSON = "thompson"
    EPSILON_GREEDY = "epsilon_greedy"
    ENSEMBLE = "ensemble"
    SKIP = "skip"
