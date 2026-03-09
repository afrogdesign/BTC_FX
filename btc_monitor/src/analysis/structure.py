"""
structure.py – スイング高値安値の検出と HH/HL/LH/LL 判定
"""
from typing import List, Tuple, Optional
import pandas as pd


def detect_swing_highs(high: pd.Series, n: int) -> List[Tuple[int, float]]:
    """
    スイング高値を検出する。
    index i がスイング高値 ⟺ high[i] が前後 n 本の最大値
    Returns: [(index, price), ...]
    """
    swings = []
    for i in range(n, len(high) - n):
        window = high.iloc[i - n: i + n + 1]
        if high.iloc[i] == window.max():
            swings.append((i, round(high.iloc[i], 2)))
    return swings


def detect_swing_lows(low: pd.Series, n: int) -> List[Tuple[int, float]]:
    """
    スイング安値を検出する。
    index i がスイング安値 ⟺ low[i] が前後 n 本の最小値
    Returns: [(index, price), ...]
    """
    swings = []
    for i in range(n, len(low) - n):
        window = low.iloc[i - n: i + n + 1]
        if low.iloc[i] == window.min():
            swings.append((i, round(low.iloc[i], 2)))
    return swings


def classify_structure(swing_highs: List[Tuple[int, float]],
                        swing_lows: List[Tuple[int, float]]) -> str:
    """
    直近 2 スイングの高値・安値の切り上がり/切り下がりで構造を分類する。

    Returns
    -------
    str: hh_hl / lh_ll / mixed / insufficient_data
    """
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "insufficient_data"

    # 直近 2 つ
    prev_high, last_high = swing_highs[-2][1], swing_highs[-1][1]
    prev_low, last_low = swing_lows[-2][1], swing_lows[-1][1]

    hh = last_high > prev_high   # 高値切り上げ
    hl = last_low > prev_low     # 安値切り上げ
    lh = last_high < prev_high   # 高値切り下げ
    ll = last_low < prev_low     # 安値切り下げ

    if hh and hl:
        return "hh_hl"
    elif lh and ll:
        return "lh_ll"
    else:
        return "mixed"


def is_swing_high_updated(swing_highs: List[Tuple[int, float]]) -> bool:
    """直近 15m スイング高値が更新されているか（トリガー判定用）。"""
    if len(swing_highs) < 2:
        return False
    return swing_highs[-1][1] > swing_highs[-2][1]


def is_swing_low_updated(swing_lows: List[Tuple[int, float]]) -> bool:
    """直近 15m スイング安値が更新されているか（ショートトリガー判定用）。"""
    if len(swing_lows) < 2:
        return False
    return swing_lows[-1][1] < swing_lows[-2][1]
