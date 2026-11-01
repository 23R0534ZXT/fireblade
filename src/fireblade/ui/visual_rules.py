"""Bounded cell-only numeric graphics; never scan or copy the dataset."""
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

VISUAL_ROLE = int(Qt.UserRole) + 91


def visual_value(rule, value):
    try:
        number, low, high = Decimal(str(value)), Decimal(rule.minimum), Decimal(rule.maximum)
        if not all(v.is_finite() for v in (number, low, high)) or low > high:
            return None
        fraction = .5 if low==high else float(max(Decimal(0), min(Decimal(1), (number-low)/(high-low))))
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    start,end=QColor(rule.background),QColor(rule.foreground)
    weight=fraction
    if rule.visual=='scale3':
        middle=Decimal(rule.middle_value)
        if rule.middle_mode=='percent':middle=low+(high-low)*middle/100
        if low==high:start=end=QColor(rule.middle_color);weight=.5
        elif low<middle<high:
            if number<=middle:end=QColor(rule.middle_color);weight=float(max(Decimal(0),min(Decimal(1),(number-low)/(middle-low))))
            else:start=QColor(rule.middle_color);weight=float(max(Decimal(0),min(Decimal(1),(number-middle)/(high-middle))))
        elif middle<=low:start=QColor(rule.middle_color)
        else:end=QColor(rule.middle_color)
    color = QColor(*(round(a+(b-a)*weight) for a,b in zip(start.getRgb(),end.getRgb())))
    if rule.visual=='bar' and number<0:color=QColor(rule.negative_color)
    if rule.visual == 'icon':
        level=icon_level(rule,value,fraction)
        if level<0:return None
        color = QColor(rule.icon_colors[level])
    return rule.visual, fraction, color


def contrast_color(background, base=None):
    """Choose the higher-contrast black/white text using relative luminance."""
    if background.alpha()!=255:
        if base is None:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QPalette
            app=QApplication.instance()
            base=app.palette().color(QPalette.Base) if app else QColor('#ffffff')
        alpha=background.alphaF()
        channels=[(a*alpha+b*(1-alpha))/255 for a,b in zip(background.getRgb()[:3],base.getRgb()[:3])]
    else:channels = [value/255 for value in background.getRgb()[:3]]
    linear = [value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4 for value in channels]
    luminance = sum(weight*value for weight,value in zip((.2126,.7152,.0722),linear))
    black_ratio = (luminance+.05)/.05
    white_ratio = 1.05/(luminance+.05)
    return QColor('#000000' if black_ratio >= white_ratio else '#ffffff')


from functools import lru_cache
from PySide6.QtGui import QImage
from fireblade.core.icon_assets import png_bytes
ICON_ROLE = int(Qt.UserRole)+92

@lru_cache(maxsize=96)
def icon_image(encoded):
    return QImage.fromData(png_bytes(encoded),'PNG')


def icon_level(rule,value,fraction):
    if rule.icon_floor:
        number=Decimal(str(value)) if rule.icon_floor_mode=='number' else Decimal(str(fraction))*100
        floor=Decimal(rule.icon_floor)
        if number<floor or number==floor and rule.icon_floor_comparison=='>':return -1
    if rule.icon_thresholds:
        modes=rule.icon_threshold_modes or [rule.icon_threshold_mode]*len(rule.icon_thresholds)
        # Highest matching icon wins, including when mixed bounds cross after filtering.
        for i in range(len(rule.icon_thresholds)-1,-1,-1):
            number=Decimal(str(value)) if modes[i]=='number' else Decimal(str(fraction))*100
            threshold=Decimal(rule.icon_thresholds[i])
            if number>threshold or number==threshold and (not rule.icon_comparisons or rule.icon_comparisons[i]=='>='):return i+1
        return 0
    return min(len(rule.icon_colors)-1,int(fraction*len(rule.icon_colors)))

BAR_ROLE=int(Qt.UserRole)+93
