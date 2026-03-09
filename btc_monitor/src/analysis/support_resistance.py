"""
support_resistance.py – S/R ゾーンの抽出・統合・反応回数カウント
"""
from typing import List, Dict, Tuple
import pandas as pd


Zone = Dict  # {"low": float, "high": float, "strength": int, "source": str}


def _zones_overlap(z1: Zone, z2: Zone, atr: float) -> bool:
    """2 ゾーンが ATR 比で近接しているかを判定する。"""
    merge_threshold = atr * 0.5
    return not (z1["high"] + merge_threshold < z2["low"] or
                z2["high"] + merge_threshold < z1["low"])


def _merge_zones(zones: List[Zone]) -> Zone:
    """複数ゾーンを 1 つにまとめる。"""
    lo = min(z["low"] for z in zones)
    hi = max(z["high"] for z in zones)
    strength = sum(z["strength"] for z in zones)
    sources = list({z["source"] for z in zones})
    return {"low": round(lo, 2), "high": round(hi, 2),
            "strength": strength, "source": ",".join(sources)}


def _count_reactions(df: pd.DataFrame, zone: Zone) -> int:
    """
    ヒゲまたは実体がゾーン内に入った足数を数える。
    同方向で連続する 3 本以内は 1 反応にまとめる。
    """
    lo, hi = zone["low"], zone["high"]
    in_zone = ((df["low"] <= hi) & (df["high"] >= lo))
    count = 0
    consecutive = 0
    prev_in = False
    for val in in_zone:
        if val:
            if prev_in:
                consecutive += 1
                if consecutive > 3:
                    count += 1
                    consecutive = 0
            else:
                count += 1
                consecutive = 1
        else:
            consecutive = 0
        prev_in = val
    return count


def extract_zones_from_swings(
    swing_highs: list,
    swing_lows: list,
    atr: float,
    source: str,
    df: pd.DataFrame,
) -> Tuple[List[Zone], List[Zone]]:
    """
    スイング高値→レジスタンス候補、スイング安値→サポート候補を生成する。

    Returns
    -------
    (support_zones, resistance_zones)
    """
    half_atr = atr * 0.2

    resistance_zones = []
    for _, price in swing_highs:
        z = {"low": round(price - half_atr, 2),
             "high": round(price + half_atr, 2),
             "strength": 1, "source": source}
        z["strength"] = _count_reactions(df, z)
        resistance_zones.append(z)

    support_zones = []
    for _, price in swing_lows:
        z = {"low": round(price - half_atr, 2),
             "high": round(price + half_atr, 2),
             "strength": 1, "source": source}
        z["strength"] = _count_reactions(df, z)
        support_zones.append(z)

    return support_zones, resistance_zones


def merge_zone_list(zones: List[Zone], atr: float) -> List[Zone]:
    """
    近接ゾーンを ATR 比を用いて統合し、強度降順で返す。
    """
    if not zones:
        return []

    # 価格でソート
    zones = sorted(zones, key=lambda z: z["low"])
    merged = [zones[0]]

    for z in zones[1:]:
        if _zones_overlap(merged[-1], z, atr):
            merged[-1] = _merge_zones([merged[-1], z])
        else:
            merged.append(z)

    # 強度降順
    return sorted(merged, key=lambda z: z["strength"], reverse=True)


def build_sr_zones(
    df_4h: pd.DataFrame, swings_4h: tuple,
    df_1h: pd.DataFrame, swings_1h: tuple,
    df_15m: pd.DataFrame, swings_15m: tuple,
    atr_4h: float,
) -> Tuple[List[Zone], List[Zone]]:
    """
    各時間足のスイングから S/R ゾーンを生成し、統合して最大 3 件ずつ返す。

    Parameters
    ----------
    swings_XX: (swing_highs, swing_lows) のタプル
    atr_4h: 統合の基準となる 4H ATR
    """
    all_support: List[Zone] = []
    all_resistance: List[Zone] = []

    for df, (sh, sl), src in [
        (df_4h, swings_4h, "4h"),
        (df_1h, swings_1h, "1h"),
        (df_15m, swings_15m, "15m"),
    ]:
        sup, res = extract_zones_from_swings(sh, sl, atr_4h, src, df)
        all_support.extend(sup)
        all_resistance.extend(res)

    support_merged = merge_zone_list(all_support, atr_4h)[:3]
    resistance_merged = merge_zone_list(all_resistance, atr_4h)[:3]

    return support_merged, resistance_merged


def is_near_zone(price: float, zones: List[Zone], atr: float, multiplier: float = 0.5) -> bool:
    """価格がゾーンの ATR×multiplier 以内にあるか。"""
    threshold = atr * multiplier
    for z in zones:
        if z["low"] - threshold <= price <= z["high"] + threshold:
            return True
    return False


def distance_to_nearest_zone(price: float, zones: List[Zone], atr: float) -> float:
    """最も近い S/R ゾーンまでの距離を ATR 比で返す。"""
    if not zones:
        return 99.0
    min_dist = float("inf")
    for z in zones:
        mid = (z["low"] + z["high"]) / 2
        dist = abs(price - mid) / atr if atr > 0 else 99.0
        if dist < min_dist:
            min_dist = dist
    return round(min_dist, 2)
