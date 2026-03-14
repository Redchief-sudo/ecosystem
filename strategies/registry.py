from __future__ import annotations
from typing import Dict, Type, List
from .base_strategy import BaseStrategy


class StrategyRegistry:
    def __init__(self):
        self._registry: Dict[str, Type[BaseStrategy]] = {}

    def register(self, strategy_cls: Type[BaseStrategy]):
        key = strategy_cls.STRATEGY_NAME
        if key in self._registry:
            raise ValueError(f"Strategy key collision: {key} already registered")
        self._registry[key] = strategy_cls

    def get(self, key: str):
        return self._registry.get(key)

    def keys(self) -> List[str]:
        return list(self._registry.keys())

    def all(self) -> Dict[str, Type[BaseStrategy]]:
        return dict(self._registry)
