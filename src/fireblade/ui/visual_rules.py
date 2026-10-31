"""Bounded cell-only numeric graphics; never scan or copy the dataset."""
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

VISUAL_ROLE = int(Qt.UserRole) + 91


def visual_value(rule, value):
    try:
        number, low, high = Decimal(str(value)), Decimal(rule.minimum), Decimal(rule.maximum)
        if not all(v.is_finite() for v in (number, low, high)) or low >= high:
            return None
        fraction = float(max(Decimal(0), min(Decimal(1), (number-low)/(high-low))))
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    start, end = QColor(rule.background), QColor(rule.foreground)
    color = QColor(*(round(a+(b-a)*fraction) for a,b in zip(start.getRgb()[:3],end.getRgb()[:3])))
    if rule.visual == 'icon':
        color = QColor(('#c62828', '#c58b00', '#218739')[min(2, int(fraction*3))])
    return rule.visual, fraction, color
