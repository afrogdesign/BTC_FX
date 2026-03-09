"""
regime.py – 市場レジーム判定
"""
import pandas as pd
from typing import Tuple
from src.indicators.ema import get_ema50_slope_pct_per_bar


def detect_regime(
    close: pd.Series,
    ema20: pd.Series,
    ema50: pd.Series,
    ema200: pd.Series,
    rsi: pd.Series,
    atr: pd.Series,
    swing_highs_4h: list,
    swing_lows_4h: list,
) -> Tuple[str, str]:
    """
    market_regime と transition_direction を返す。

    Returns
    -------
    (regime, transition_direction)
    regime: uptrend / downtrend / range / volatile / transition
    transition_direction: up / down / ""
    """
    if len(ema20) < 5 or len(atr) < 20:
        return "range", ""

    curr_close = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]

    # ATR 比（直近 20 本平均との比較）
    avg_atr = atr.iloc[-21:-1].mean() if len(atr) > 21 else atr.mean()
    curr_atr = atr.iloc[-1]
    atr_ratio = curr_atr / avg_atr if avg_atr > 0 else 1.0

    # ── Volatile 判定 ─────────────────────────────────────────────────────────
    if atr_ratio > 2.0:
        return "volatile", ""

    # ── Uptrend / Downtrend ───────────────────────────────────────────────────
    bullish_ema = curr_ema20 > curr_ema50 > curr_ema200
    bearish_ema = curr_ema20 < curr_ema50 < curr_ema200

    if bullish_ema and curr_close > curr_ema200:
        return "uptrend", ""
    if bearish_ema and curr_close < curr_ema200:
        return "downtrend", ""

    # ── Range 判定 ─────────────────────────────────────────────────────────────
    # EMA20 と EMA50 が近接しており、EMA50 傾きが平坦
    ema_diff_ratio = abs(curr_ema20 - curr_ema50) / (curr_atr if curr_atr > 0 else 1)
    ema50_slope = get_ema50_slope_pct_per_bar(ema50)
    if ema_diff_ratio < 1.0 and abs(ema50_slope) < 0.0005:
        return "range", ""

    # ── Transition ────────────────────────────────────────────────────────────
    direction = _calc_transition_direction(
        ema20, ema50, ema200, rsi, atr, swing_highs_4h, swing_lows_4h
    )
    return "transition", direction


def _calc_transition_direction(
    ema20: pd.Series,
    ema50: pd.Series,
    ema200: pd.Series,
    rsi: pd.Series,
    atr: pd.Series,
    swing_highs: list,
    swing_lows: list,
) -> str:
    """transition の方向（up / down / ""）を判定する。"""
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]
    ema50_slope = get_ema50_slope_pct_per_bar(ema50)
    ema20_slope = get_ema50_slope_pct_per_bar(ema20)

    # 上向き条件
    up_score = 0
    ema_gap = abs(curr_ema20 - curr_ema50)
    if ema_gap < curr_atr * 0.5 and ema20_slope > 0:
        up_score += 1
    if ema50_slope > -0.0005:  # -0.05%/本 を上回る
        up_score += 1
    if curr_rsi >= 50:
        up_score += 1
    if _swing_rising(swing_highs, swing_lows):
        up_score += 1

    if up_score >= 3:
        return "up"

    # 下向き条件
    down_score = 0
    if ema_gap < curr_atr * 0.5 and ema20_slope < 0:
        down_score += 1
    if ema50_slope < 0.0005:  # +0.05%/本 以下
        down_score += 1
    if curr_rsi < 50:
        down_score += 1
    if _swing_falling(swing_highs, swing_lows):
        down_score += 1

    if down_score >= 3:
        return "down"

    return ""


def _swing_rising(swing_highs: list, swing_lows: list) -> bool:
    """直近 2 スイングで高値または安値が切り上がっているか。"""
    if len(swing_highs) >= 2 and swing_highs[-1][1] > swing_highs[-2][1]:
        return True
    if len(swing_lows) >= 2 and swing_lows[-1][1] > swing_lows[-2][1]:
        return True
    return False


def _swing_falling(swing_highs: list, swing_lows: list) -> bool:
    """直近 2 スイングで高値または安値が切り下がっているか。"""
    if len(swing_highs) >= 2 and swing_highs[-1][1] < swing_highs[-2][1]:
        return True
    if len(swing_lows) >= 2 and swing_lows[-1][1] < swing_lows[-2][1]:
        return True
    return False
