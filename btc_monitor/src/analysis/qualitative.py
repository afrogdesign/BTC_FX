"""
qualitative.py – 定性コンテキストの算出
"""
from typing import Dict, List
import pandas as pd
from datetime import datetime
import pytz


def get_session(dt_utc: datetime) -> str:
    """UTC 時刻からトレーディングセッションを返す。"""
    hour = dt_utc.hour
    if 22 <= hour or hour < 5:
        return "Tokyo"
    elif 5 <= hour < 8:
        return "London_open"
    elif 8 <= hour < 16:
        return "London"
    elif 13 <= hour < 22:
        return "NY"
    return "overlap"


def calc_pullback_depth(
    current_price: float,
    swing_highs: list,
    swing_lows: list,
    bias: str,
) -> float:
    """
    押し目深度 (0.0〜1.0) を返す。
    ロング: (最高値 - 現在値) / (最高値 - 最安値)
    ショート: (現在値 - 最安値) / (最高値 - 最安値)
    """
    if not swing_highs or not swing_lows:
        return 0.0
    recent_high = max(p for _, p in swing_highs[-3:]) if swing_highs else current_price
    recent_low = min(p for _, p in swing_lows[-3:]) if swing_lows else current_price
    range_size = recent_high - recent_low
    if range_size == 0:
        return 0.0
    if bias == "long":
        return round((recent_high - current_price) / range_size, 2)
    else:
        return round((current_price - recent_low) / range_size, 2)


def calc_wick_rejection(df: pd.DataFrame, n: int = 3) -> float:
    """
    直近 n 本のヒゲ/実体比率の平均を返す（0 = ヒゲなし、1 以上 = 長いヒゲ）。
    """
    if len(df) < n:
        return 0.0
    recent = df.iloc[-n:]
    body = (recent["close"] - recent["open"]).abs()
    total_range = recent["high"] - recent["low"]
    wick = total_range - body
    ratio = (wick / total_range.replace(0, float("nan"))).mean()
    return round(ratio, 2) if not pd.isna(ratio) else 0.0


def calc_body_strength(df: pd.DataFrame, n: int = 3) -> float:
    """直近 n 本の実体/レンジ比率の平均（実体が強いほど 1 に近い）。"""
    if len(df) < n:
        return 0.5
    recent = df.iloc[-n:]
    body = (recent["close"] - recent["open"]).abs()
    total_range = recent["high"] - recent["low"]
    ratio = (body / total_range.replace(0, float("nan"))).mean()
    return round(ratio, 2) if not pd.isna(ratio) else 0.5


def detect_range_state(
    current_price: float,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
) -> str:
    """
    レンジ内の位置を返す: near_support / near_resistance / middle / no_range
    """
    if not support_zones and not resistance_zones:
        return "no_range"

    sup_mid = (support_zones[0]["low"] + support_zones[0]["high"]) / 2 if support_zones else None
    res_mid = (resistance_zones[0]["low"] + resistance_zones[0]["high"]) / 2 if resistance_zones else None

    if sup_mid and res_mid:
        range_size = res_mid - sup_mid
        if range_size <= 0:
            return "no_range"
        position = (current_price - sup_mid) / range_size
        if position <= 0.2:
            return "near_support"
        elif position >= 0.8:
            return "near_resistance"
        else:
            return "middle"
    return "no_range"


def check_late_entry_risk(
    phase: str,
    rsi: float,
    ema20_slope: str,
    structure_4h: str,
) -> bool:
    """
    遅行エントリーリスクがあるか判定する。
    """
    if phase == "reversal_risk":
        return True
    if rsi > 72 and ema20_slope == "up":
        return True
    if rsi < 28 and ema20_slope == "down":
        return True
    return False


def check_trend_exhaustion(
    rsi: float,
    volume_ratio: float,
    market_regime: str,
    structure_4h: str,
) -> bool:
    """トレンド疲労リスクがあるか判定する。"""
    if market_regime not in ("uptrend", "downtrend"):
        return False
    if rsi > 78 and volume_ratio < 0.8:
        return True
    if rsi < 22 and volume_ratio < 0.8:
        return True
    return False


def build_qualitative_context(
    current_price: float,
    df_15m: pd.DataFrame,
    swing_highs_4h: list,
    swing_lows_4h: list,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
    bias: str,
    phase: str,
    market_regime: str,
    rsi: float,
    volume_ratio: float,
    ema20_slope: str,
    structure_4h: str,
    no_trade_flags: List[str],
) -> Dict:
    """定性コンテキストをまとめて返す。"""
    now_utc = datetime.utcnow()

    pullback_depth = calc_pullback_depth(
        current_price, swing_highs_4h, swing_lows_4h, bias
    )
    wick_rejection = calc_wick_rejection(df_15m)
    body_strength = calc_body_strength(df_15m)
    range_state = detect_range_state(current_price, support_zones, resistance_zones)
    late_entry_risk = check_late_entry_risk(phase, rsi, ema20_slope, structure_4h)
    trend_exhaustion_risk = check_trend_exhaustion(rsi, volume_ratio, market_regime, structure_4h)

    # rule_conflicts: 方向に矛盾するシグナルを収集
    rule_conflicts = []
    if bias == "long" and rsi > 70:
        rule_conflicts.append("RSI過熱(Long)")
    if bias == "short" and rsi < 30:
        rule_conflicts.append("RSI売られ過ぎ(Short)")
    if len(no_trade_flags) >= 2:
        rule_conflicts.append("禁止フラグ複数")

    return {
        "session": get_session(now_utc),
        "pullback_depth": pullback_depth,
        "wick_rejection": wick_rejection,
        "body_strength": body_strength,
        "range_state": range_state,
        "late_entry_risk": late_entry_risk,
        "trend_exhaustion_risk": trend_exhaustion_risk,
        "rule_conflicts": rule_conflicts,
    }
