from .registry import StrategyRegistry

registry = StrategyRegistry()

# Import all strategies
from .features.momentum import EliteMomentumStrategy
from .features.mean_reversion import MeanReversionStrategyV2 as MeanReversionStrategy
from .features.breakout import EliteBreakoutStrategyV2 as EliteBreakoutStrategy
from .features.volatility_breakout import VolatilityBreakoutStrategy
from .features.aggressive import EliteAggressiveStrategy
from .features.risk_caps import RiskCapsStrategy
from .features.safe import ProfessionalEliteStrategy
from .features.smart_money import SmartMoneyUltraStrategy

# Register all strategies
registry.register(EliteMomentumStrategy)
registry.register(MeanReversionStrategy)
registry.register(EliteBreakoutStrategy)
registry.register(VolatilityBreakoutStrategy)
registry.register(EliteAggressiveStrategy)
registry.register(RiskCapsStrategy)
registry.register(ProfessionalEliteStrategy)
registry.register(SmartMoneyUltraStrategy)

