"""
config.py – 設定値の読み込みとバリデーション
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_KEYS = [
    "OPENAI_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "MAIL_FROM",
    "MAIL_TO",
]


def _mask(value: str) -> str:
    """秘密値をマスクして返す。"""
    if not value:
        return "***MASKED***"
    return value[:2] + "***MASKED***"


def validate_env() -> None:
    """必須環境変数の存在と非空文字を検証する。欠損時は EnvironmentError を raise。"""
    missing = []
    for key in REQUIRED_KEYS:
        val = os.getenv(key, "")
        if not val or val.strip() == "":
            missing.append(key)
    if missing:
        raise EnvironmentError(
            f"必須環境変数が未設定です: {missing}. "
            "秘密値はログに出力されません (***MASKED***)。"
        )


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes")


def _get_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _get_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _get_list(key: str, default: str) -> list:
    return [x.strip() for x in os.getenv(key, default).split(",") if x.strip()]


# ── MEXC ──────────────────────────────────────────────────────────────────────
MEXC_BASE_URL: str = os.getenv("MEXC_BASE_URL", "https://contract.mexc.com")
MEXC_SYMBOL: str = os.getenv("MEXC_SYMBOL", "BTC_USDT")

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_SUMMARY_MODEL: str = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
OPENAI_ADVICE_MODEL: str = os.getenv("OPENAI_ADVICE_MODEL", "gpt-4o")

# ── メール ───────────────────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = _get_int("SMTP_PORT", 587)
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM: str = os.getenv("MAIL_FROM", "")
MAIL_TO: str = os.getenv("MAIL_TO", "")

# ── タイムゾーン ──────────────────────────────────────────────────────────────
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tokyo")

# ── スケジュール ──────────────────────────────────────────────────────────────
REPORT_TIMES: list = _get_list("REPORT_TIMES", "09:05,13:05,17:05,21:05,01:05,05:05")

# ── 指標パラメータ ────────────────────────────────────────────────────────────
EMA_FAST: int = _get_int("EMA_FAST", 20)
EMA_MID: int = _get_int("EMA_MID", 50)
EMA_SLOW: int = _get_int("EMA_SLOW", 200)
RSI_LENGTH: int = _get_int("RSI_LENGTH", 14)
ATR_LENGTH: int = _get_int("ATR_LENGTH", 14)

# ── データ取得本数 ─────────────────────────────────────────────────────────────
FETCH_LIMIT_4H: int = _get_int("FETCH_LIMIT_4H", 300)
FETCH_LIMIT_1H: int = _get_int("FETCH_LIMIT_1H", 500)
FETCH_LIMIT_15M: int = _get_int("FETCH_LIMIT_15M", 500)

# ── スコアリング閾値 ───────────────────────────────────────────────────────────
LONG_SHORT_DIFF_THRESHOLD: int = _get_int("LONG_SHORT_DIFF_THRESHOLD", 10)
SHORT_LONG_DIFF_THRESHOLD: int = _get_int("SHORT_LONG_DIFF_THRESHOLD", 12)

# ── Confidence 閾値 ────────────────────────────────────────────────────────────
CONFIDENCE_LONG_MIN: int = _get_int("CONFIDENCE_LONG_MIN", 65)
CONFIDENCE_SHORT_MIN: int = _get_int("CONFIDENCE_SHORT_MIN", 70)
CONFIDENCE_ALERT_CHANGE: int = _get_int("CONFIDENCE_ALERT_CHANGE", 10)

# ── ATR フィルター ─────────────────────────────────────────────────────────────
MAX_ACCEPTABLE_ATR_RATIO: float = _get_float("MAX_ACCEPTABLE_ATR_RATIO", 2.0)
MIN_ACCEPTABLE_ATR_RATIO: float = _get_float("MIN_ACCEPTABLE_ATR_RATIO", 0.3)
MIN_RR_RATIO: float = _get_float("MIN_RR_RATIO", 1.3)
SL_ATR_MULTIPLIER: float = _get_float("SL_ATR_MULTIPLIER", 1.5)

# ── Funding Rate 閾値 ──────────────────────────────────────────────────────────
FUNDING_SHORT_WARNING: float = _get_float("FUNDING_SHORT_WARNING", -0.03)
FUNDING_SHORT_PROHIBITED: float = _get_float("FUNDING_SHORT_PROHIBITED", -0.05)
FUNDING_LONG_WARNING: float = _get_float("FUNDING_LONG_WARNING", 0.05)
FUNDING_LONG_PROHIBITED: float = _get_float("FUNDING_LONG_PROHIBITED", 0.08)

# ── スイング検出パラメータ ────────────────────────────────────────────────────
SWING_N_4H: int = _get_int("SWING_N_4H", 3)
SWING_N_1H: int = _get_int("SWING_N_1H", 2)
SWING_N_15M: int = _get_int("SWING_N_15M", 2)

# ── API レート制限 ─────────────────────────────────────────────────────────────
REQUEST_INTERVAL_SEC: float = _get_float("REQUEST_INTERVAL_SEC", 0.3)
API_TIMEOUT_SEC: int = _get_int("API_TIMEOUT_SEC", 5)
API_RETRY_COUNT: int = _get_int("API_RETRY_COUNT", 3)

# ── AI API ────────────────────────────────────────────────────────────────────
AI_TIMEOUT_SEC: int = _get_int("AI_TIMEOUT_SEC", 5)
AI_RETRY_COUNT: int = _get_int("AI_RETRY_COUNT", 3)
AI_CACHE_ENABLED: bool = _get_bool("AI_CACHE_ENABLED", False)

# ── ヘルスチェック ─────────────────────────────────────────────────────────────
HEARTBEAT_FILE: str = os.getenv("HEARTBEAT_FILE", "logs/heartbeat.txt")
HEALTH_CHECK_MAX_HOURS: int = _get_int("HEALTH_CHECK_MAX_HOURS", 6)

# ── ログ保持期間 ──────────────────────────────────────────────────────────────
LOG_RETENTION_SIGNALS_DAYS: int = _get_int("LOG_RETENTION_SIGNALS_DAYS", 90)
LOG_RETENTION_NOTIFICATIONS_DAYS: int = _get_int("LOG_RETENTION_NOTIFICATIONS_DAYS", 180)
LOG_RETENTION_ERRORS_DAYS: int = _get_int("LOG_RETENTION_ERRORS_DAYS", 180)

# ── 通知クールダウン ──────────────────────────────────────────────────────────
ALERT_COOLDOWN_MINUTES: int = _get_int("ALERT_COOLDOWN_MINUTES", 60)

# ── ドライランモード ──────────────────────────────────────────────────────────
DRYRUN_MODE: bool = _get_bool("DRYRUN_MODE", False)

# ── サーバー時刻許容誤差 ──────────────────────────────────────────────────────
SERVER_TIME_TOLERANCE_SEC: int = _get_int("SERVER_TIME_TOLERANCE_SEC", 2)
