"""
evaluator.py – バックテスト結果の勝敗評価・RR 実現値算出
"""
import sys
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BACKTEST_RESULTS_DIR = Path("data/historical/backtest_results")
EVAL_CSV_PATH = Path("data/historical/backtest_results/evaluation.csv")

CSV_HEADERS = [
    "timestamp", "bias", "phase", "market_regime",
    "long_display_score", "short_display_score", "confidence",
    "atr_ratio", "volume_ratio", "critical_zone", "no_trade_flags",
    "primary_setup_side", "primary_setup_status",
    "entry_price", "stop_loss", "tp1", "rr_estimate",
    "outcome",            # win / loss / no_trade / expired
    "actual_rr",          # 実現 RR（TP 到達なら正値、SL 到達なら負値）
    "pnl_pct",            # 損益 %
    "hold_bars",          # 保有足数
]


def _ensure_eval_csv() -> None:
    EVAL_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EVAL_CSV_PATH.exists():
        with open(EVAL_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)


def evaluate_outcome(
    entry_price: float,
    stop_loss: float,
    tp1: float,
    bias: str,
    future_prices: pd.DataFrame,
    max_bars: int = 48,
) -> Tuple[str, float, float, int]:
    """
    エントリー後の価格推移から結果を判定する。

    Parameters
    ----------
    future_prices: エントリー後の OHLC データ (high, low 列が必要)
    max_bars: 最大保有足数（期限切れ = expired）

    Returns
    -------
    (outcome, actual_rr, pnl_pct, hold_bars)
    outcome: win / loss / expired
    """
    if len(future_prices) == 0:
        return "expired", 0.0, 0.0, 0

    stop_dist = abs(entry_price - stop_loss)
    tp_dist = abs(tp1 - entry_price)

    for i, (_, row) in enumerate(future_prices.iterrows()):
        if i >= max_bars:
            break
        h, l = row["high"], row["low"]

        if bias == "long":
            if l <= stop_loss:
                actual_rr = round(-(stop_dist / stop_dist), 2)  # -1.0
                pnl = round((stop_loss - entry_price) / entry_price * 100, 2)
                return "loss", actual_rr, pnl, i + 1
            if h >= tp1:
                actual_rr = round(tp_dist / stop_dist, 2)
                pnl = round((tp1 - entry_price) / entry_price * 100, 2)
                return "win", actual_rr, pnl, i + 1
        else:  # short
            if h >= stop_loss:
                actual_rr = -1.0
                pnl = round((entry_price - stop_loss) / entry_price * 100, 2)
                return "loss", actual_rr, pnl, i + 1
            if l <= tp1:
                actual_rr = round(tp_dist / stop_dist, 2)
                pnl = round((entry_price - tp1) / entry_price * 100, 2)
                return "win", actual_rr, pnl, i + 1

    return "expired", 0.0, 0.0, min(max_bars, len(future_prices))


