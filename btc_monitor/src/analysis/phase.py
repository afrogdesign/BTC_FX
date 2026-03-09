"""
phase.py – Phase 分類（bias 決定後に実行）
"""
import pandas as pd
from typing import List, Dict


def classify_phase(
    bias: str,
    market_regime: str,
    close: pd.Series,
    ema50: pd.Series,
    ema200: pd.Series,
    rsi: pd.Series,
    atr: pd.Series,
    structure_4h: str,
    swing_high_updated_15m: bool,
    swing_low_updated_15m: bool,
    volume_ratio: float,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
) -> str:
    """
    trend_following / pullback / breakout / range / reversal_risk を返す。
    """
    curr = close.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]

    # ── reversal_risk ────────────────────────────────────────────────────────
    reversal_flags = 0
    if curr_rsi > 75 or curr_rsi < 25:
        reversal_flags += 1
    # 長いヒゲ連続（簡易: 直近 3 本のヒゲ/実体比）
    if len(close) >= 3:
        reversal_flags += 0  # wick_ratio は qualitative.py で算出
    if market_regime == "volatile":
        reversal_flags += 1
    if reversal_flags >= 2:
        return "reversal_risk"

    # ── breakout ──────────────────────────────────────────────────────────────
    if bias in ("long", "short") and volume_ratio >= 1.5:
        if bias == "long" and swing_high_updated_15m and market_regime in ("range", "transition"):
            return "breakout"
        if bias == "short" and swing_low_updated_15m and market_regime in ("range", "transition"):
            return "breakout"

    # ── trend_following ───────────────────────────────────────────────────────
    if market_regime in ("uptrend", "downtrend"):
        if structure_4h in ("hh_hl", "lh_ll"):
            # 押し目が浅い（EMA50 付近まで来ていない）
            if bias == "long" and curr > curr_ema50 * 1.005:
                return "trend_following"
            if bias == "short" and curr < curr_ema50 * 0.995:
                return "trend_following"

    # ── pullback ──────────────────────────────────────────────────────────────
    if market_regime in ("uptrend", "downtrend"):
        # 価格が EMA50〜200 の間
        if bias == "long" and curr_ema200 <= curr <= curr_ema50 * 1.02:
            return "pullback"
        if bias == "short" and curr_ema50 * 0.98 <= curr <= curr_ema200:
            return "pullback"

    # ── range ────────────────────────────────────────────────────────────────
    if market_regime == "range" or bias == "wait":
        return "range"

    return "trend_following"
