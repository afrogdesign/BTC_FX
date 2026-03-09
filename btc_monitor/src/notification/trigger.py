"""
trigger.py – 通知トリガー判定
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import config

logger = logging.getLogger(__name__)

LAST_RESULT_PATH = Path("logs/last_result.json")
LAST_NOTIFIED_PATH = Path("logs/last_notified.json")


def _load_json(path: Path) -> Optional[Dict]:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("JSON 読み込み失敗 (%s): %s", path, e)
    return None


def should_notify(current: Dict) -> Tuple[bool, List[str]]:
    """
    通知を送るべきか判定する。

    Returns
    -------
    (bool, reasons)
    """
    last_result = _load_json(LAST_RESULT_PATH)
    last_notified = _load_json(LAST_NOTIFIED_PATH)

    bias = current.get("bias", "wait")
    confidence = current.get("confidence", 0)
    primary_status = current.get("primary_setup_status", "none")
    agreement = current.get("agreement_with_machine", "partial")

    # 通知最低基準チェック
    if bias == "long" and confidence < config.CONFIDENCE_LONG_MIN:
        logger.info("Confidence 不足 (long): %d < %d", confidence, config.CONFIDENCE_LONG_MIN)
        return False, []
    if bias == "short" and confidence < config.CONFIDENCE_SHORT_MIN:
        logger.info("Confidence 不足 (short): %d < %d", confidence, config.CONFIDENCE_SHORT_MIN)
        return False, []

    # ── 抑制条件チェック ────────────────────────────────────────────────────
    # 1. bias=wait かつ変化なし
    if bias == "wait" and last_notified and last_notified.get("bias") == "wait":
        logger.info("bias=wait かつ前回も wait: 通知スキップ")
        return False, []

    # 2. invalid かつ禁止フラグ 2 つ以上
    flags = current.get("no_trade_flags", [])
    if primary_status == "invalid" and len(flags) >= 2:
        if last_notified and last_notified.get("primary_setup_status") == "invalid":
            logger.info("invalid フラグ 2 以上で変化なし: 通知スキップ")
            return False, []

    # 3. クールダウン: 同一種別の通知を ALERT_COOLDOWN_MINUTES 以内に送信済み
    if last_notified:
        last_time_str = last_notified.get("timestamp_utc", "")
        if last_time_str:
            try:
                last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
                if elapsed < config.ALERT_COOLDOWN_MINUTES:
                    logger.info("クールダウン中 (%.1f分 < %d分): 通知スキップ", elapsed, config.ALERT_COOLDOWN_MINUTES)
                    return False, []
            except Exception:
                pass

    # ── トリガー条件チェック ─────────────────────────────────────────────────
    reasons = []

    prev_status = (last_notified or {}).get("primary_setup_status", "none")
    prev_bias = (last_notified or {}).get("bias", "wait")
    prev_confidence = (last_notified or {}).get("confidence", 0)
    prev_agreement = (last_notified or {}).get("agreement_with_machine", "partial")

    # 1. invalid→watch / invalid→ready
    if prev_status == "invalid" and primary_status in ("watch", "ready"):
        reasons.append("status_upgraded")

    # 2. watch→ready
    if prev_status == "watch" and primary_status == "ready":
        reasons.append("status_ready")

    # 3. bias 変化
    if prev_bias == "wait" and bias in ("long", "short"):
        reasons.append("bias_changed")

    # 4. confidence 変化
    if abs(confidence - prev_confidence) >= config.CONFIDENCE_ALERT_CHANGE:
        reasons.append("confidence_jump")

    # 5. agreement 変化
    if prev_agreement == "agree" and agreement == "disagree":
        reasons.append("ai_disagree")
    elif prev_agreement == "disagree" and agreement == "agree":
        reasons.append("ai_agree")

    if not reasons:
        logger.info("通知トリガー条件なし: スキップ")
        return False, []

    return True, reasons


def save_last_result(result: Dict) -> None:
    """最新実行結果を保存する。"""
    LAST_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)


def save_last_notified(result: Dict) -> None:
    """直前通知結果を保存する。"""
    LAST_NOTIFIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_NOTIFIED_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
