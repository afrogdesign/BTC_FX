# BTC 半自動トレード補佐システム

BTCUSDT (MEXC パーペチュアル) を対象に、機械判定と OpenAI AI 審査を組み合わせて
`long / short / wait` の三択シグナルを定期生成しメール通知するシステムです。

> ⚠️ **注意**: 本システムは情報提供目的です。自動発注や資金管理は行いません。
> 投資判断は必ず自己責任で行ってください。

---

## アーキテクチャ

```
Layer 1 (機械判定)
  MEXC API → EMA/RSI/ATR/Volume → 構造判定 → S/Rゾーン → レジーム
  → スコアリング → RR評価 → Confidence → Bias → Phase

Layer 2 (AI審査)
  機械判定結果 → OpenAI (gpt-4o) → decision/quality/confidence/notes

通知
  差分トリガー判定 → OpenAI (gpt-4o-mini) 要約 → メール送信
```

---

## セットアップ

### 1. Python バージョン確認

```bash
python --version  # 3.11 以上推奨
```

### 2. 依存パッケージのインストール

```bash
cd btc_monitor
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開いて以下の値を入力してください。

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API キー | ✅ |
| `SMTP_HOST` | SMTP サーバー (デフォルト: smtp.gmail.com) | ✅ |
| `SMTP_PORT` | SMTP ポート (デフォルト: 587) | ✅ |
| `SMTP_USER` | 送信元メールアドレス | ✅ |
| `SMTP_PASSWORD` | アプリパスワード (Gmail の場合) | ✅ |
| `MAIL_FROM` | 差出人アドレス | ✅ |
| `MAIL_TO` | 宛先アドレス | ✅ |

> Gmail の場合は「アプリパスワード」を使用してください。
> アカウント設定 → セキュリティ → 2 段階認証 → アプリパスワード

### 4. ログディレクトリの確認

```bash
mkdir -p logs/signals logs/notifications logs/csv logs/errors
```

---

## 起動方法

### 通常起動（スケジューラーモード）

```bash
python main.py
```

`REPORT_TIMES` (デフォルト: `09:05,13:05,17:05,21:05,01:05,05:05` JST) に設定した
時刻ごとに自動実行します。

### ドライランモード（メール送信なし）

`.env` に `DRYRUN_MODE=true` を設定して起動します。

```bash
DRYRUN_MODE=true python main.py
```

### 1 回だけ即時実行（テスト用）

```python
# Python インタープリターで実行
from main import run_cycle
result = run_cycle()
print(result["bias"], result["confidence"])
```

---

## 判定フロー

```
1. データ取得      → 4H/1H/15m 確定足 + Funding Rate
2. 指標計算        → EMA20/50/200, RSI14, ATR14, Volume Ratio
3. 構造判定        → スイング検出, HH/HL/LH/LL
4. S/R ゾーン      → 各時間足からゾーン抽出・統合
5. レジーム判定    → uptrend/downtrend/range/volatile/transition
6. スコア算出      → long/short スコア (0-100)
7. Bias 決定       → score_gap ≥ 10→long, ≤ -12→short, それ以外→wait
8. Phase 確定      → trend_following/pullback/breakout/range/reversal_risk
9. Confidence 算出 → 0-100 (long≥65, short≥70 で通知)
10. セットアップ   → entry_zone, SL, TP1/TP2, RR
11. AI 審査        → OpenAI gpt-4o → decision/quality/confidence
12. 通知判定       → 差分トリガー + クールダウン判定
13. 要約生成       → OpenAI gpt-4o-mini でメール本文作成
14. メール送信     → SMTP with TLS
```

---

## 通知トリガー条件

以下のいずれかに該当し、かつ Confidence が方向別最低基準を満たす場合に通知します。

1. `primary_setup_status` が `invalid → watch` / `invalid → ready` に変化
2. `primary_setup_status` が `watch → ready` に変化
3. `bias` が `wait → long` / `wait → short` に変化
4. `confidence` が前回通知比 ±10 以上変化
5. `agreement_with_machine` が `agree ↔ disagree` に変化

**抑制条件**: bias=wait で変化なし、invalid フラグ 2 つ以上で変化なし、
同一種別を 60 分以内に送信済み

---

## バックテスト

```bash
# 1. ヒストリカルデータを配置
# data/historical/btc_4h.csv, btc_1h.csv, btc_15m.csv
# (必須列: timestamp, open, high, low, close, volume)

# 2. バックテスト実行
python backtest/runner.py

# 3. 勝敗評価
python backtest/evaluator.py data/historical/backtest_results/backtest_XXXX.json data/historical/btc_4h.csv
```

---

## ファイル構成

```
btc_monitor/
├── main.py              # エントリーポイント・スケジューラー
├── config.py            # 設定値ロード・バリデーション
├── requirements.txt
├── .env                 # 秘密情報（Git 除外）
├── .env.example         # テンプレート
├── NEXT_TASK.md         # 作業進捗記録
├── prompts/             # AI プロンプトファイル
├── src/
│   ├── data/            # データ取得・検証
│   ├── indicators/      # EMA/RSI/ATR/Volume
│   ├── analysis/        # 構造・S/R・レジーム・スコア・RR・定性
│   ├── ai/              # OpenAI 連携
│   ├── notification/    # 通知トリガー・メール送信
│   └── storage/         # JSON/CSV 保存・クリーンアップ
├── backtest/            # バックテストフレームワーク
└── logs/                # ログ（Git 除外）
```

---

## 設定パラメータ（主要）

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `EMA_FAST/MID/SLOW` | 20/50/200 | EMA 期間 |
| `RSI_LENGTH` | 14 | RSI 期間 |
| `LONG_SHORT_DIFF_THRESHOLD` | 10 | Long バイアス判定閾値 |
| `SHORT_LONG_DIFF_THRESHOLD` | 12 | Short バイアス判定閾値 |
| `CONFIDENCE_LONG_MIN` | 65 | Long 通知 Confidence 最低値 |
| `CONFIDENCE_SHORT_MIN` | 70 | Short 通知 Confidence 最低値 |
| `MIN_RR_RATIO` | 1.3 | 最小 RR |
| `SL_ATR_MULTIPLIER` | 1.5 | SL = Entry ± ATR × 1.5 |
| `ALERT_COOLDOWN_MINUTES` | 60 | 通知クールダウン（分） |
| `DRYRUN_MODE` | false | true でメール送信をスキップ |

---

## ログ

| 種別 | 場所 | 保持期間 |
|------|------|---------|
| 判定 JSON | `logs/signals/` | 90 日 |
| 通知ログ | `logs/notifications/` | 180 日 |
| エラーログ | `logs/errors/` | 180 日 |
| CSV 累積 | `logs/csv/trades.csv` | 無期限 |
| ヘルスチェック | `logs/heartbeat.txt` | 常時更新 |

---

## セキュリティ

- `.env` ファイルはリポジトリにコミットしない (`.gitignore` 済み)
- ログ・エラーメッセージに API キー・パスワードは出力しない (`***MASKED***`)
- 起動時に必須環境変数の存在を検証し、欠損時は `SystemExit(1)` で終了

---

## 更新履歴

- **v1.1**: CODEX実装仕様書 v1.1 に基づき初版実装
