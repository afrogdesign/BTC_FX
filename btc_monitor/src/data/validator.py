"""
validator.py – データの妥当性チェック
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)

MIN_ROWS = {
    "4h": 220,
    "1h": 220,
    "15m": 100,
}


def validate_klines(df: pd.DataFrame, interval: str) -> bool:
    """
    ローソク足配列の長さ、NaN の有無、タイムスタンプ単調増加を確認する。

    Returns
    -------
    bool: 有効なら True
    """
    if df is None or df.empty:
        logger.warning("[%s] データが空です", interval)
        return False

    min_rows = MIN_ROWS.get(interval, 50)
    if len(df) < min_rows:
        logger.warning("[%s] データ本数不足: %d < %d", interval, len(df), min_rows)
        return False

    required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            logger.warning("[%s] 列 '%s' が存在しません", interval, col)
            return False

    for col in ["open", "high", "low", "close", "volume"]:
        if df[col].isna().any():
            logger.warning("[%s] 列 '%s' に NaN が含まれています", interval, col)
            return False

    if not df["timestamp"].is_monotonic_increasing:
        logger.warning("[%s] タイムスタンプが単調増加ではありません", interval)
        return False

    # high >= low チェック
    if (df["high"] < df["low"]).any():
        logger.warning("[%s] high < low の異常データが存在します", interval)
        return False

    return True
