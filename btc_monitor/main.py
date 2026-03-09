"""
main.py – BTC半自動トレード補佐システム エントリーポイント
"""
import sys
import os
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
import schedule
import time
import pytz

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent))

import config
from config import validate_env

from src.data.fetcher import fetch_klines, fetch_funding_rate, get_server_time
from src.data.validator import validate_klines
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
from src.analysis.confidence import (
    calc_tf_signal, calc_confidence, check_critical_zone
)
from src.analysis.phase import classify_phase
from src.analysis.rr import calc_long_setup, calc_short_setup, decide_primary_setup
from src.analysis.qualitative import build_qualitative_context
from src.ai.advice import run_ai_advice, calc_agreement
from src.ai.summary import run_ai_summary, build_subject, build_fallback_body
from src.notification.trigger import should_notify, save_last_result, save_last_notified
from src.notification.email_sender import send_notification, retry_failed_mails
from src.storage.json_store import save_signal, save_notification_log
from src.storage.csv_logger import append_log
from src.storage.cleanup import run_cleanup

# ── ロギング設定 ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/errors/app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def update_heartbeat() -> None:
    """logs/heartbeat.txt に現在時刻 (ISO 8601) を書き込む。"""
    path = Path(config.HEARTBEAT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now(timezone.utc).isoformat())


