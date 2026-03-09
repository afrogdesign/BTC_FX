"""
scoring.py – long_score / short_score のスコアリング計算
"""
from typing import List, Dict, Tuple
import pandas as pd
import config
from src.analysis.support_resistance import is_near_zone


def _normalize_score(raw: float) -> int:
    """生スコアを 0〜100 に正規化する。(-30〜80 の範囲を想定)"""
    normalized = (raw + 30) / 80 * 100
    return int(round(max(0, min(100, normalized))))


def calc_scores(
    bias_direction: str,  # 暫定。後で使わない
    ema_alignment: str,
    ema20_slope: str,
    close: pd.Series,
    ema20: pd.Series,
    ema50: pd.Series,
    ema200: pd.Series,
    rsi: pd.Series,
    atr: pd.Series,
    volume_ratio: float,
    market_regime: str,
    structure_4h: str,
    structure_1h: str,
    swing_high_updated_15m: bool,
    swing_low_updated_15m: bool,
    support_zones: List[Dict],
    resistance_zones: List[Dict],
    funding_rate: float,
    atr_ratio: float,
) -> Tuple[int, int, int]:
    """
    long_raw, short_raw を計算し、display_score に正規化して返す。

    Returns
    -------
    (long_display_score, short_display_score, score_gap)
    """
    curr = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_atr = atr.iloc[-1]

    long_raw = 0.0
    short_raw = 0.0

    # ── 地合いブロック (0〜30) ──────────────────────────────────────────────────
    # 4H レジーム
    if market_regime == "uptrend":
        long_raw += 15
        short_raw -= 5
    elif market_regime == "downtrend":
        short_raw += 15
        long_raw -= 5
    elif market_regime == "volatile":
        long_raw -= 10
        short_raw -= 10

    # EMA 配列
    if ema_alignment == "bullish":
        long_raw += 10
    elif ema_alignment == "bearish":
        short_raw += 10

    # EMA20 傾き
    if ema20_slope == "up":
        long_raw += 5
    elif ema20_slope == "down":
        short_raw += 5

    # 価格と EMA50 の位置関係
    if curr > curr_ema50:
        long_raw += 5
    elif curr < curr_ema50:
        short_raw += 5

    # ── 構造ブロック (0〜30) ──────────────────────────────────────────────────
    # 4H 構造
    if structure_4h == "hh_hl":
        long_raw += 12
        short_raw -= 5
    elif structure_4h == "lh_ll":
        short_raw += 12
        long_raw -= 5

    # 1H 構造
    if structure_1h == "hh_hl":
        long_raw += 10
    elif structure_1h == "lh_ll":
        short_raw += 10

    # 重要ゾーン反発チェック
    near_support = is_near_zone(curr, support_zones, curr_atr, multiplier=0.5)
    near_resistance = is_near_zone(curr, resistance_zones, curr_atr, multiplier=0.5)

    if near_support:
        long_raw += 8
        short_raw -= 5
    if near_resistance:
        short_raw += 8
        long_raw -= 5

    # ── トリガーブロック (0〜20) ──────────────────────────────────────────────
    # 15m 高値更新
    if swing_high_updated_15m:
        long_raw += 8
    # 15m 安値更新
    if swing_low_updated_15m:
        short_raw += 8

    # Volume Ratio
    if volume_ratio >= 1.5:
        long_raw += 7
        short_raw += 7  # ボリューム増加は両方向で有利

    # RSI 過熱チェック（過熱でないことがトリガー条件）
    if 40 <= curr_rsi <= 65:
        long_raw += 5
    elif curr_rsi > 70:
        short_raw += 5  # RSI 過熱はショートに有利
    elif curr_rsi < 30:
        long_raw += 5   # RSI 売られすぎはロングに有利

    # ── リスクブロック (-30〜0) ───────────────────────────────────────────────
    # レジスタンス直下 / サポート直上
    resistance_atr05 = is_near_zone(curr, resistance_zones, curr_atr, multiplier=0.3)
    support_atr05 = is_near_zone(curr, support_zones, curr_atr, multiplier=0.3)

    if resistance_atr05:
        long_raw -= 10
    if support_atr05:
        short_raw -= 10

    # 200 EMA 攻防中
    if abs(curr - curr_ema200) < curr_atr * 0.5:
        long_raw -= 8
        short_raw -= 8

    # レンジ中央判定
    if market_regime == "range":
        long_raw -= 8
        short_raw -= 8

    # ATR 極端
    if atr_ratio > config.MAX_ACCEPTABLE_ATR_RATIO * 0.8:
        long_raw -= 5
        short_raw -= 5
    elif atr_ratio < config.MIN_ACCEPTABLE_ATR_RATIO * 1.2:
        long_raw -= 5
        short_raw -= 5

    # Funding Rate リスク
    if funding_rate is not None:
        if funding_rate >= config.FUNDING_LONG_WARNING:
            long_raw -= 5
        if funding_rate <= config.FUNDING_SHORT_WARNING:
            short_raw -= 5

    # クリップ
    long_raw = max(-30, min(80, long_raw))
    short_raw = max(-30, min(80, short_raw))

    long_display = _normalize_score(long_raw)
    short_display = _normalize_score(short_raw)
    gap = long_display - short_display

    return long_display, short_display, gap


def decide_bias(long_display: int, short_display: int) -> str:
    """
    score_gap = long_display - short_display を評価して bias を返す。
    gap >= 10 → long, gap <= -12 → short, それ以外 → wait
    """
    gap = long_display - short_display
    if gap >= config.LONG_SHORT_DIFF_THRESHOLD:
        return "long"
    elif gap <= -config.SHORT_LONG_DIFF_THRESHOLD:
        return "short"
    else:
        return "wait"
