"""
Financial Precision Module - INSTITUTIONAL GRADE
================================================
Provides Decimal-based calculations for zero-precision-loss financial operations.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP, getcontext
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)

# Set precision for financial calculations (28 decimal places)
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

class FinancialDecimal:
    """Wrapper for Decimal with financial-specific operations."""
    
    PRICE_PRECISION = Decimal('0.00000001')  # 8 decimals for crypto
    AMOUNT_PRECISION = Decimal('0.01')  # 2 decimals for USD
    PERCENTAGE_PRECISION = Decimal('0.0001')  # 4 decimals
    
    def __init__(self, value: Union[str, float, Decimal, int], precision: Optional[Decimal] = None):
        if isinstance(value, Decimal):
            self.value = value
        elif isinstance(value, str):
            self.value = Decimal(value)
        elif isinstance(value, (int, float)):
            self.value = Decimal(str(value))  # Convert via string to avoid precision loss
        else:
            raise TypeError(f"Unsupported type: {type(value)}")
        self.precision = precision or self.PRICE_PRECISION
    
    def quantize(self, precision: Optional[Decimal] = None, rounding: str = 'HALF_UP') -> Decimal:
        """Quantize to specified precision."""
        prec = precision or self.precision
        rounding_mode = {'DOWN': ROUND_DOWN, 'UP': ROUND_UP, 'HALF_UP': ROUND_HALF_UP}.get(rounding.upper(), ROUND_HALF_UP)
        return self.value.quantize(prec, rounding=rounding_mode)
    
    def to_float(self) -> float:
        """Convert to float (use with caution)."""
        return float(self.value)
    
    def __add__(self, other):
        if isinstance(other, FinancialDecimal):
            return FinancialDecimal(self.value + other.value, self.precision)
        return FinancialDecimal(self.value + Decimal(str(other)), self.precision)
    
    def __sub__(self, other):
        if isinstance(other, FinancialDecimal):
            return FinancialDecimal(self.value - other.value, self.precision)
        return FinancialDecimal(self.value - Decimal(str(other)), self.precision)
    
    def __mul__(self, other):
        if isinstance(other, FinancialDecimal):
            return FinancialDecimal(self.value * other.value, self.precision)
        return FinancialDecimal(self.value * Decimal(str(other)), self.precision)
    
    def __truediv__(self, other):
        if isinstance(other, FinancialDecimal):
            if other.value == 0:
                raise ZeroDivisionError("Division by zero")
            return FinancialDecimal(self.value / other.value, self.precision)
        divisor = Decimal(str(other))
        if divisor == 0:
            raise ZeroDivisionError("Division by zero")
        return FinancialDecimal(self.value / divisor, self.precision)
    
    def __lt__(self, other): 
        return self.value < (other.value if isinstance(other, FinancialDecimal) else Decimal(str(other)))
    
    def __le__(self, other): 
        return self.value <= (other.value if isinstance(other, FinancialDecimal) else Decimal(str(other)))
    
    def __gt__(self, other): 
        return self.value > (other.value if isinstance(other, FinancialDecimal) else Decimal(str(other)))
    
    def __ge__(self, other): 
        return self.value >= (other.value if isinstance(other, FinancialDecimal) else Decimal(str(other)))
    
    def __eq__(self, other): 
        return self.value == (other.value if isinstance(other, FinancialDecimal) else Decimal(str(other)))
    
    def __str__(self): 
        return str(self.value)
    
    def __repr__(self): 
        return f"FinancialDecimal({self.value})"


def safe_float_to_decimal(value: float) -> Decimal:
    """Safely convert float to Decimal without precision loss."""
    return Decimal(str(value))


def decimal_to_float(value: Decimal, precision: int = 8) -> float:
    """Convert Decimal to float with specified precision."""
    return float(value.quantize(Decimal('0.1') ** precision))
