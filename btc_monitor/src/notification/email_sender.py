"""
email_sender.py – メール送信（smtplib + TLS）
"""
import smtplib
import logging
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import config

logger = logging.getLogger(__name__)

FAILED_MAIL_DIR = Path("logs/errors")
MAX_RESEND_ATTEMPTS = 3


def _send_email(subject: str, body: str) -> bool:
    """SMTP でメールを送信する。成功で True、失敗で False を返す。"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.MAIL_FROM
    msg["To"] = config.MAIL_TO
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.MAIL_FROM, config.MAIL_TO, msg.as_string())
        logger.info("メール送信成功: %s", subject)
        return True
    except Exception as e:
        logger.error("メール送信失敗: %s", e)
        return False


def send_notification(subject: str, body: str) -> None:
    """
    通知メールを送信する。
    DRYRUN_MODE=true の場合は送信せずログ出力のみ行う。
    失敗時はローカルに保存する。
    """
    if config.DRYRUN_MODE:
        logger.info("[DRYRUN] メール送信スキップ: %s", subject)
        return

    if not _send_email(subject, body):
        _save_failed_mail(subject, body)


def _save_failed_mail(subject: str, body: str) -> None:
    """送信失敗したメールをローカルに保存する。"""
    FAILED_MAIL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = FAILED_MAIL_DIR / f"failed_mail_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"subject": subject, "body": body, "attempts": 1}, f,
                  ensure_ascii=False, indent=2)
    logger.info("失敗メールを保存: %s", path)


def retry_failed_mails() -> None:
    """
    前回失敗したメールの再送を試みる（最大 MAX_RESEND_ATTEMPTS 回）。
    """
    FAILED_MAIL_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(FAILED_MAIL_DIR.glob("failed_mail_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            attempts = data.get("attempts", 1)
            if attempts >= MAX_RESEND_ATTEMPTS:
                logger.warning("再送上限到達、削除: %s", path)
                path.unlink()
                continue

            success = _send_email(data["subject"], data["body"])
            if success:
                path.unlink()
                logger.info("再送成功: %s", path)
            else:
                data["attempts"] = attempts + 1
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("再送処理エラー (%s): %s", path, e)
