"""
json_store.py – 判定結果 JSON の保存・読み込み
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

SIGNALS_DIR = Path("logs/signals")
NOTIFICATIONS_DIR = Path("logs/notifications")


def save_signal(result: Dict) -> Path:
    """判定結果を logs/signals/YYYYMMDD_HHMMSS.json に保存する。"""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = SIGNALS_DIR / f"{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    logger.info("シグナル保存: %s", path)
    return path


def save_notification_log(result: Dict) -> Path:
    """通知ログを logs/notifications/YYYYMMDD_HHMMSS.json に保存する。"""
    NOTIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = NOTIFICATIONS_DIR / f"{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    logger.info("通知ログ保存: %s", path)
    return path


def load_json(path: Path) -> Optional[Dict]:
    """JSON ファイルを読み込んで返す。"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("JSON 読み込み失敗 (%s): %s", path, e)
        return None
