"""
fetcher.py – MEXC Contract REST API からデータを取得する
"""
import time
import logging
from typing import Optional
import requests
import pandas as pd
import config

logger = logging.getLogger(__name__)

INTERVAL_MAP = {
    "4h": "Hour4",
    "1h": "Min60",
    "15m": "Min15",
}


def _request_with_retry(url: str, params: dict) -> Optional[dict]:
    """リトライ付き HTTP GET リクエスト。"""
    for attempt in range(1, config.API_RETRY_COUNT + 1):
        try:
            resp = requests.get(url, params=params, timeout=config.API_TIMEOUT_SEC)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") is False:
                logger.warning("API returned success=false: %s", data.get("code"))
                return None
            return data
        except requests.exceptions.Timeout:
            logger.warning("API timeout (attempt %d/%d): %s", attempt, config.API_RETRY_COUNT, url)
        except requests.exceptions.RequestException as e:
            logger.warning("API error (attempt %d/%d): %s", attempt, config.API_RETRY_COUNT, e)
        if attempt < config.API_RETRY_COUNT:
            time.sleep(config.REQUEST_INTERVAL_SEC)
    return None


def get_server_time() -> Optional[int]:
    """取引所サーバー時刻 (Unix ミリ秒) を返す。失敗時は None。"""
    # MEXC Contract API の複数エンドポイントを試みる
    endpoints = [
        f"{config.MEXC_BASE_URL}/api/v1/contract/ping",
        f"{config.MEXC_BASE_URL}/api/v1/contract/detail",
    ]
    for url in endpoints:
        try:
            resp = requests.get(url, timeout=config.API_TIMEOUT_SEC)
            resp.raise_for_status()
            data = resp.json()
            # serverTime フィールドを探す
            if isinstance(data.get("data"), dict) and "serverTime" in data["data"]:
                return int(data["data"]["serverTime"])
            # フォールバック: ローカル時刻をミリ秒で返す
        except Exception:
            continue
    # どのエンドポイントも失敗した場合はローカル時刻を使用
    import time as _time
    return int(_time.time() * 1000)


def fetch_klines(interval: str, limit: int) -> Optional[pd.DataFrame]:
    """
    MEXC Contract API からローソク足データを取得し、未確定足を除外して返す。

    Returns
    -------
    pd.DataFrame or None
        columns: timestamp, open, high, low, close, volume
    """
    mexc_interval = INTERVAL_MAP.get(interval)
    if not mexc_interval:
        raise ValueError(f"未対応の interval: {interval}")

    url = f"{config.MEXC_BASE_URL}/api/v1/contract/kline/{config.MEXC_SYMBOL}"
    params = {"interval": mexc_interval, "limit": limit}

    data = _request_with_retry(url, params)
    if data is None:
        return None

    raw = data.get("data", {})
    if not raw:
        logger.warning("ローソク足データが空 (interval=%s)", interval)
        return None

    # MEXC は {"time":[], "open":[], "high":[], "low":[], "close":[], "vol":[]} 形式
    try:
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(raw["time"], unit="s", utc=True),
            "open":  [float(x) for x in raw["open"]],
            "high":  [float(x) for x in raw["high"]],
            "low":   [float(x) for x in raw["low"]],
            "close": [float(x) for x in raw["close"]],
            "volume":[float(x) for x in raw["vol"]],
        })
    except (KeyError, ValueError) as e:
        logger.error("ローソク足パース失敗: %s", e)
        return None

    df = df.sort_values("timestamp").reset_index(drop=True)

    # 未確定足（最終足）を除外
    if len(df) > 1:
        df = df.iloc[:-1]

    time.sleep(config.REQUEST_INTERVAL_SEC)
    return df


def fetch_funding_rate() -> Optional[float]:
    """現在の Funding Rate を小数で返す。失敗時は None。"""
    url = f"{config.MEXC_BASE_URL}/api/v1/contract/funding_rate/{config.MEXC_SYMBOL}"
    data = _request_with_retry(url, {})
    if data is None:
        return None
    try:
        rate = data["data"]["fundingRate"]
        return float(rate)
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Funding Rate パース失敗: %s", e)
        return None
