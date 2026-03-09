"""
csv_logger.py – CSV ログへの追記
"""
import csv
import logging
from pathlib import Path
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)

CSV_PATH = Path("logs/csv/trades.csv")

CSV_HEADERS = [
    "timestamp_utc", "timestamp_jst", "bias", "phase", "market_regime",
    "transition_direction", "signals_4h", "signals_1h", "signals_15m",
    "long_display_score", "short_display_score", "score_gap", "confidence",
    "primary_setup_side", "primary_setup_status",
    "long_status", "long_entry_mid", "long_stop_loss", "long_tp1", "long_rr",
    "short_status", "short_entry_mid", "short_stop_loss", "short_tp1", "short_rr",
    "funding_rate", "atr_ratio", "volume_ratio",
    "critical_zone", "no_trade_flags",
    "ai_decision", "ai_quality", "ai_confidence",
    "agreement_with_machine", "reason_for_notification",
    "notified",
]


def _ensure_header() -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)


def append_log(result: Dict, notified: bool) -> None:
    """判定結果を CSV に 1 行追記する。"""
    _ensure_header()
    ai = result.get("ai_advice") or {}
    long_s = result.get("long_setup", {})
    short_s = result.get("short_setup", {})

    row = [
        result.get("timestamp_utc", ""),
        result.get("timestamp_jst", ""),
        result.get("bias", ""),
        result.get("phase", ""),
        result.get("market_regime", ""),
        result.get("transition_direction", ""),
        result.get("signals_4h", ""),
        result.get("signals_1h", ""),
        result.get("signals_15m", ""),
        result.get("long_display_score", ""),
        result.get("short_display_score", ""),
        result.get("score_gap", ""),
        result.get("confidence", ""),
        result.get("primary_setup_side", ""),
        result.get("primary_setup_status", ""),
        long_s.get("status", ""),
        long_s.get("entry_mid", ""),
        long_s.get("stop_loss", ""),
        long_s.get("tp1", ""),
        long_s.get("rr_estimate", ""),
        short_s.get("status", ""),
        short_s.get("entry_mid", ""),
        short_s.get("stop_loss", ""),
        short_s.get("tp1", ""),
        short_s.get("rr_estimate", ""),
        result.get("funding_rate", ""),
        result.get("atr_ratio", ""),
        result.get("volume_ratio", ""),
        result.get("critical_zone", ""),
        "|".join(result.get("no_trade_flags", [])),
        ai.get("decision", ""),
        ai.get("quality", ""),
        ai.get("confidence", ""),
        result.get("agreement_with_machine", ""),
        "|".join(result.get("reason_for_notification", [])),
        str(notified),
    ]

    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
    except Exception as e:
        logger.error("CSV 書き込みエラー: %s", e)
