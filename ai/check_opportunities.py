from decimal import Decimal
import logging
from trading.models import StrategyDecision, TradeOpportunity, DecisionOutcome, TradeSide
from trading.trade_intent.trade_intent_builder import TradeIntentBuilder

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting check_opportunities...")

    # Create test opportunity
    opportunity = TradeOpportunity(
        token_address="0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC mainnet
        chain="ethereum",
        current_price=1.0,
        dex=None
    )

    # Create test decision
    decision = StrategyDecision(
        opportunity_id="test_opportunity_0001",  # REQUIRED
        decision_id="ai_dec_0001",
        token=opportunity.token_address,
        outcome=DecisionOutcome.APPROVED,
        strategy_name="Elite Basic Strategy",
        strategy_id="elite_basic",
        confidence=0.8,
        position_size=Decimal("1.0"),
        side=TradeSide.BUY
    )

    portfolio_state = {"total_value_usd": 5000.0}

    try:
        intent = TradeIntentBuilder.from_decision(
            decision=decision,
            opportunity=opportunity,
            portfolio_state=portfolio_state
        )
        logger.info(f"✅ TradeIntent created successfully: {intent}")

    except Exception as e:
        logger.error(f"❌ Failed to create TradeIntent: {e}")

