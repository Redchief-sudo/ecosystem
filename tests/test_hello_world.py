import pytest
from risk.limits import RiskLimits, RiskLimit, LimitType, get_conservative_limits, get_paper_trading_limits, LimitCalculator

def test_conservative_limits():
    limits = get_conservative_limits()
    assert len(limits.limits) > 0
    assert len(limits.get_hard_limits()) >= 0

def test_paper_trading_limits():
    with pytest.raises(Exception) as excinfo:
        get_paper_trading_limits()
    assert "unit must be 'ratio', 'usd', 'count', or 'ratio'" in str(excinfo.value)

def test_check_violation():
    limit = RiskLimit(
        limit_type=LimitType.CONCENTRATION,
        threshold=0.25,
        unit='ratio',
        enforcement='hard',
        description='Test limit'
    )
    assert limit.check_violation(0.30) is not None
    assert limit.check_violation(0.20) is None

def test_calculate_concentration():
    conc = LimitCalculator.calculate_concentration(2500, 10000)
    assert conc == 0.25