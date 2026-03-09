"""
atr.py – ATR 計算・ATR 比算出
"""
import pandas as pd
import numpy as np


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """True Range の指数移動平均から ATR を計算する。"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    return atr.round(2)


def calc_atr_ratio(atr: pd.Series, lookback: int = 20) -> float:
    """
    現在 ATR / 直近 lookback 本の平均 ATR を返す。
    ボラティリティの相対的な大きさを示す。
    """
    if len(atr) < lookback + 1:
        return 1.0
    current = atr.iloc[-1]
    avg = atr.iloc[-(lookback + 1):-1].mean()
    if avg == 0:
        return 1.0
    return round(current / avg, 2)
