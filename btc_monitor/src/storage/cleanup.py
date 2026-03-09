"""
cleanup.py – 古いログの削除
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
import config

logger = logging.getLogger(__name__)

LAST_CLEANUP_FILE = Path("logs/.last_cleanup")


def _should_run() -> bool:
    """前回クリーンアップから 24 時間以上経過しているか確認する。"""
    if not LAST_CLEANUP_FILE.exists():
        return True
    try:
        ts_str = LAST_CLEANUP_FILE.read_text().strip()
        last_run = datetime.fromisoformat(ts_str)
        return (datetime.utcnow() - last_run).total_seconds() >= 86400
    except Exception:
        return True


def _cleanup_dir(directory: Path, days: int) -> int:
    """指定ディレクトリから days 日より古い .json / .txt ファイルを削除する。"""
    if not directory.exists():
        return 0
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = 0
    for f in directory.glob("*.json"):
        try:
            mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except Exception as e:
            logger.warning("削除失敗 (%s): %s", f, e)
    return deleted


def run_cleanup() -> None:
    """
    起動時に呼び出す。24 時間未経過の場合はスキップする。
    """
    if not _should_run():
        return

    total = 0
    total += _cleanup_dir(Path("logs/signals"), config.LOG_RETENTION_SIGNALS_DAYS)
    total += _cleanup_dir(Path("logs/notifications"), config.LOG_RETENTION_NOTIFICATIONS_DAYS)
    total += _cleanup_dir(Path("logs/errors"), config.LOG_RETENTION_ERRORS_DAYS)

    logger.info("クリーンアップ完了: %d ファイル削除", total)

    LAST_CLEANUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_CLEANUP_FILE.write_text(datetime.utcnow().isoformat())
