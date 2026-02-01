# trade_strategies/professional_elite_strategy.py
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Set, Any

import numpy as np
from ..base_strategy import BaseStrategy
from ..data_classes import SignalType, DecisionAction, RiskProfile, StrategyDecision, Rationale, TradeSignal
from core.numeric_constants import get_numeric_constants

logger = logging.getLogger("strategies.professional_elite")

class ProfessionalEliteStrategy(BaseStrategy):
    IS_STRATEGY = True
    STRATEGY_NAME = "safe"

    def __init__(self, strategy_config, global_config):
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.trade_history: List[Dict] = []
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}
        self.portfolio_var = 0
        self.max_drawdown = 0
        self.peak_portfolio_value = 0
        self.current_positions: Dict[str, float] = {}
        self.returns_history: deque = deque(maxlen=100)
        self.sharpe_ratio = 0
        super().__init__(strategy_config, global_config)

    def strategy_id(self) -> str:
        return "professional_elite_v1"

    def version(self) -> str:
        return "1.0.0"

    def description(self) -> str:
        return "Professional-grade institutional strategy with Kelly Criterion, Sharpe optimization, and advanced risk management"

    def supported_markets(self) -> List[str]:
        return ["ethereum", "base", "solana", "polygon", "arbitrum", "optimism"]

    def timeframes(self) -> List[str]:
        return ["1h", "4h", "24h", "7d"]

    def required_features(self) -> Set[str]:
        return {"price", "volume_24h", "liquidity_usd", "price_change_24h", "market_cap", "rsi", "volatility"}

    def warmup_period(self) -> int:
        return 20

    def evaluate(self, market_state: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[StrategyDecision]:
        try:
            c = self.strategy_config
            if not c:
                return None

            token_id = market_state.get("id") or market_state.get("symbol")
            if not token_id:
                return None

            price = self._safe(market_state, "price")
            vol_24h = self._safe(market_state, "volume_24h")
            liq = self._safe(market_state, "liquidity_usd")
            price_change_24h = self._safe(market_state, "price_change_24h", 0)
            if not all([price, vol_24h, liq]):
                return None

            self._update_history(token_id, price, vol_24h)

            min_vol = c.get("min_volume_24h", 100000)
            min_liq = c.get("min_liquidity", 250000)
            if vol_24h < min_vol or liq < min_liq:
                return None

            regime = self._detect_market_regime(token_id, price_change_24h)
            if regime == "HIGH_VOLATILITY" and not c.get("trade_in_volatility", False):
                return None

            flow_score = self._analyze_order_flow(market_state)
            if flow_score < c.get("min_flow_score", 0.4):
                return None

            edge = self._calculate_statistical_edge(token_id, price)
            if edge < c.get("min_edge", 0.02):
                return None

            if self._check_drawdown_limit(c):
                return None

            correlation_risk = self._assess_correlation_risk(token_id)
            if correlation_risk > c.get("max_correlation", 0.7):
                return None

            if self._is_portfolio_over_concentrated(c):
                return None

            alpha_score = self._calculate_alpha_score(market_state, token_id, regime, flow_score, edge)
            if alpha_score < c.get("min_alpha_score", 0.65):
                return None

            win_rate, avg_win, avg_loss = self._realized_trade_stats()
            kelly_fraction = self._calculate_kelly_criterion(win_rate, avg_win, avg_loss)
            kelly_multiplier = c.get("kelly_fraction", 0.25)
            kelly_size = kelly_fraction * kelly_multiplier

            volatility = self._calculate_realized_volatility(token_id)
            target_vol = c.get("target_volatility", 0.10)
            vol_adjustment = target_vol / max(volatility, 0.01)

            base_size = c.get("base_position_size", 0.001)
            position_size = base_size * kelly_size * vol_adjustment * alpha_score
            max_size = c.get("max_position_size", 0.002)
            min_size = c.get("min_position_size", 0.0001)
            position_size = np.clip(position_size, min_size, max_size)

            sharpe_target = c.get("target_sharpe", 2.0)
            confidence = self._calculate_sharpe_adjusted_confidence(alpha_score, volatility, sharpe_target)

            atr = self._calculate_atr(token_id)
            atr_multiplier = c.get("stop_atr_multiplier", 2.0)
            stop_loss = price - (atr * atr_multiplier)

            risk_reward_ratio = c.get("risk_reward_ratio", 2.5)
            take_profit = price + ((price - stop_loss) * risk_reward_ratio)
            if regime == "LOW_VOLATILITY":
                take_profit *= 0.85
            elif regime == "HIGH_VOLATILITY":
                take_profit *= 1.15
                stop_loss = price - (atr * atr_multiplier * 1.3)

            expected_impact = self._estimate_price_impact(position_size, vol_24h, liq)
            max_impact = c.get("max_price_impact", 0.005)
            if expected_impact > max_impact:
                return None

            slippage = self._estimate_slippage(vol_24h, liq, regime)

            decision = StrategyDecision(
                strategy_id=self.strategy_id(),
                action=DecisionAction.BUY,
                confidence=confidence,
                rationale=Rationale(
                    primary_reason=f"Strong institutional-grade opportunity with {alpha_score:.1%} alpha score",
                    indicators_used=["rsi", "price_change_24h", "volume_24h", "liquidity_usd", "market_cap"],
                    factors={
                        "alpha_score": alpha_score,
                        "statistical_edge": edge,
                        "kelly_fraction": kelly_size,
                        "sharpe_ratio": self.sharpe_ratio,
                        "flow_score": flow_score,
                        "volatility": volatility,
                        "expected_slippage": slippage,
                        "price_impact": expected_impact,
                    },
                    market_conditions=regime,
                    regime_confidence=0.8,
                    additional_notes=f"Risk-reward: {risk_reward_ratio:.1f}, Win rate: {win_rate:.1%}, ATR: {atr:.4f}"
                ),
                metadata={
                    "regime": regime,
                    "alpha_score": alpha_score,
                    "statistical_edge": edge,
                    "kelly_fraction": kelly_size,
                    "volatility": volatility,
                    "sharpe_ratio": self.sharpe_ratio,
                    "flow_score": flow_score,
                    "expected_slippage": slippage,
                    "price_impact": expected_impact,
                    "risk_reward": risk_reward_ratio,
                    "win_rate": win_rate,
                    "atr": atr,
                    "token_id": token_id,
                    "price": price,
                    "volume_24h": vol_24h,
                    "liquidity": liq,
                },
                version=self.version(),
            )
            return decision
        except Exception as e:
            logger.error(f"[ProfElite] Error: {e}", exc_info=True)
            return None

    def signal_type(self) -> SignalType:
        return SignalType.DIRECTIONAL

    def risk_profile(self) -> RiskProfile:
        return RiskProfile(
            max_drawdown=0.10,
            max_concurrent_positions=5,
            volatility_tolerance=1.0,
            min_confidence_threshold=0.35,
            max_position_size=0.02,
            max_loss_per_trade=0.01,
            risk_per_trade=0.005,
        )

    def _safe(self, data, key, default=None):
        if not isinstance(data, dict):
            return default
        return data.get(key, default)

    def _create_signal(self, signal_type, confidence, price, size, stop_loss, take_profit, metadata=None):
        return TradeSignal(
            strategy_id=self.STRATEGY_NAME,
            signal_type=signal_type,
            confidence=float(confidence),
            score=float(confidence),
            metadata=metadata or {}
        )

    def _update_history(self, token_id, price, volume):
        now = datetime.now()
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=100)
            self.volume_history[token_id] = deque(maxlen=100)
        self.price_history[token_id].append((now, price))
        self.volume_history[token_id].append((now, volume))

    def _detect_market_regime(self, token_id, price_change_24h):
        if token_id not in self.price_history or len(self.price_history[token_id]) < 10:
            return "UNKNOWN"
        prices = np.array([p for _, p in self.price_history[token_id]])
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]
        trend_strength = abs(slope) / max(np.mean(prices), 1e-8)
        if volatility > self.strategy_config.get("high_vol_threshold", 0.05):
            return "HIGH_VOLATILITY"
        elif volatility < self.strategy_config.get("low_vol_threshold", 0.01):
            return "LOW_VOLATILITY"
        elif trend_strength > self.strategy_config.get("trend_strength_threshold", 0.02):
            return "TRENDING"
        else:
            return "RANGING"

    def _analyze_order_flow(self, o):
        vol_24h = self._safe(o, "volume_24h")
        liq = self._safe(o, "liquidity_usd")
        if not vol_24h or not liq:
            return 0
        vol_liq_ratio = vol_24h / liq
        if 0.5 <= vol_liq_ratio <= 2.0:
            flow_score = 1.0
        elif vol_liq_ratio < 0.5:
            flow_score = vol_liq_ratio / 0.5
        else:
            flow_score = max(0.2, 2.0 / vol_liq_ratio)
        token_id = o.get("id") or o.get("symbol")
        if token_id in self.volume_history and len(self.volume_history[token_id]) > 5:
            volumes = np.array([v for _, v in self.volume_history[token_id]])
            consistency_score = max(0, 1 - np.std(volumes) / np.mean(volumes))
            flow_score = (flow_score + consistency_score) / 2
        return flow_score

    def _calculate_statistical_edge(self, token_id, current_price):
        if token_id not in self.price_history or len(self.price_history[token_id]) < 20:
            return 0
        prices = np.array([p for _, p in self.price_history[token_id]])
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        z_score = (current_price - mean_price) / max(std_price, 1e-8)
        mean_reversion_edge = max(0, -z_score * 0.02)
        short_term_return = (prices[-1] - prices[-5]) / prices[-5]
        medium_term_return = (prices[-1] - prices[-10]) / prices[-10]
        momentum_edge = (short_term_return + medium_term_return) / 2
        total_edge = mean_reversion_edge * 0.6 + momentum_edge * 0.4
        return max(0, total_edge)

    def _check_drawdown_limit(self, c):
        return self.max_drawdown > c.get("max_drawdown_limit", 0.15)

    def _assess_correlation_risk(self, token_id):
        if not self.current_positions or token_id not in self.price_history:
            return 0
        correlations = []
        for pos_token in self.current_positions:
            if pos_token in self.price_history:
                prices1 = np.array([p for _, p in self.price_history[token_id]])
                prices2 = np.array([p for _, p in self.price_history[pos_token]])
                min_len = min(len(prices1), len(prices2))
                if min_len < 2:
                    continue
                corr = np.corrcoef(prices1[-min_len:], prices2[-min_len:])[0, 1]
                correlations.append(corr)
        return max(correlations) if correlations else 0

    def _is_portfolio_over_concentrated(self, c):
        return len(self.current_positions) >= c.get("max_concurrent_positions", 10)

    def _calculate_alpha_score(self, o, token_id, regime, flow_score, edge):
        liq = self._safe(o, "liquidity_usd")
        mcap = self._safe(o, "market_cap")
        scores = []
        scores.append(min(1.0, liq / 500000) * 0.25)
        scores.append(flow_score * 0.20)
        scores.append(min(1.0, edge / 0.05) * 0.30)
        scores.append({"TRENDING": 0.9,"LOW_VOLATILITY":0.8,"RANGING":0.6,"HIGH_VOLATILITY":0.4,"UNKNOWN":0.5}.get(regime,0.5) *0.15)
        if mcap:
            scores.append(min(1.0, mcap / 10000000) * 0.10)
        else:
            scores.append(0.05)
        return sum(scores)

    def _realized_trade_stats(self):
        if not self.trade_history:
            return 0.55, 0.08, 0.04
        wins = [t for t in self.trade_history if t["pnl"] > 0]
        win_rate = len(wins)/len(self.trade_history)
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0.08
        losses = [t for t in self.trade_history if t["pnl"] <= 0]
        avg_loss = abs(np.mean([t["pnl"] for t in losses])) if losses else 0.04
        return win_rate, avg_win, avg_loss

    def _calculate_kelly_criterion(self, win_rate, avg_win, avg_loss):
        if avg_loss == 0:
            return 0
        b = avg_win / avg_loss
        q = 1 - win_rate
        kelly = (win_rate * b - q) / b
        return max(0, min(1, kelly))

    def _calculate_realized_volatility(self, token_id):
        if token_id not in self.price_history or len(self.price_history[token_id]) < 10:
            return 0.05
        prices = np.array([p for _, p in self.price_history[token_id]])
        returns = np.diff(prices) / prices[:-1]
        return np.std(returns) * np.sqrt(365*24)

    def _calculate_atr(self, token_id):
        if token_id not in self.price_history or len(self.price_history[token_id]) < 2:
            return 0
        prices = np.array([p for _, p in self.price_history[token_id]])
        tr = np.abs(np.diff(prices))
        return np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)

    def _calculate_sharpe_adjusted_confidence(self, alpha_score, volatility, target_sharpe):
        expected_return = alpha_score * 0.10
        sharpe = expected_return / max(volatility, 1e-8)
        self.sharpe_ratio = sharpe
        return max(0.1, min(1.0, (sharpe / target_sharpe) * alpha_score))

    def _estimate_price_impact(self, position_size, volume_24h, liquidity_usd):
        if volume_24h == 0:
            return 1.0
        avg_volume_per_period = volume_24h / 24
        position_usd = position_size * 10000
        impact = 0.1 * np.sqrt(position_usd / max(avg_volume_per_period, 1e-8))
        return min(1.0, impact)

    def _estimate_slippage(self, volume_24h, liquidity_usd, regime):
        nc = get_numeric_constants()
        base_slippage = nc.slippage_base_pct
        if liquidity_usd > 500000:
            liq_divisor = nc.slippage_liquidity_high_divisor
        elif liquidity_usd > 250000:
            liq_divisor = nc.slippage_liquidity_medium_divisor
        else:
            liq_divisor = nc.slippage_liquidity_low_divisor
        regime_adj = {
            "LOW_VOLATILITY": nc.slippage_regime_low_vol_pct,
            "RANGING": nc.slippage_regime_ranging_pct,
            "TRENDING": nc.slippage_regime_trending_pct,
            "HIGH_VOLATILITY": nc.slippage_regime_high_vol_pct,
            "UNKNOWN": 1.0
        }.get(regime,1.0)
        return base_slippage * liq_divisor * regime_adj

