"""
runner.py – バックテスト実行
AI 審査なしで機械判定アルゴリズムの妥当性を検証する。
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import config

from src.indicators.ema import calc_ema, get_ema_alignment, get_ema20_slope
from src.indicators.rsi import calc_rsi
from src.indicators.atr import calc_atr, calc_atr_ratio
from src.indicators.volume import calc_volume_ratio
from src.analysis.structure import (
    detect_swing_highs, detect_swing_lows, classify_structure,
    is_swing_high_updated, is_swing_low_updated,
)
from src.analysis.support_resistance import build_sr_zones, is_near_zone
from src.analysis.regime import detect_regime
from src.analysis.scoring import calc_scores, decide_bias
from src.analysis.confidence import calc_tf_signal, calc_confidence, check_critical_zone
from src.analysis.phase import classify_phase
from src.analysis.rr import calc_long_setup, calc_short_setup, decide_primary_setup

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HISTORICAL_DIR = Path("data/historical")
BACKTEST_RESULTS_DIR = Path("data/historical/backtest_results")


def load_historical_csv(filepath: Path) -> pd.DataFrame:
    """
    ヒストリカルデータ CSV を読み込む。
    必須列: timestamp, open, high, low, close, volume
    """
    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def run_single_step(
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
    df_15m: pd.DataFrame,
    funding_rate: float = 0.0,
) -> Optional[Dict]:
    """
    与えられたローソク足データに対して 1 ステップの機械判定を実行し、
    結果 dict を返す。AI 審査は実行しない。
    """
    try:
        # 指標計算
        ema20_4h = calc_ema(df_4h["close"], config.EMA_FAST)
        ema50_4h = calc_ema(df_4h["close"], config.EMA_MID)
        ema200_4h = calc_ema(df_4h["close"], config.EMA_SLOW)
        rsi_4h = calc_rsi(df_4h["close"], config.RSI_LENGTH)
        atr_4h = calc_atr(df_4h["high"], df_4h["low"], df_4h["close"], config.ATR_LENGTH)

        ema20_1h = calc_ema(df_1h["close"], config.EMA_FAST)
        ema50_1h = calc_ema(df_1h["close"], config.EMA_MID)
        ema200_1h = calc_ema(df_1h["close"], config.EMA_SLOW)
        rsi_1h = calc_rsi(df_1h["close"], config.RSI_LENGTH)

        ema20_15m = calc_ema(df_15m["close"], config.EMA_FAST)
        ema50_15m = calc_ema(df_15m["close"], config.EMA_MID)
        ema200_15m = calc_ema(df_15m["close"], config.EMA_SLOW)
        rsi_15m = calc_rsi(df_15m["close"], config.RSI_LENGTH)

        current_price = round(df_4h["close"].iloc[-1], 2)
        curr_atr = round(atr_4h.iloc[-1], 2)
        atr_ratio = calc_atr_ratio(atr_4h)
        volume_ratio = calc_volume_ratio(df_15m["volume"])
        ema_alignment = get_ema_alignment(ema20_4h, ema50_4h, ema200_4h)
        ema20_slope = get_ema20_slope(ema20_4h)

        # 構造判定
        sh_4h = detect_swing_highs(df_4h["high"], config.SWING_N_4H)
        sl_4h = detect_swing_lows(df_4h["low"], config.SWING_N_4H)
        sh_1h = detect_swing_highs(df_1h["high"], config.SWING_N_1H)
        sl_1h = detect_swing_lows(df_1h["low"], config.SWING_N_1H)
        sh_15m = detect_swing_highs(df_15m["high"], config.SWING_N_15M)
        sl_15m = detect_swing_lows(df_15m["low"], config.SWING_N_15M)

        structure_4h = classify_structure(sh_4h, sl_4h)
        structure_1h = classify_structure(sh_1h, sl_1h)
        structure_15m = classify_structure(sh_15m, sl_15m)
        swing_high_updated = is_swing_high_updated(sh_15m)
        swing_low_updated = is_swing_low_updated(sl_15m)

        # S/R ゾーン
        support_zones, resistance_zones = build_sr_zones(
            df_4h, (sh_4h, sl_4h),
            df_1h, (sh_1h, sl_1h),
            df_15m, (sh_15m, sl_15m),
            atr_4h=curr_atr,
        )

        # レジーム
        market_regime, transition_direction = detect_regime(
            df_4h["close"], ema20_4h, ema50_4h, ema200_4h,
            rsi_4h, atr_4h, sh_4h, sl_4h,
        )

        # スコア
        long_display, short_display, score_gap = calc_scores(
            bias_direction="",
            ema_alignment=ema_alignment,
            ema20_slope=ema20_slope,
            close=df_4h["close"],
            ema20=ema20_4h, ema50=ema50_4h, ema200=ema200_4h,
            rsi=rsi_4h, atr=atr_4h,
            volume_ratio=volume_ratio,
            market_regime=market_regime,
            structure_4h=structure_4h, structure_1h=structure_1h,
            swing_high_updated_15m=swing_high_updated,
            swing_low_updated_15m=swing_low_updated,
            support_zones=support_zones,
            resistance_zones=resistance_zones,
            funding_rate=funding_rate,
            atr_ratio=atr_ratio,
        )

        # シグナル
        ema_align_1h = get_ema_alignment(ema20_1h, ema50_1h, ema200_1h)
        ema_align_15m = get_ema_alignment(ema20_15m, ema50_15m, ema200_15m)
        sig_4h = calc_tf_signal(ema_alignment, structure_4h)
        sig_1h = calc_tf_signal(ema_align_1h, structure_1h)
        sig_15m = calc_tf_signal(ema_align_15m, structure_15m)

        # 禁止フラグ
        no_trade_flags = []
        if atr_ratio > config.MAX_ACCEPTABLE_ATR_RATIO:
            no_trade_flags.append("ATR_extreme_high")
        if atr_ratio < config.MIN_ACCEPTABLE_ATR_RATIO:
            no_trade_flags.append("ATR_extreme_low")
        if funding_rate >= config.FUNDING_LONG_PROHIBITED:
            no_trade_flags.append("Funding_prohibited_long")
        if funding_rate <= config.FUNDING_SHORT_PROHIBITED:
            no_trade_flags.append("Funding_prohibited_short")

        critical_zone = check_critical_zone(current_price, support_zones, resistance_zones, curr_atr)
        bias = decide_bias(long_display, short_display)

        # Phase
        phase = classify_phase(
            bias=bias, market_regime=market_regime,
            close=df_4h["close"], ema50=ema50_4h, ema200=ema200_4h,
            rsi=rsi_4h, atr=atr_4h, structure_4h=structure_4h,
            swing_high_updated_15m=swing_high_updated,
            swing_low_updated_15m=swing_low_updated,
            volume_ratio=volume_ratio,
            support_zones=support_zones, resistance_zones=resistance_zones,
        )

        # Confidence
        confidence = calc_confidence(
            bias=bias, long_display=long_display, short_display=short_display,
            sig_4h=sig_4h, sig_1h=sig_1h, sig_15m=sig_15m,
            market_regime=market_regime, phase=phase, rr_estimate=1.5,
            support_zones=support_zones, resistance_zones=resistance_zones,
            atr=curr_atr, current_price=current_price, critical_zone=critical_zone,
            funding_rate=funding_rate, atr_ratio=atr_ratio,
        )

        # セットアップ
        long_setup = calc_long_setup(
            current_price=current_price, support_zones=support_zones,
            resistance_zones=resistance_zones, atr=curr_atr,
            funding_rate=funding_rate, atr_ratio=atr_ratio, confidence=confidence,
        )
        short_setup = calc_short_setup(
            current_price=current_price, support_zones=support_zones,
            resistance_zones=resistance_zones, atr=curr_atr,
            funding_rate=funding_rate, atr_ratio=atr_ratio, confidence=confidence,
        )

        rr_est = long_setup["rr_estimate"] if bias == "long" else short_setup["rr_estimate"]
        primary_side, primary_status = decide_primary_setup(bias, long_setup, short_setup)

        ts = df_4h["timestamp"].iloc[-1]

        return {
            "timestamp": str(ts),
            "current_price": current_price,
            "bias": bias,
            "phase": phase,
            "market_regime": market_regime,
            "transition_direction": transition_direction,
            "signals_4h": sig_4h,
            "signals_1h": sig_1h,
            "signals_15m": sig_15m,
            "long_display_score": long_display,
            "short_display_score": short_display,
            "score_gap": score_gap,
            "confidence": confidence,
            "atr_ratio": atr_ratio,
            "volume_ratio": volume_ratio,
            "critical_zone": critical_zone,
            "no_trade_flags": no_trade_flags,
            "long_setup": long_setup,
            "short_setup": short_setup,
            "primary_setup_side": primary_side,
            "primary_setup_status": primary_status,
            "rr_estimate": rr_est,
            "ai_advice": None,
        }
    except Exception as e:
        logger.warning("ステップ処理エラー: %s", e)
        return None


def run_backtest(
    csv_4h: Path,
    csv_1h: Path,
    csv_15m: Path,
    window_4h: int = 300,
    window_1h: int = 500,
    window_15m: int = 500,
    step: int = 4,  # 4H 足換算でのステップ数
) -> List[Dict]:
    """
    ヒストリカルデータを読み込み、ウォークフォワードでアルゴリズムを適用する。

    Parameters
    ----------
    step: 何 4H 足ごとに判定を実行するか（デフォルト=4: 16 時間ごと）
    """
    logger.info("バックテスト開始")
    df4 = load_historical_csv(csv_4h)
    df1 = load_historical_csv(csv_1h)
    df15 = load_historical_csv(csv_15m)

    results = []
    n = len(df4)
    logger.info("4H データ: %d 本", n)

    for end_idx in range(window_4h, n, step):
        sub_4h = df4.iloc[end_idx - window_4h: end_idx].reset_index(drop=True)

        # 対応する 1H・15m データを抽出（タイムスタンプ基準）
        ts_start = sub_4h["timestamp"].iloc[0]
        ts_end = sub_4h["timestamp"].iloc[-1]

        sub_1h = df1[
            (df1["timestamp"] >= ts_start) & (df1["timestamp"] <= ts_end)
        ].tail(window_1h).reset_index(drop=True)

        sub_15m = df15[
            (df15["timestamp"] >= ts_start) & (df15["timestamp"] <= ts_end)
        ].tail(window_15m).reset_index(drop=True)

        if len(sub_1h) < 50 or len(sub_15m) < 50:
            continue

        result = run_single_step(sub_4h, sub_1h, sub_15m)
        if result:
            results.append(result)

    logger.info("バックテスト完了: %d ステップ処理", len(results))

    # 結果保存
    BACKTEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = BACKTEST_RESULTS_DIR / f"backtest_{ts_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    logger.info("結果保存: %s", out_path)

    return results


if __name__ == "__main__":
    # 使用例:
    # python backtest/runner.py
    # data/historical/ 配下に btc_4h.csv, btc_1h.csv, btc_15m.csv を配置して実行
    csv_4h = HISTORICAL_DIR / "btc_4h.csv"
    csv_1h = HISTORICAL_DIR / "btc_1h.csv"
    csv_15m = HISTORICAL_DIR / "btc_15m.csv"

    if not csv_4h.exists():
        print(f"[ERROR] {csv_4h} が存在しません。ヒストリカルデータを配置してください。")
        sys.exit(1)

    results = run_backtest(csv_4h, csv_1h, csv_15m)
    print(f"\nバックテスト完了: {len(results)} ステップ")
