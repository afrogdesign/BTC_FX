"""
rr.py – RR 評価・エントリーゾーン計算・setup.status 判定
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import config
from src.analysis.support_resistance import is_near_zone


def calc_long_setup(
    current_price: float,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
    atr: float,
    funding_rate: float,
    atr_ratio: float,
    confidence: int,
) -> Dict:
    """
    ロング側のセットアップを計算して返す。

    Returns
    -------
    dict with keys: status, entry_zone, entry_mid, stop_loss, tp1, tp2,
                    rr_estimate, entry_to_stop_pct, entry_to_target_pct, invalid_reason
    """
    invalid_reasons = []

    # エントリーゾーン: 最も近い（強度の高い）サポートゾーンを使用
    if support_zones:
        best_sup = max(support_zones, key=lambda z: z["strength"])
        entry_zone = {"low": best_sup["low"], "high": best_sup["high"]}
    else:
        # サポートなし: 現在価格の ATR×0.3 を中心に設定
        entry_zone = {
            "low": round(current_price - atr * 0.3, 2),
            "high": round(current_price + atr * 0.1, 2),
        }

    entry_mid = round((entry_zone["low"] + entry_zone["high"]) / 2, 2)
    stop_loss = round(entry_mid - atr * config.SL_ATR_MULTIPLIER, 2)
    stop_dist = abs(entry_mid - stop_loss)

    # TP: entry_mid を起点に RR 基準で設定
    tp1 = round(entry_mid + stop_dist * 1.5, 2)
    tp2 = round(entry_mid + stop_dist * 2.0, 2)

    # 最寄りレジスタンスがある場合は tp1 を調整
    if resistance_zones:
        nearest_res = min(resistance_zones, key=lambda z: abs((z["low"] + z["high"]) / 2 - entry_mid))
        res_mid = (nearest_res["low"] + nearest_res["high"]) / 2
        if res_mid > entry_mid:
            tp1 = round(min(tp1, res_mid * 0.998), 2)

    rr_estimate = round((tp1 - entry_mid) / stop_dist, 2) if stop_dist > 0 else 0.0
    entry_to_stop_pct = round(stop_dist / atr * 100, 2) if atr > 0 else 0.0
    entry_to_target_pct = round(abs(tp1 - entry_mid) / atr * 100, 2) if atr > 0 else 0.0

    # 禁止条件チェック
    if rr_estimate < config.MIN_RR_RATIO:
        invalid_reasons.append("RR不足")
    if atr_ratio > config.MAX_ACCEPTABLE_ATR_RATIO:
        invalid_reasons.append("ATR極端高")
    if atr_ratio < config.MIN_ACCEPTABLE_ATR_RATIO:
        invalid_reasons.append("ATR極端低")
    if funding_rate is not None and funding_rate >= config.FUNDING_LONG_PROHIBITED:
        invalid_reasons.append("FundingRate禁止(Long)")
    if is_near_zone(entry_mid, resistance_zones, atr, 0.5):
        invalid_reasons.append("重要レジスタンス直下")
    if confidence < config.CONFIDENCE_LONG_MIN:
        invalid_reasons.append(f"Confidence不足({confidence}<{config.CONFIDENCE_LONG_MIN})")

    if invalid_reasons:
        status = "invalid"
        return {
            "status": status,
            "entry_zone": {"low": 0.0, "high": 0.0},
            "entry_mid": 0.0,
            "stop_loss": 0.0,
            "tp1": 0.0,
            "tp2": 0.0,
            "rr_estimate": 0.0,
            "entry_to_stop_pct": 0.0,
            "entry_to_target_pct": 0.0,
            "invalid_reason": " / ".join(invalid_reasons),
        }

    # status 判定
    in_entry_zone = entry_zone["low"] <= current_price <= entry_zone["high"]
    near_entry = abs(current_price - entry_mid) <= atr * 0.3

    if in_entry_zone:
        status = "ready"
    elif near_entry:
        status = "watch"
    else:
        status = "watch"

    return {
        "status": status,
        "entry_zone": entry_zone,
        "entry_mid": entry_mid,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "rr_estimate": rr_estimate,
        "entry_to_stop_pct": round(entry_to_stop_pct, 2),
        "entry_to_target_pct": round(entry_to_target_pct, 2),
        "invalid_reason": "",
    }


def calc_short_setup(
    current_price: float,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
    atr: float,
    funding_rate: float,
    atr_ratio: float,
    confidence: int,
) -> Dict:
    """
    ショート側のセットアップを計算して返す。
    """
    invalid_reasons = []

    # エントリーゾーン: 最も近い（強度の高い）レジスタンスゾーンを使用
    if resistance_zones:
        best_res = max(resistance_zones, key=lambda z: z["strength"])
        entry_zone = {"low": best_res["low"], "high": best_res["high"]}
    else:
        entry_zone = {
            "low": round(current_price - atr * 0.1, 2),
            "high": round(current_price + atr * 0.3, 2),
        }

    entry_mid = round((entry_zone["low"] + entry_zone["high"]) / 2, 2)
    stop_loss = round(entry_mid + atr * config.SL_ATR_MULTIPLIER, 2)
    stop_dist = abs(stop_loss - entry_mid)

    tp1 = round(entry_mid - stop_dist * 1.5, 2)
    tp2 = round(entry_mid - stop_dist * 2.0, 2)

    # 最寄りサポートがある場合は tp1 を調整
    if support_zones:
        nearest_sup = min(support_zones, key=lambda z: abs((z["low"] + z["high"]) / 2 - entry_mid))
        sup_mid = (nearest_sup["low"] + nearest_sup["high"]) / 2
        if sup_mid < entry_mid:
            tp1 = round(max(tp1, sup_mid * 1.002), 2)

    rr_estimate = round((entry_mid - tp1) / stop_dist, 2) if stop_dist > 0 else 0.0
    entry_to_stop_pct = round(stop_dist / atr * 100, 2) if atr > 0 else 0.0
    entry_to_target_pct = round(abs(entry_mid - tp1) / atr * 100, 2) if atr > 0 else 0.0

    # 禁止条件チェック
    if rr_estimate < config.MIN_RR_RATIO:
        invalid_reasons.append("RR不足")
    if atr_ratio > config.MAX_ACCEPTABLE_ATR_RATIO:
        invalid_reasons.append("ATR極端高")
    if atr_ratio < config.MIN_ACCEPTABLE_ATR_RATIO:
        invalid_reasons.append("ATR極端低")
    if funding_rate is not None and funding_rate <= config.FUNDING_SHORT_PROHIBITED:
        invalid_reasons.append("FundingRate禁止(Short)")
    if is_near_zone(entry_mid, support_zones, atr, 0.5):
        invalid_reasons.append("重要サポート直上")
    if confidence < config.CONFIDENCE_SHORT_MIN:
        invalid_reasons.append(f"Confidence不足({confidence}<{config.CONFIDENCE_SHORT_MIN})")

    if invalid_reasons:
        return {
            "status": "invalid",
            "entry_zone": {"low": 0.0, "high": 0.0},
            "entry_mid": 0.0,
            "stop_loss": 0.0,
            "tp1": 0.0,
            "tp2": 0.0,
            "rr_estimate": 0.0,
            "entry_to_stop_pct": 0.0,
            "entry_to_target_pct": 0.0,
            "invalid_reason": " / ".join(invalid_reasons),
        }

    in_entry_zone = entry_zone["low"] <= current_price <= entry_zone["high"]
    near_entry = abs(current_price - entry_mid) <= atr * 0.3

    if in_entry_zone:
        status = "ready"
    elif near_entry:
        status = "watch"
    else:
        status = "watch"

    return {
        "status": status,
        "entry_zone": entry_zone,
        "entry_mid": entry_mid,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "rr_estimate": rr_estimate,
        "entry_to_stop_pct": round(entry_to_stop_pct, 2),
        "entry_to_target_pct": round(entry_to_target_pct, 2),
        "invalid_reason": "",
    }


def decide_primary_setup(bias: str, long_setup: Dict, short_setup: Dict) -> Tuple[str, str]:
    """
    primary_setup_side と primary_setup_status を決定する。

    Returns
    -------
    (primary_setup_side, primary_setup_status)
    """
    if bias == "long":
        return "long", long_setup["status"]
    elif bias == "short":
        return "short", short_setup["status"]
    else:
        # bias=wait: より進捗が進んでいる側を採用
        if long_setup["status"] == "ready":
            return "long", "ready"
        elif short_setup["status"] == "ready":
            return "short", "ready"
        elif long_setup["status"] == "watch" and short_setup["status"] != "watch":
            return "long", "watch"
        elif short_setup["status"] == "watch" and long_setup["status"] != "watch":
            return "short", "watch"
        else:
            return "none", "none"
