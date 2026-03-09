"""
summary.py – メール本文の生成（OpenAI 要約モデル使用）
"""
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict
import openai
import config

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "summary_prompt.md"

BIAS_LABEL = {"long": "ロング", "short": "ショート", "wait": "待機"}
STATUS_LABEL = {"ready": "エントリー準備完了", "watch": "監視中", "invalid": "無効", "none": "なし"}


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "あなたはBTCトレード要約アシスタントです。"


def build_fallback_body(result: Dict) -> str:
    """AI 要約失敗時のテンプレート本文を生成する。"""
    bias = result.get("bias", "wait")
    phase = result.get("phase", "-")
    confidence = result.get("confidence", 0)
    long_score = result.get("long_display_score", 0)
    short_score = result.get("short_display_score", 0)
    regime = result.get("market_regime", "-")
    transition_dir = result.get("transition_direction", "")
    funding = result.get("funding_rate")
    atr_ratio = result.get("atr_ratio", 1.0)
    vol_ratio = result.get("volume_ratio", 1.0)
    critical = result.get("critical_zone", False)
    flags = result.get("no_trade_flags", [])
    ai_advice = result.get("ai_advice")
    long_s = result.get("long_setup", {})
    short_s = result.get("short_setup", {})
    primary_side = result.get("primary_setup_side", "none")
    primary_status = result.get("primary_setup_status", "none")

    lines = []
    lines.append("=" * 50)
    lines.append(f"【BTC半自動トレード補佐システム 判定レポート】")
    lines.append("=" * 50)
    lines.append("")

    # ── 結論 ──
    lines.append("■ 結論と信頼度")
    lines.append(f"  バイアス  : {BIAS_LABEL.get(bias, bias)}")
    lines.append(f"  フェーズ  : {phase}")
    lines.append(f"  Confidence: {confidence}")
    if ai_advice:
        lines.append(f"  AI審査    : {ai_advice.get('decision')} (品質:{ai_advice.get('quality')}, 信頼:{ai_advice.get('confidence')})")
        lines.append(f"  AIコメント: {ai_advice.get('notes')}")
    else:
        lines.append("  AI審査    : 取得失敗（機械判定のみ）")
    lines.append("")

    # ── 機械判定サマリー ──
    lines.append("■ 機械判定サマリー")
    lines.append(f"  Longスコア / Shortスコア : {long_score} / {short_score} (差:{result.get('score_gap',0)})")
    lines.append(f"  4H / 1H / 15m シグナル   : {result.get('signals_4h','?')} / {result.get('signals_1h','?')} / {result.get('signals_15m','?')}")
    reg_str = regime
    if transition_dir:
        reg_str += f" (方向:{transition_dir})"
    lines.append(f"  市場レジーム              : {reg_str}")
    lines.append("")

    # ── 指標 ──
    lines.append("■ 指標・環境")
    lines.append(f"  Funding Rate : {f'{funding:.4f}' if funding is not None else 'N/A'}")
    lines.append(f"  ATR比        : {atr_ratio}")
    lines.append(f"  Volume Ratio : {vol_ratio}")

    sup_zones = result.get("support_zones", [])
    res_zones = result.get("resistance_zones", [])
    if sup_zones:
        z = sup_zones[0]
        lines.append(f"  主要サポート : {z['low']} - {z['high']} (強度:{z['strength']})")
    if res_zones:
        z = res_zones[0]
        lines.append(f"  主要レジスタンス: {z['low']} - {z['high']} (強度:{z['strength']})")
    lines.append("")

    # ── セットアップ ──
    lines.append("■ セットアップ")
    for side, setup in [("ロング", long_s), ("ショート", short_s)]:
        st = setup.get("status", "-")
        lines.append(f"  [{side}] ステータス: {STATUS_LABEL.get(st, st)}")
        if st != "invalid":
            lines.append(f"    エントリーゾーン: {setup.get('entry_zone', {}).get('low')} - {setup.get('entry_zone', {}).get('high')}")
            lines.append(f"    SL: {setup.get('stop_loss')}  TP1: {setup.get('tp1')}  TP2: {setup.get('tp2')}  RR: {setup.get('rr_estimate')}")
        else:
            lines.append(f"    無効理由: {setup.get('invalid_reason', '-')}")
    lines.append("")

    # ── リスク ──
    if critical:
        lines.append("⚠️  CRITICAL ZONE: 重要サポレジと現在価格が接触中")
    if flags:
        lines.append("■ リスクフラグ: " + ", ".join(flags))

    lines.append("")
    lines.append("-" * 50)
    return "\n".join(lines)


def build_subject(result: Dict) -> str:
    """メール件名を生成する。"""
    bias = result.get("bias", "wait")
    confidence = result.get("confidence", 0)
    ai_advice = result.get("ai_advice")
    primary_status = result.get("primary_setup_status", "none")
    agreement = result.get("agreement_with_machine", "")

    # 時刻
    from datetime import datetime
    import pytz
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M")

    subject = f"[BTC監視] {time_str} {bias} / Confidence {confidence}"

    if primary_status == "ready":
        subject += " 🟢READY"
    elif primary_status == "watch":
        subject += " 🟡WATCH"

    if ai_advice is None:
        subject += " ⚠️ AI審査:機械判定のみ"
    elif agreement == "disagree":
        decision = ai_advice.get("decision", "")
        subject += f" ⚠️ AI審査:{decision}"

    return subject


def run_ai_summary(result: Dict) -> str:
    """
    AI 要約モデルでメール本文を生成する。
    失敗時はテンプレート本文を返す。
    """
    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    system_prompt = _load_prompt()
    user_message = json.dumps(result, ensure_ascii=False, default=str)

    for attempt in range(1, config.AI_RETRY_COUNT + 1):
        try:
            response = client.chat.completions.create(
                model=config.OPENAI_SUMMARY_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                timeout=config.AI_TIMEOUT_SEC,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Summary 生成エラー (attempt %d/%d): %s", attempt, config.AI_RETRY_COUNT, e)
            if attempt < config.AI_RETRY_COUNT:
                time.sleep(1)

    return build_fallback_body(result)
