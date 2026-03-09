"""
rsi.py – RSI 計算
"""
import pandas as pd


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder 法による RSI を計算する。"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(2)
