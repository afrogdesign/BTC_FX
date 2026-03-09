"""
confidence.py – Confidence スコア算出
"""
from typing import List, Dict
import config


def calc_tf_signal(ema_alignment: str, structure: str) -> str:
    """
    EMA の並びと価格構造から時間足の方向シグナルを決める。
    bullish + hh_hl → long
    bearish + lh_ll → short
    それ以外 → wait
    """
    if ema_alignment == "bullish" and structure == "hh_hl":
        return "long"
    elif ema_alignment == "bearish" and structure == "lh_ll":
        return "short"
    else:
        return "wait"


def count_agreeing_timeframes(sig_4h: str, sig_1h: str, sig_15m: str, bias: str) -> int:
    """bias と一致する時間足数を返す。"""
    return sum(1 for s in [sig_4h, sig_1h, sig_15m] if s == bias)


def calc_confidence(
    bias: str,
    long_display: int,
    short_display: int,
    sig_4h: str,
    sig_1h: str,
    sig_15m: str,
    market_regime: str,
    phase: str,
    rr_estimate: float,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
    atr: float,
    current_price: float,
    critical_zone: bool,
    funding_rate: float,
    atr_ratio: float,
) -> int:
    """
    0〜100 の Confidence スコアを算出して返す。
    """
    # 1. ベーススコア
    if bias == "long":
        base = long_display
    elif bias == "short":
        base = short_display
    else:
        base = min(50, max(long_display, short_display) * 0.6)

    score = base

    # 2. 時間足整合ボーナス
    agree_count = count_agreeing_timeframes(sig_4h, sig_1h, sig_15m, bias)
    if agree_count == 3:
        score += 15
    elif agree_count == 2:
        score += 8

    # 3. レジームの明確さ
    regime_bonus = {
        "uptrend": 10, "downtrend": 10,
        "transition": 0, "range": -5, "volatile": -10,
    }
    score += regime_bonus.get(market_regime, 0)

    # 4. Phase 補正
    phase_bonus = {
        "trend_following": 5, "pullback": 3,
        "breakout": 0, "range": -5, "reversal_risk": -10,
    }
    score += phase_bonus.get(phase, 0)

    # 5. RR 品質
    if rr_estimate >= 2.0:
        score += 10
    elif rr_estimate >= 1.5:
        score += 5
    elif rr_estimate < config.MIN_RR_RATIO:
        score -= 15

    # 6. 反対ゾーンまでの余白
    if bias == "long":
        opponent_zones = resistance_zones
    else:
        opponent_zones = support_zones

    if opponent_zones:
        nearest_mid = (opponent_zones[0]["low"] + opponent_zones[0]["high"]) / 2
        dist_atr = abs(current_price - nearest_mid) / atr if atr > 0 else 99.0
        if dist_atr >= 1.5:
            score += 5
        elif dist_atr < 0.8:
            score -= 5

    # 7. 危険ペナルティ
    if critical_zone:
        score -= 10

    if funding_rate is not None:
        if bias == "long" and funding_rate >= config.FUNDING_LONG_WARNING:
            score -= 5
        if bias == "short" and funding_rate <= config.FUNDING_SHORT_WARNING:
            score -= 5

    if atr_ratio > config.MAX_ACCEPTABLE_ATR_RATIO * 0.8:
        score -= 5
    if atr_ratio < config.MIN_ACCEPTABLE_ATR_RATIO * 1.2:
        score -= 5

    return int(round(max(0, min(100, score))))


def check_critical_zone(
    current_price: float,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
    atr: float,
) -> bool:
    """重要 S/R と現在価格が ATR×0.5 以内なら True。"""
    threshold = atr * 0.5
    all_zones = support_zones + resistance_zones
    for z in all_zones:
        if z.get("strength", 0) >= 3:
            if z["low"] - threshold <= current_price <= z["high"] + threshold:
                return True
    return False