def run_cycle() -> dict:
    """
    1 サイクルの処理を実行し、判定結果 JSON を返す。
    """
    now_utc = datetime.now(timezone.utc)
    tz = pytz.timezone(config.TIMEZONE)
    now_jst = now_utc.astimezone(tz)

    logger.info("===== サイクル開始: %s =====", now_jst.strftime("%Y-%m-%d %H:%M:%S %Z"))

    # ── サーバー時刻チェック ──────────────────────────────────────────────────
    server_time_ms = get_server_time()
    server_time_gap = 0.0
    if server_time_ms:
        server_time = datetime.fromtimestamp(server_time_ms / 1000, tz=timezone.utc)
        server_time_gap = round((now_utc - server_time).total_seconds(), 1)
        if abs(server_time_gap) > config.SERVER_TIME_TOLERANCE_SEC:
            logger.warning("サーバー時刻誤差: %.1f 秒", server_time_gap)

    # ── Step 1: データ取得 ────────────────────────────────────────────────────
    logger.info("データ取得中...")
    df_4h = fetch_klines("4h", config.FETCH_LIMIT_4H)
    df_1h = fetch_klines("1h", config.FETCH_LIMIT_1H)
    df_15m = fetch_klines("15m", config.FETCH_LIMIT_15M)
    funding_rate = fetch_funding_rate()

    for df, interval in [(df_4h, "4h"), (df_1h, "1h"), (df_15m, "15m")]:
        if not validate_klines(df, interval):
            raise ValueError(f"[{interval}] データ検証失敗。サイクルをスキップします。")

    # ── Step 2: 指標計算 ──────────────────────────────────────────────────────
    logger.info("指標計算中...")
    # 4H
    ema20_4h = calc_ema(df_4h["close"], config.EMA_FAST)
    ema50_4h = calc_ema(df_4h["close"], config.EMA_MID)
    ema200_4h = calc_ema(df_4h["close"], config.EMA_SLOW)
    rsi_4h = calc_rsi(df_4h["close"], config.RSI_LENGTH)
    atr_4h = calc_atr(df_4h["high"], df_4h["low"], df_4h["close"], config.ATR_LENGTH)

    # 1H
    ema20_1h = calc_ema(df_1h["close"], config.EMA_FAST)
    ema50_1h = calc_ema(df_1h["close"], config.EMA_MID)
    ema200_1h = calc_ema(df_1h["close"], config.EMA_SLOW)
    rsi_1h = calc_rsi(df_1h["close"], config.RSI_LENGTH)
    atr_1h = calc_atr(df_1h["high"], df_1h["low"], df_1h["close"], config.ATR_LENGTH)

    # 15m
    ema20_15m = calc_ema(df_15m["close"], config.EMA_FAST)
    ema50_15m = calc_ema(df_15m["close"], config.EMA_MID)
    ema200_15m = calc_ema(df_15m["close"], config.EMA_SLOW)
    rsi_15m = calc_rsi(df_15m["close"], config.RSI_LENGTH)
    atr_15m = calc_atr(df_15m["high"], df_15m["low"], df_15m["close"], config.ATR_LENGTH)

    current_price = round(df_4h["close"].iloc[-1], 2)
    curr_atr_4h = round(atr_4h.iloc[-1], 2)
    curr_rsi_4h = round(rsi_4h.iloc[-1], 2)
    atr_ratio = calc_atr_ratio(atr_4h)
    volume_ratio = calc_volume_ratio(df_15m["volume"])
    ema_alignment = get_ema_alignment(ema20_4h, ema50_4h, ema200_4h)
    ema20_slope = get_ema20_slope(ema20_4h)

    # ── Step 3: 構造判定 ──────────────────────────────────────────────────────
    logger.info("構造判定中...")
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

    # ── Step 4: S/R ゾーン ───────────────────────────────────────────────────
    logger.info("S/R ゾーン抽出中...")
    support_zones, resistance_zones = build_sr_zones(
        df_4h, (sh_4h, sl_4h),
        df_1h, (sh_1h, sl_1h),
        df_15m, (sh_15m, sl_15m),
        atr_4h=curr_atr_4h,
    )

    # ── Step 5: 市場レジーム判定 ──────────────────────────────────────────────
    logger.info("レジーム判定中...")
    market_regime, transition_direction = detect_regime(
        df_4h["close"], ema20_4h, ema50_4h, ema200_4h,
        rsi_4h, atr_4h, sh_4h, sl_4h,
    )

    # ── Step 6: スコア算出 ────────────────────────────────────────────────────
    logger.info("スコア算出中...")
    long_display, short_display, score_gap = calc_scores(
        bias_direction="",
        ema_alignment=ema_alignment,
        ema20_slope=ema20_slope,
        close=df_4h["close"],
        ema20=ema20_4h,
        ema50=ema50_4h,
        ema200=ema200_4h,
        rsi=rsi_4h,
        atr=atr_4h,
        volume_ratio=volume_ratio,
        market_regime=market_regime,
        structure_4h=structure_4h,
        structure_1h=structure_1h,
        swing_high_updated_15m=swing_high_updated,
        swing_low_updated_15m=swing_low_updated,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        funding_rate=funding_rate or 0,
        atr_ratio=atr_ratio,
    )

    # ── Step 7: 時間足シグナル ────────────────────────────────────────────────
    ema_align_1h = get_ema_alignment(ema20_1h, ema50_1h, ema200_1h)
    ema_align_15m = get_ema_alignment(ema20_15m, ema50_15m, ema200_15m)
    sig_4h = calc_tf_signal(ema_alignment, structure_4h)
    sig_1h = calc_tf_signal(ema_align_1h, structure_1h)
    sig_15m = calc_tf_signal(ema_align_15m, structure_15m)

    # ── Step 8: 禁止条件チェック ──────────────────────────────────────────────
    no_trade_flags = []
    if atr_ratio > config.MAX_ACCEPTABLE_ATR_RATIO:
        no_trade_flags.append("ATR_extreme_high")
    if atr_ratio < config.MIN_ACCEPTABLE_ATR_RATIO:
        no_trade_flags.append("ATR_extreme_low")
    if funding_rate is not None:
        if funding_rate >= config.FUNDING_LONG_PROHIBITED:
            no_trade_flags.append("Funding_prohibited_long")
        elif funding_rate >= config.FUNDING_LONG_WARNING:
            no_trade_flags.append("Funding_warning_long")
        if funding_rate <= config.FUNDING_SHORT_PROHIBITED:
            no_trade_flags.append("Funding_prohibited_short")
        elif funding_rate <= config.FUNDING_SHORT_WARNING:
            no_trade_flags.append("Funding_warning_short")
    if is_near_zone(current_price, support_zones + resistance_zones, curr_atr_4h, 0.5):
        no_trade_flags.append("Critical_zone_warning")

    critical_zone = check_critical_zone(current_price, support_zones, resistance_zones, curr_atr_4h)

    # ── Step 9: Bias 決定（暫定） ─────────────────────────────────────────────
    bias = decide_bias(long_display, short_display)

    # ── 暫定 confidence（Phase 確定前の仮計算） ───────────────────────────────
    temp_confidence = calc_confidence(
        bias=bias,
        long_display=long_display,
        short_display=short_display,
        sig_4h=sig_4h, sig_1h=sig_1h, sig_15m=sig_15m,
        market_regime=market_regime,
        phase="range",  # 仮
        rr_estimate=1.5,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        atr=curr_atr_4h,
        current_price=current_price,
        critical_zone=critical_zone,
        funding_rate=funding_rate or 0,
        atr_ratio=atr_ratio,
    )

    # ── Step 10: Phase 確定 ───────────────────────────────────────────────────
    logger.info("Phase 分類中...")
    phase = classify_phase(
        bias=bias,
        market_regime=market_regime,
        close=df_4h["close"],
        ema50=ema50_4h,
        ema200=ema200_4h,
        rsi=rsi_4h,
        atr=atr_4h,
        structure_4h=structure_4h,
        swing_high_updated_15m=swing_high_updated,
        swing_low_updated_15m=swing_low_updated,
        volume_ratio=volume_ratio,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
    )

    # ── Step 11: RR 評価・セットアップ ────────────────────────────────────────
    logger.info("RR 評価中...")
    confidence = calc_confidence(
        bias=bias,
        long_display=long_display,
        short_display=short_display,
        sig_4h=sig_4h, sig_1h=sig_1h, sig_15m=sig_15m,
        market_regime=market_regime,
        phase=phase,
        rr_estimate=1.5,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        atr=curr_atr_4h,
        current_price=current_price,
        critical_zone=critical_zone,
        funding_rate=funding_rate or 0,
        atr_ratio=atr_ratio,
    )

    long_setup = calc_long_setup(
        current_price=current_price,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        atr=curr_atr_4h,
        funding_rate=funding_rate or 0,
        atr_ratio=atr_ratio,
        confidence=confidence,
    )
    short_setup = calc_short_setup(
        current_price=current_price,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        atr=curr_atr_4h,
        funding_rate=funding_rate or 0,
        atr_ratio=atr_ratio,
        confidence=confidence,
    )

    # RR を再取得して confidence を最終計算
    rr_est = long_setup["rr_estimate"] if bias == "long" else short_setup["rr_estimate"]
    confidence = calc_confidence(
        bias=bias,
        long_display=long_display,
        short_display=short_display,
        sig_4h=sig_4h, sig_1h=sig_1h, sig_15m=sig_15m,
        market_regime=market_regime,
        phase=phase,
        rr_estimate=rr_est,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        atr=curr_atr_4h,
        current_price=current_price,
        critical_zone=critical_zone,
        funding_rate=funding_rate or 0,
        atr_ratio=atr_ratio,
    )

    # ── Step 12: primary_setup 決定 ───────────────────────────────────────────
    primary_side, primary_status = decide_primary_setup(bias, long_setup, short_setup)

    # ── Step 13: 定性コンテキスト ──────────────────────────────────────────────
    qualitative = build_qualitative_context(
        current_price=current_price,
        df_15m=df_15m,
        swing_highs_4h=sh_4h,
        swing_lows_4h=sl_4h,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        bias=bias,
        phase=phase,
        market_regime=market_regime,
        rsi=curr_rsi_4h,
        volume_ratio=volume_ratio,
        ema20_slope=ema20_slope,
        structure_4h=structure_4h,
        no_trade_flags=no_trade_flags,
    )

    # ── 機械判定結果組み立て ──────────────────────────────────────────────────
    machine_result = {
        "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_jst": now_jst.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "server_time_gap_sec": server_time_gap,
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
        "critical_zone": critical_zone,
        "support_zones": support_zones,
        "resistance_zones": resistance_zones,
        "long_setup": long_setup,
        "short_setup": short_setup,
        "primary_setup_side": primary_side,
        "primary_setup_status": primary_status,
        "funding_rate": round(funding_rate, 6) if funding_rate is not None else None,
        "atr_ratio": atr_ratio,
        "volume_ratio": volume_ratio,
        "rr_estimate": rr_est,
        "no_trade_flags": no_trade_flags,
        "ema_alignment": ema_alignment,
    }

    # ── Step 14: AI 審査 ──────────────────────────────────────────────────────
    logger.info("AI 審査実行中...")
    ai_advice = run_ai_advice(machine_result, qualitative)
    agreement = calc_agreement(machine_result, (ai_advice or {}).get("decision", "NO_TRADE"))
    machine_result["ai_advice"] = ai_advice
    machine_result["agreement_with_machine"] = agreement

    # ── Step 15: 通知判定 ──────────────────────────────────────────────────────
    logger.info("通知判定中...")
    do_notify, reasons = should_notify(machine_result)
    machine_result["reason_for_notification"] = reasons

    # ── Step 16: 要約・件名生成 ────────────────────────────────────────────────
    if do_notify:
        logger.info("メール本文生成中...")
        body = run_ai_summary(machine_result)
        subject = build_subject(machine_result)
    else:
        body = build_fallback_body(machine_result)
        subject = build_subject(machine_result)

    machine_result["summary_subject"] = subject
    machine_result["summary_body"] = body

    # ── Step 17: ログ保存・通知 ────────────────────────────────────────────────
    save_signal(machine_result)
    save_last_result(machine_result)
    append_log(machine_result, notified=do_notify)

    if do_notify:
        logger.info("メール送信: %s", subject)
        send_notification(subject, body)
        save_last_notified(machine_result)
        save_notification_log(machine_result)

    update_heartbeat()
    logger.info("===== サイクル完了: bias=%s confidence=%d do_notify=%s =====",
                bias, confidence, do_notify)

    return machine_result


def main() -> None:
    """スケジューラーを起動し、REPORT_TIMES に定義された時刻ごとに run_cycle を実行する。"""
    # 環境変数バリデーション
    try:
        validate_env()
    except EnvironmentError as e:
        logger.error("起動前バリデーション失敗: %s", e)
        sys.exit(1)

    # ログディレクトリ作成
    for d in ["logs/signals", "logs/notifications", "logs/csv", "logs/errors"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # クリーンアップ
    run_cleanup()

    logger.info("BTC半自動トレード補佐システム 起動")
    logger.info("スケジュール: %s", config.REPORT_TIMES)
    logger.info("ドライランモード: %s", config.DRYRUN_MODE)

    # スケジュール登録
    def _job():
        retry_failed_mails()
        try:
            run_cycle()
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("run_cycle 例外:\n%s", tb)
            # エラー通知
            try:
                error_body = f"BTC監視システムでエラーが発生しました。\n\n{tb[:1000]}"
                send_notification("[BTC監視] システムエラー", error_body)
            except Exception:
                pass

    for t in config.REPORT_TIMES:
        schedule.every().day.at(t).do(_job)
        logger.info("スケジュール登録: %s", t)

    logger.info("待機中...")
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
