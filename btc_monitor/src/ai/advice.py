"""
advice.py – OpenAI を使った AI 審査
"""
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict
import openai
import config

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "advice_prompt.md"


def _load_prompt() -> str:
    """プロンプトファイルを読み込む。"""
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "あなたはBTCトレードの局面審査員です。"


def _build_user_message(machine_result: Dict, qualitative: Dict) -> str:
    """AI に渡すユーザーメッセージを構築する。"""
    return json.dumps({
        "machine_result": {
            "bias": machine_result.get("bias"),
            "phase": machine_result.get("phase"),
            "market_regime": machine_result.get("market_regime"),
            "transition_direction": machine_result.get("transition_direction"),
            "signals_4h": machine_result.get("signals_4h"),
            "signals_1h": machine_result.get("signals_1h"),
            "signals_15m": machine_result.get("signals_15m"),
            "long_display_score": machine_result.get("long_display_score"),
            "short_display_score": machine_result.get("short_display_score"),
            "confidence": machine_result.get("confidence"),
            "critical_zone": machine_result.get("critical_zone"),
            "funding_rate": machine_result.get("funding_rate"),
            "atr_ratio": machine_result.get("atr_ratio"),
            "volume_ratio": machine_result.get("volume_ratio"),
            "support_zones": machine_result.get("support_zones"),
            "resistance_zones": machine_result.get("resistance_zones"),
            "long_setup": machine_result.get("long_setup"),
            "short_setup": machine_result.get("short_setup"),
            "no_trade_flags": machine_result.get("no_trade_flags"),
        },
        "qualitative_context": qualitative,
    }, ensure_ascii=False, indent=2)


def calc_agreement(machine_result: Dict, ai_decision: str) -> str:
    """
    AI 審査の agreement_with_machine を 4 条件の一致数で決定する。
    agree: 3〜4 / partial: 2 / disagree: 0〜1
    """
    bias = machine_result.get("bias", "wait")
    regime = machine_result.get("market_regime", "")
    ema_align = machine_result.get("ema_alignment", "mixed")
    funding = machine_result.get("funding_rate", 0) or 0
    volume_ratio = machine_result.get("volume_ratio", 1.0) or 1.0

    agree_count = 0

    # 1. 上位足方向 (4H レジーム) が一致するか
    if (bias == "long" and regime in ("uptrend", "transition")) or \
       (bias == "short" and regime in ("downtrend",)):
        agree_count += 1
    elif bias == "wait":
        agree_count += 0

    # 2. EMA 並びが方向と整合するか
    if (bias == "long" and ema_align == "bullish") or \
       (bias == "short" and ema_align == "bearish"):
        agree_count += 1

    # 3. S/R に対して有利な位置か（AI は decision で判断）
    if (bias == "long" and ai_decision in ("LONG", "WAIT")) or \
       (bias == "short" and ai_decision in ("SHORT", "WAIT")):
        agree_count += 1

    # 4. Volume Ratio が有利か
    if volume_ratio >= 1.3:
        agree_count += 1

    if agree_count >= 3:
        return "agree"
    elif agree_count == 2:
        return "partial"
    else:
        return "disagree"


def run_ai_advice(machine_result: Dict, qualitative: Dict) -> Optional[Dict]:
    """
    AI 審査を実行し結果を返す。エラー時は None を返す。

    Returns
    -------
    dict or None
        {"decision": ..., "quality": ..., "confidence": ..., "notes": ...}
    """
    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    system_prompt = _load_prompt()
    user_message = _build_user_message(machine_result, qualitative)

    for attempt in range(1, config.AI_RETRY_COUNT + 1):
        try:
            response = client.chat.completions.create(
                model=config.OPENAI_ADVICE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                timeout=config.AI_TIMEOUT_SEC,
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)

            # 型チェック・正規化
            decision = parsed.get("decision", "NO_TRADE").upper()
            if decision not in ("LONG", "SHORT", "WAIT", "NO_TRADE"):
                decision = "NO_TRADE"
            quality = parsed.get("quality", "C")
            if quality not in ("A", "B", "C"):
                quality = "C"
            confidence = float(parsed.get("confidence", 0.5))
            confidence = round(max(0.0, min(1.0, confidence)), 2)
            notes = str(parsed.get("notes", ""))[:300]

            return {
                "decision": decision,
                "quality": quality,
                "confidence": confidence,
                "notes": notes,
            }

        except Exception as e:
            logger.warning("AI advice エラー (attempt %d/%d): %s", attempt, config.AI_RETRY_COUNT, e)
            if attempt < config.AI_RETRY_COUNT:
                time.sleep(1)

    return None
