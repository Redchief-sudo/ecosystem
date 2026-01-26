# Exit Module
# Exit strategy evaluation and position exit decisions

from .exit import ExitManager, create_exit_manager, ExitFeatures
from .policy import ExitPolicy, ExitPolicyType, get_default_policy
from .verdict import ExitVerdict, ExitAssessment, ExitSignal, hold, partial_exit, full_exit, emergency_exit

__all__ = [
    # Manager
    'ExitManager',
    'create_exit_manager',
    'ExitFeatures',
    
    # Policy
    'ExitPolicy',
    'ExitPolicyType',
    'get_default_policy',
    
    # Verdict
    'ExitVerdict',
    'ExitAssessment',
    'ExitSignal',
    'hold',
    'partial_exit',
    'full_exit',
    'emergency_exit'
]