def evaluate_backtest_results(
    results: List[Dict],
    df_4h: pd.DataFrame,
) -> pd.DataFrame:
    """
    バックテスト判定結果と 4H ヒストリカルデータを突合し、勝敗を評価する。

    Parameters
    ----------
    results: runner.py の出力リスト
    df_4h: 全期間の 4H ローソク足
    """
    _ensure_eval_csv()
    rows = []

    for r in results:
        bias = r.get("bias", "wait")
        primary_side = r.get("primary_setup_side", "none")

        if bias == "wait" or primary_side == "none":
            outcome = "no_trade"
            entry_price = 0.0
            stop_loss = 0.0
            tp1 = 0.0
            rr = 0.0
            actual_rr = 0.0
            pnl = 0.0
            hold_bars = 0
        else:
            # エントリー価格とセットアップ情報取得
            setup = r.get(f"{primary_side}_setup", {})
            entry_price = setup.get("entry_mid", r.get("current_price", 0.0))
            stop_loss = setup.get("stop_loss", 0.0)
            tp1 = setup.get("tp1", 0.0)
            rr = setup.get("rr_estimate", 0.0)

            if setup.get("status") == "invalid":
                outcome = "no_trade"
                actual_rr = 0.0
                pnl = 0.0
                hold_bars = 0
            else:
                # エントリー後の価格データを取得
                ts_str = r.get("timestamp", "")
                try:
                    ts = pd.to_datetime(ts_str)
                    future = df_4h[df_4h["timestamp"] > ts].head(48).reset_index(drop=True)
                    outcome, actual_rr, pnl, hold_bars = evaluate_outcome(
                        entry_price, stop_loss, tp1, primary_side, future
                    )
                except Exception as e:
                    logger.warning("勝敗評価エラー: %s", e)
                    outcome = "expired"
                    actual_rr = 0.0
                    pnl = 0.0
                    hold_bars = 0

        row = {
            "timestamp": r.get("timestamp", ""),
            "bias": bias,
            "phase": r.get("phase", ""),
            "market_regime": r.get("market_regime", ""),
            "long_display_score": r.get("long_display_score", 0),
            "short_display_score": r.get("short_display_score", 0),
            "confidence": r.get("confidence", 0),
            "atr_ratio": r.get("atr_ratio", 0),
            "volume_ratio": r.get("volume_ratio", 0),
            "critical_zone": r.get("critical_zone", False),
            "no_trade_flags": "|".join(r.get("no_trade_flags", [])),
            "primary_setup_side": primary_side,
            "primary_setup_status": r.get("primary_setup_status", "none"),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "tp1": round(tp1, 2),
            "rr_estimate": rr,
            "outcome": outcome,
            "actual_rr": actual_rr,
            "pnl_pct": pnl,
            "hold_bars": hold_bars,
        }
        rows.append(row)

    # CSV 追記
    with open(EVAL_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerows(rows)

    df = pd.DataFrame(rows)
    _print_summary(df)
    return df


def _print_summary(df: pd.DataFrame) -> None:
    """サマリー統計を出力する。"""
    if df.empty:
        logger.info("評価データなし")
        return

    total = len(df)
    traded = df[df["outcome"] != "no_trade"]
    no_trade = df[df["outcome"] == "no_trade"]
    wins = df[df["outcome"] == "win"]
    losses = df[df["outcome"] == "loss"]

    print("\n" + "=" * 60)
    print("■ バックテスト評価サマリー")
    print("=" * 60)
    print(f"総ステップ数   : {total}")
    print(f"見送り (no_trade): {len(no_trade)} ({len(no_trade)/total*100:.1f}%)")
    print(f"エントリー数   : {len(traded)}")

    if len(traded) > 0:
        win_rate = len(wins) / len(traded) * 100
        avg_rr_win = wins["actual_rr"].mean() if len(wins) > 0 else 0
        avg_rr_loss = losses["actual_rr"].mean() if len(losses) > 0 else 0
        print(f"勝率           : {win_rate:.1f}%")
        print(f"平均 RR (勝ち) : {avg_rr_win:.2f}")
        print(f"平均 RR (負け) : {avg_rr_loss:.2f}")
        print(f"総損益 (%合計) : {df['pnl_pct'].sum():.2f}%")

    print("\n■ bias 別集計")
    for bias_val in ["long", "short", "wait"]:
        sub = df[df["bias"] == bias_val]
        if len(sub) > 0:
            w = sub[sub["outcome"] == "win"]
            t = sub[sub["outcome"] != "no_trade"]
            wr = len(w) / len(t) * 100 if len(t) > 0 else 0
            print(f"  {bias_val:6}: {len(sub):4} 件, エントリー {len(t)}, 勝率 {wr:.1f}%")

    print("\n■ phase 別集計")
    for phase in df["phase"].unique():
        sub = df[(df["phase"] == phase) & (df["outcome"] != "no_trade")]
        if len(sub) > 0:
            w = sub[sub["outcome"] == "win"]
            wr = len(w) / len(sub) * 100
            print(f"  {phase:20}: {len(sub):4} 件, 勝率 {wr:.1f}%")

    print("\n■ confidence 帯別集計")
    for lo, hi in [(0, 50), (50, 65), (65, 75), (75, 85), (85, 101)]:
        sub = df[(df["confidence"] >= lo) & (df["confidence"] < hi) &
                 (df["outcome"] != "no_trade")]
        if len(sub) > 0:
            w = sub[sub["outcome"] == "win"]
            wr = len(w) / len(sub) * 100
            print(f"  confidence {lo:3}〜{hi:3}: {len(sub):4} 件, 勝率 {wr:.1f}%")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    # 使用例:
    # python backtest/evaluator.py data/historical/backtest_results/backtest_XXXX.json data/historical/btc_4h.csv
    import sys

    if len(sys.argv) < 3:
        print("Usage: python evaluator.py <backtest_json> <btc_4h_csv>")
        sys.exit(1)

    results_path = Path(sys.argv[1])
    csv_4h_path = Path(sys.argv[2])

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    df_4h = pd.read_csv(csv_4h_path)
    df_4h["timestamp"] = pd.to_datetime(df_4h["timestamp"])
    df_4h = df_4h.sort_values("timestamp").reset_index(drop=True)

    evaluate_backtest_results(results, df_4h)
