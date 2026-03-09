"""
ema.py – EMA 計算・EMA 配列判定
"""
import pandas as pd
import config


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """指数移動平均を計算して返す。"""
    return series.ewm(span=period, adjust=False).mean().round(2)


def get_ema_alignment(ema_fast: pd.Series, ema_mid: pd.Series, ema_slow: pd.Series) -> str:
    """
    EMA の並びから方向性を返す。
    bullish: fast > mid > slow
    bearish: fast < mid < slow
    mixed: それ以外
    """
    f = ema_fast.iloc[-1]
    m = ema_mid.iloc[-1]
    s = ema_slow.iloc[-1]

    if f > m > s:
        return "bullish"
    elif f < m < s:
        return "bearish"
    else:
        return "mixed"


def get_ema20_slope(ema20: pd.Series, n: int = 3) -> str:
    """
    直近 n 本の EMA20 傾きを返す。
    up: 上向き / down: 下向き / flat: 横ばい
    判定基準: (最終値 - n本前の値) / n本前の値 の変化率
    """
    if len(ema20) < n + 1:
        return "flat"
    prev = ema20.iloc[-(n + 1)]
    curr = ema20.iloc[-1]
    if prev == 0:
        return "flat"
    pct_change = (curr - prev) / prev
    if pct_change > 0.0005 * n:
        return "up"
    elif pct_change < -0.0005 * n:
        return "down"
    else:
        return "flat"


def get_ema50_slope_pct_per_bar(ema50: pd.Series, n: int = 3) -> float:
    """EMA50 の直近 n 本平均傾き (%/本) を返す。"""
    if len(ema50) < n + 1:
        return 0.0
    prev = ema50.iloc[-(n + 1)]
    curr = ema50.iloc[-1]
    if prev == 0:
        return 0.0
    return ((curr - prev) / prev) / n
