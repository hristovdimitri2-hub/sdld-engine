"""Помощна функция за ДДС (суми с включен данък)."""
from __future__ import annotations


def withVAT(amount: float, rate: float) -> float:
    """Връща стойността с ДДС, закръглена до 2 знака.

    withVAT(100, 0.21) -> 121.0
    """
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise TypeError("amount трябва да е число")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise TypeError("rate трябва да е число")
    if rate < 0:
        raise ValueError("rate не може да е отрицателен")
    return round(float(amount) * (1.0 + float(rate)), 2)
