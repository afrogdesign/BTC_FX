# BTC半自動トレード補佐システム CODEX実装仕様書 完全版 v1.1

> **目的**: 本書は統合版設計書 v4.0 と実装仕様書 v1.0 を統合し、矛盾を解消した最終版です。機械判定と AI 審査の設計思想を維持しつつ、具体的なディレクトリ構成、環境変数、アルゴリズム仕様、JSON スキーマ、テスト方針を定義します。ここに書かれた数値や条件は確定値として扱い、次期改訂があるまで変更しないものとします。

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [ディレクトリ構成](#2-ディレクトリ構成)
3. [環境設定 (.env)](#3-環境設定-env)
4. [要件確定事項](#4-要件確定事項)
5. [モジュール設計](#5-モジュール設計)
6. [アルゴリズム仕様](#6-アルゴリズム仕様)
7. [JSON スキーマ](#7-json-スキーマ)
8. [プロンプト仕様](#8-プロンプト仕様)
9. [実装順序](#9-実装順序)
10. [テスト戦略](#10-テスト戦略)
11. [サンプル JSON](#11-サンプル-json)
12. [更新履歴](#12-更新履歴)

---

## 1. プロジェクト概要

### 1-1. システム定義

- **名称**: BTC半自動トレード補佐システム
- **対象銘柄**: BTCUSDT (MEXC パーペチュアル)
- **目的**: 機械的な定量ロジックと OpenAI による定性審査を組み合わせ、`long / short / wait` の三択シグナルを定期的に生成しメールで通知する。自動発注や資金管理は行わない。

### 1-2. アーキテクチャ概要

本システムは以下の 2 層構成で動作する。

1. **Layer 1 – 機械判定**: MEXC から 4H/1H/15m の確定足データを取得し、EMA、RSI、ATR、Volume Ratio を計算する。構造判定 (スイング高値安値・HH/HL/LH/LL)、S/R ゾーン抽出・統合、市場レジーム判定、スコアリング、RR 評価、Confidence 算出、Bias 決定、Phase 確定を順番に実行する。
2. **Layer 2 – AI 審査**: 機械判定結果と定性コンテキストを OpenAI モデルに送り、`decision` (`LONG`/`SHORT`/`WAIT`/`NO_TRADE`) と品質評価 (quality, confidence) を取得する。AI 審査は補助的な意見とし、bias が最終決定を担う。AI エラー時は `ai_advice` を `null` とし、機械判定のみで通知する。

### 1-3. 技術スタック

```text
言語        : Python 3.11+
データ取得  : requests + MEXC Public REST API
指標計算    : pandas + numpy（ta-lib は使用しない）
AI 連携     : openai Python SDK
メール送信  : smtplib (SMTP with TLS)
スケジュール: schedule ライブラリ または cron
ログ        : JSON / CSV / テキスト
```

---

## 2. ディレクトリ構成

以下に示すディレクトリ構造は確定版であり、すべてのモジュールはここに準拠して配置する。

```text
btc_monitor/
├── main.py                        # エントリーポイント・スケジューラー
├── config.py                      # 設定値ロード・バリデーション
├── requirements.txt
├── .env                           # 秘密情報（Git 除外）
├── .env.example                   # テンプレート
├── .gitignore
│
├── prompts/
│   ├── advice_prompt.md           # AI 審査プロンプト
│   └── summary_prompt.md          # 要約生成プロンプト
│
├── src/
│   ├── data/
│   │   ├── fetcher.py             # MEXC API データ取得
│   │   └── validator.py           # データ検証・欠損チェック
│   ├── indicators/
│   │   ├── ema.py                 # EMA 計算
│   │   ├── rsi.py                 # RSI 計算
│   │   ├── atr.py                 # ATR 計算
│   │   └── volume.py              # Volume Ratio 計算
│   ├── analysis/
│   │   ├── structure.py           # スイング検出・価格構造
│   │   ├── support_resistance.py  # S/R ゾーン抽出・統合
│   │   ├── regime.py              # 市場レジーム判定
│   │   ├── phase.py               # Phase 分類
│   │   ├── scoring.py             # スコアリング計算
│   │   ├── confidence.py          # Confidence 算出
│   │   ├── rr.py                  # RR 評価・エントリーゾーン計算
│   │   └── qualitative.py         # 定性コンテキスト算出
│   ├── ai/
│   │   ├── advice.py              # AI 審査呼び出し
│   │   └── summary.py             # 要約生成呼び出し
│   ├── notification/
│   │   ├── trigger.py             # 通知トリガー判定
│   │   └── email_sender.py        # メール送信
│   └── storage/
│       ├── json_store.py          # JSON 保存・読み込み
│       ├── csv_logger.py          # CSV ログ追記
│       └── cleanup.py             # 古いログ削除
│
├── logs/
│   ├── heartbeat.txt              # 死活監視用
│   ├── last_result.json           # 前回実行結果（差分比較用）
│   ├── last_notified.json         # 前回通知結果（抑制用）
│   ├── signals/                   # 判定 JSON 保存 (90 日)
│   ├── notifications/             # 通知ログ保存 (180 日)
│   ├── csv/
│   │   └── trades.csv             # CSV ログ
│   └── errors/                    # エラーログ保存 (180 日)
│
├── data/
│   └── historical/                # バックテスト用ローカルデータ
└── backtest/
    ├── runner.py                  # バックテスト実行
    └── evaluator.py               # 勝敗評価
```

ログディレクトリは `.gitignore` に含め、公開リポジトリにコミットしない。古いログのクリーンアップは `src/storage/cleanup.py` で行い、実行開始時に 24 時間以上経過していた場合のみ削除処理を実行する。

---

## 3. 環境設定 (.env)

### 3-1. .env.example（確定値）

以下は `.env.example` に記載する全環境変数とデフォルト値の一覧である。開発環境では `.env` にコピーして秘密値を入力する。

```bash
# === MEXC ===
MEXC_BASE_URL=https://contract.mexc.com
MEXC_SYMBOL=BTC_USDT

# === OpenAI ===
OPENAI_API_KEY=
OPENAI_SUMMARY_MODEL=gpt-4o-mini    # 要約生成モデル
OPENAI_ADVICE_MODEL=gpt-4o          # AI 審査モデル

# === メール送信 ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=
MAIL_TO=

# === タイムゾーン ===
TIMEZONE=Asia/Tokyo

# === スケジュール ===
# 4H 足確定後の実行時刻 (JST)。正確な日時は取引所サーバー時刻を基準とする。
REPORT_TIMES=09:05,13:05,17:05,21:05,01:05,05:05

# === 指標パラメータ ===
EMA_FAST=20
EMA_MID=50
EMA_SLOW=200
RSI_LENGTH=14
ATR_LENGTH=14

# === データ取得本数 ===
FETCH_LIMIT_4H=300
FETCH_LIMIT_1H=500
FETCH_LIMIT_15M=500

# === スコアリング閾値 ===
# long_display_score − short_display_score >= 10 なら long、<= -12 なら short、その他は wait
LONG_SHORT_DIFF_THRESHOLD=10
SHORT_LONG_DIFF_THRESHOLD=12

# === Confidence 閾値 ===
CONFIDENCE_LONG_MIN=65
CONFIDENCE_SHORT_MIN=70
CONFIDENCE_ALERT_CHANGE=10    # 前回通知との差がこの値以上なら通知トリガー

# === ATR フィルター ===
MAX_ACCEPTABLE_ATR_RATIO=2.0
MIN_ACCEPTABLE_ATR_RATIO=0.3
MIN_RR_RATIO=1.3
SL_ATR_MULTIPLIER=1.5

# === Funding Rate 閾値 (小数)
FUNDING_SHORT_WARNING=-0.03
FUNDING_SHORT_PROHIBITED=-0.05
FUNDING_LONG_WARNING=0.05
FUNDING_LONG_PROHIBITED=0.08

# === スイング検出パラメータ ===
SWING_N_4H=3
SWING_N_1H=2
SWING_N_15M=2

# === API レート制限・タイムアウト ===
REQUEST_INTERVAL_SEC=0.3
API_TIMEOUT_SEC=5
API_RETRY_COUNT=3

# === AI API ===
AI_TIMEOUT_SEC=5
AI_RETRY_COUNT=3
AI_CACHE_ENABLED=false        # 初版は AI 審査結果をキャッシュしない

# === ヘルスチェック ===
HEARTBEAT_FILE=logs/heartbeat.txt
HEALTH_CHECK_MAX_HOURS=6

# === ログ保持期間（日） ===
LOG_RETENTION_SIGNALS_DAYS=90
LOG_RETENTION_NOTIFICATIONS_DAYS=180
LOG_RETENTION_ERRORS_DAYS=180

# === 通知クールダウン（分） ===
ALERT_COOLDOWN_MINUTES=60

# === ドライランモード ===
DRYRUN_MODE=false

# === サーバー時刻許容誤差（秒） ===
SERVER_TIME_TOLERANCE_SEC=2
```

### 3-2. 起動前バリデーション

`config.py` では `.env` の読み込み後、必須キー (`OPENAI_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO`) の存在と空文字でないことを検証する。欠損している場合は `EnvironmentError` を発生させ、ログに `***MASKED***` を出力する。パスワードや API キーなどの秘密値はログ・エラーメッセージに直接表示せず、常に `***MASKED***` に置換する。

---

## 4. 要件確定事項

### 4-1. 判定順序

処理の順序は下表に従い、前の工程が完了してから次へ進む。特に Phase 確定は bias 決定後に実行する。

1. **データ取得** – 4H/1H/15m の確定足を取得し未確定足を除外。
2. **指標計算** – EMA20/50/200、RSI14、ATR14、Volume Ratio を計算。
3. **構造判定** – スイング高値・安値を検出し、HH/HL/LH/LL を判定。
4. **S/R ゾーン抽出・統合** – 各時間足のスイングからサポート・レジスタンス候補を生成し、ATR 比を用いて近接ゾーンを統合する。
5. **市場レジーム判定** – `uptrend` / `downtrend` / `range` / `volatile` / `transition` の 5 分類。transition は上向き・下向きの条件を持つ。
6. **スコア算出** – long_score / short_score を地合い・構造・トリガー・リスクの4ブロックで加点・減点し、-30〜80 を 0〜100 に正規化。
7. **RR 評価** – エントリーゾーン中心からストップラインおよび TP1/TP2 の位置と期待 RR を計算。
8. **禁止条件チェック** – RR 不足、ATR 極端値、Funding Rate 極端値、重要ゾーン直上直下などを確認し invalid を設定。
9. **Confidence 算出** – 時間足整合数やレジームの明確さ、Phase 補正、RR 品質、反対ゾーンまでの余白、危険ペナルティを加減算して 0〜100 に丸める。
10. **Bias 決定** – `score_gap = long_display_score - short_display_score` を評価。10 以上なら `long`、-12 以下なら `short`、それ以外は `wait`。
11. **Phase 確定** – bias 決定後に `trend_following` / `pullback` / `breakout` / `range` / `reversal_risk` へ分類。
12. **定性コンテキスト算出** – セッション分類、pullback 深度、wick rejection、実体強さ、range state、late_entry_risk、trend_exhaustion_risk、rule_conflicts 等。
13. **AI 審査** – 機械判定と定性コンテキストを AI モデルに送り、`decision`, `quality`, `confidence` を取得。AI エラー時は `ai_advice` を `null` とし、フォールバック本文を使用する。
14. **セットアップ評価** – long/short それぞれの `setup.status` (`ready`/`watch`/`invalid`)、entry_zone、stop_loss、tp1、tp2、RR、距離 % を算出。
15. **primary_setup_side / status 決定** – bias を主ラベルとしつつ、各 setup.status を比較して通知の主語 (`primary_setup_side`) と状況 (`primary_setup_status`) を決定する。
16. **通知判定** – 前回結果 (`logs/last_result.json`) と前回通知 (`logs/last_notified.json`) を比較し、差分が所定条件を満たす場合に通知。
17. **ログ保存・通知** – JSON 出力と CSV ログを保存し、メール本文を作成して送信。通知しない場合でも結果を保存して次回差分判定に利用する。

### 4-2. bias と setup.status の役割分担

| フィールド              | 役割                           | 値                              |
|-----------------------|--------------------------------|--------------------------------|
| `bias`                | 方向性の主ラベル               | `long` / `short` / `wait`      |
| `long_setup.status`   | ロング側のエントリー接近度     | `ready` / `watch` / `invalid`  |
| `short_setup.status`  | ショート側のエントリー接近度   | `ready` / `watch` / `invalid`  |
| `primary_setup_side`  | 通知・件名用の方向ラベル       | `long` / `short` / `none`      |
| `primary_setup_status`| 通知・件名用の接近度ラベル     | `ready` / `watch` / `invalid` / `none` |

**primary_setup_side / status の決定ロジック**:

```python
if bias == "long":
    primary_setup_side = "long"
    primary_setup_status = long_setup.status
elif bias == "short":
    primary_setup_side = "short"
    primary_setup_status = short_setup.status
else:
    # bias=wait の場合、より進捗が進んでいる側を採用
    if long_setup.status == "ready":
        primary_setup_side = "long"
        primary_setup_status = "ready"
    elif short_setup.status == "ready":
        primary_setup_side = "short"
        primary_setup_status = "ready"
    elif long_setup.status == "watch" and short_setup.status != "watch":
        primary_setup_side = "long"
        primary_setup_status = "watch"
    elif short_setup.status == "watch" and long_setup.status != "watch":
        primary_setup_side = "short"
        primary_setup_status = "watch"
    else:
        primary_setup_side = "none"
        primary_setup_status = "none"
```

**setup.status の厳密定義**:

- `ready`: エントリーゾーン内に価格が入っており、トリガー条件 (高値/安値更新、ボリューム増など) が成立した状態。即時に仕掛け可能。
- `watch`: 条件は整いつつあるがトリガー未成立。例えばエントリーゾーンとの距離が 0〜0.3 ATR 以内、またはトリガー確認待ちの状況。監視継続が必要。
- `invalid`: 次のいずれかに該当する場合。
  - RR が `MIN_RR_RATIO` 未満 (1.3) で利益見込みが低い。
  - ATR 比が `MAX_ACCEPTABLE_ATR_RATIO` を超えるか `MIN_ACCEPTABLE_ATR_RATIO` 未満でボラティリティが極端。
  - Funding Rate が `FUNDING_LONG_PROHIBITED` 未満または `FUNDING_SHORT_PROHIBITED` を超える。
  - 重要サポート/レジスタンスへ ATR×0.5 以内に接近しリスクが高い。
  - confidence が方向別最低基準 (65 または 70) 未満。
  - その他、禁止フラグ (強い逆行シグナル、レジームが volatile など) が 2 つ以上発動した場合。

この定義により、機械判定が `wait` でも片側の setup.status が `ready` であれば、bias を `wait` としつつ監視・通知することができる。

### 4-3. transition と transition_direction

`market_regime` が `transition` の場合、相場が上昇への移行 (up) か下降への移行 (down) かを `transition_direction` に記録する。条件は以下のとおり。

- **上向き transition**: 以下の条件のうち 3 つ以上が成立。
  1. EMA20 が EMA50 に接近またはクロス直後 (差が ATR×0.5 以内) で EMA20 が上向き。
  2. EMA50 の直近 3 本平均傾きが -0.05%/本 を上回る (横ばい〜上向き)。
  3. RSI(14) ≥ 50。
  4. 直近 2 スイング (4H 足) で高値または安値が切り上がっている。
- **下向き transition**: 上記の上向き条件を下降版に置き換えたもので、EMA20 が EMA50 に向かい、EMA50 の傾きが +0.05%/本 以下、RSI(14) < 50、スイング高値安値が切り下がる場合。

`market_regime` が `uptrend`/`downtrend`/`range`/`volatile` の場合は `transition_direction` を空文字にする。

### 4-4. AI と機械の一致判定

AI 審査の `agreement_with_machine` は、以下の主要 4 条件の一致数で決定する。

1. 上位足方向 (4H レジーム) が機械判定と同じか。
2. EMA の並び (bullish/bearish/mixed) が機械判定の方向と整合するか。
3. 現在価格が有効な S/R ゾーンに対して有利な位置にあるか (support 上方・resistance 下方)。
4. Volume Ratio と Funding Rate が方向に優位か。

一致数が 3〜4 の場合 `agree`、2 の場合 `partial`、0〜1 の場合 `disagree` とする。不一致時でも bias は機械判定を優先し、件名には `⚠️ AI審査:decision` を付与する。

### 4-5. WAIT と NO_TRADE

用語の混乱を避けるため `wait` と `no_trade` を明確に区別する。

| 値        | 意味                                  | 発生条件 |
|-----------|---------------------------------------|----------|
| `WAIT`    | 方向候補はあるがタイミング待ち         | bias が long/short だが setup.status が `watch` |
| `NO_TRADE`| 条件不足または期待値が低く見送り推奨   | bias が `wait` または invalid 条件が 2 つ以上 |

メール本文では `WAIT` を「監視中」、`NO_TRADE` を「見送り推奨」と表記する。AI 審査の `decision` でも同じ用語を使用する。

### 4-6. critical_zone の効力

`critical_zone=true` の場合、重要なサポート・レジスタンスと現在価格が接触していることを示す。このフラグは以下の効果を持つ。

- confidence を 10 点減点する (算出後に適用)。
- AI 審査プロンプトに `critical_zone: true` を明示的に渡す。
- bias を強制的に wait に変更しない。方向は維持しつつリスクの高さを示す。
- メール本文に `⚠️ CRITICAL ZONE: 重要サポレジと現在価格が接触中` を赤字相当で表示する。

### 4-7. AI 審査モデル・タイムアウト・リトライ

OpenAI のモデル設定は以下を採用する。全て `.env` から読み込み、開発時は自由に変更可能とするが、初版では下記の値をデフォルトとする。

| 項目            | 値                         |
|----------------|----------------------------|
| 要約生成モデル | `gpt-4o-mini`               |
| AI 審査モデル   | `gpt-4o`                   |
| AI タイムアウト | 5 秒                       |
| AI リトライ回数 | 3 回                       |
| AI エラー時     | `ai_advice=null` とし通知継続 |
| AI キャッシュ   | 初版では無効 (`AI_CACHE_ENABLED=false`) |

### 4-8. バックテスト時の AI 審査

バックテストの目的は機械判定アルゴリズムの妥当性検証である。初期バックテストでは AI 審査を実行せず、機械判定の勝率や RR 別期待値、禁止条件の効果を評価する。AI 審査の効果を検証する場合は代表サンプルに対してのみ実行し、結果をキャッシュして再現性を確保する。キャッシュファイルは `data/historical/ai_cache/{timestamp}.json` 等に保存し、同じ入力に対して常に同じ `ai_advice` を返すようにする。

### 4-9. 通知トリガー

通知は毎回送信せず、前回通知との差分に基づいて発火する。次のいずれかの条件を満たし、かつ bias が long または short で confidence が方向別最低基準を満たす場合に通知する。

1. `primary_setup_status` が `invalid → watch` または `invalid → ready` に変化した。
2. `primary_setup_status` が `watch → ready` に変化した。
3. `bias` が `wait → long` または `wait → short` に変化した。
4. `confidence` が前回通知比で `CONFIDENCE_ALERT_CHANGE` (10) 以上増減した。
5. `agreement_with_machine` が `agree → disagree` または `disagree → agree` に変化した (新規のみ)。

**抑制条件**: 以下のいずれかに該当するときは通知しない。

- bias = `wait` かつ前回通知から変化なし。
- invalid 条件が 2 つ以上発動しており `primary_setup_status` が `invalid` のまま。
- 同一種別の通知を `ALERT_COOLDOWN_MINUTES` (60 分) 以内に送信済み。

### 4-10. データ取得本数

| 時間足 | 取得本数 | 理由                               |
|--------|--------|------------------------------------|
| 4H     | 300    | EMA200 と S/R 抽出に十分な長さ       |
| 1H     | 500    | 中期構造・レジーム判定に十分         |
| 15m    | 500    | トリガー検出と短期構造判定に十分     |

取得後は直近未確定足を除外する。サーバー時刻とのズレが `SERVER_TIME_TOLERANCE_SEC` (2 秒) を超えた場合は警告ログに記録し、処理は続行する。

### 4-11. Funding / Volume / OI の扱い

| データ           | 採用 | 用途                                           |
|------------------|------|------------------------------------------------|
| Funding Rate     | ✅  | スコアリングのリスクブロック・安全弁         |
| Volume Ratio     | ✅  | トリガーブロックの評価                         |
| Open Interest (OI)| ❌  | 初版では採用しない。将来バージョンで検討      |

Funding Rate は四半期ごとの資金調達率を小数表示で取得する。Volume Ratio は現 15m 足の出来高を直近 20 本の平均出来高で割った値と定義する。

### 4-12. 欠損時処理

| エラー種別                | 処理内容                                       | ログ記録        |
|---------------------------|------------------------------------------------|----------------|
| 市場データ欠損・空レスポンス | 該当サイクルをスキップ                        | `errors/` に記録 |
| API タイムアウト           | `API_RETRY_COUNT` 回リトライし失敗ならスキップ | `errors/` に記録 |
| AI 審査 API エラー         | `ai_advice=null` で機械判定のみ通知             | `errors/` に記録 |
| 要約生成 API エラー       | テンプレート本文で送信                          | `errors/` に記録 |
| SMTP エラー              | 本文を `logs/errors/` に保存し再送対象とする    | `errors/` に記録 |
| 予期しない例外            | スタックトレースを記録しエラー通知を送る         | `errors/` に記録 |

### 4-13. 時刻同期

取引所の `/api/v1/contract/ping` 等でサーバー時刻 (UTC) を取得し、ローカル実行時刻との差を計算する。誤差が ±`SERVER_TIME_TOLERANCE_SEC` 秒以内なら許容し、それ以上の場合は警告ログに記録するが処理は継続する。確定足判定はサーバー時刻に基づき行い、未確定足は除外する。

### 4-14. 丸め規則

| 対象            | 桁数           | 備考 |
|-----------------|----------------|------|
| price           | 小数 2 桁      | `round(x, 2)` |
| zone の価格      | 小数 2 桁      |             |
| % 系 (RR 距離等) | 小数 2 桁      |             |
| score           | 整数           | `int(round(x))` |
| confidence      | 整数           | `int(round(x))` |
| ATR / EMA       | 小数 2 桁      |             |

### 4-15. ログ保持期間

| ログ種別              | 保持期間             |
|---------------------|--------------------|
| 判定 JSON (`signals/`)| `LOG_RETENTION_SIGNALS_DAYS` 日 |
| 通知ログ (`notifications/`) | `LOG_RETENTION_NOTIFICATIONS_DAYS` 日 |
| エラーログ (`errors/`)     | `LOG_RETENTION_ERRORS_DAYS` 日 |
| CSV (`csv/trades.csv`)    | 削除しない（累積） |

### 4-16. セキュリティ

`.env` ファイルに秘密情報を保存し、`.gitignore` で `.env`, `logs/`, `data/historical/` を除外する。起動時は必須変数の存在を検証し欠損時は `SystemExit(1)` で終了する。ログやエラー出力には API キーやパスワードを含めない。

### 4-17. S/R 反応ルール

サポート・レジスタンスゾーンにおける反応回数は以下の方法で計測する。

- ヒゲまたは実体がゾーン `[low, high]` に入った場合を 1 反応とする。
- 同方向で連続する 3 本以内の足は 1 反応にまとめる (4 本目以降は別反応)。
- 各時間足で独立して反応をカウントし、ゾーン統合後に重み付けを行う。

### 4-18. signals の定義

各時間足の総合方向シグナル `signals_4h` / `signals_1h` / `signals_15m` は次の関数で決定する。`ema_alignment` は `bullish` / `bearish` / `mixed` を返し、`structure` は HH/HL/LH/LL 判定結果を返す。

```python
def calc_tf_signal(ema_alignment: str, structure: str) -> str:
    """
    EMA の並びと価格構造から時間足の方向シグナルを決める。
    bullish + 上昇構造 (hh_hl) → long
    bearish + 下降構造 (lh_ll) → short
    それ以外 → wait
    """
    if ema_alignment == "bullish" and structure == "hh_hl":
        return "long"
    elif ema_alignment == "bearish" and structure == "lh_ll":
        return "short"
    else:
        return "wait"
```

これら 3 値を `confidence.py` の `count_agreeing_timeframes()` に渡し、時間足一致数によるボーナスを計算する。

---

## 5. モジュール設計

モジュールは機能ごとに分割し、テストしやすい構造とする。クラスは使わず関数ベースで実装する。

### 5-1. `main.py`

エントリーポイント。スケジューラーを起動し、`REPORT_TIMES` に定義された時刻ごとに `run_cycle()` を登録する。

```python
def main() -> None:
    """スケジューラーを起動し、実行を開始する。"""


def run_cycle() -> dict:
    """
    1 サイクルの処理を実行し、判定結果 JSON を返す。
    エラー発生時は該当回をスキップし、DataFetchError 等を上層に伝える。
    """


def update_heartbeat() -> None:
    """`logs/heartbeat.txt` に現在時刻 (ISO 8601) を書き込み、ヘルスチェックに利用する。"""
```

### 5-2. `config.py`

`.env` を読み込んで辞書に変換し、必須キーの存在チェックを行う。`REQUIRED_KEYS` に欠損があれば `EnvironmentError` を raise する。読み込んだ値は適切な型 (int/float/bool/list) に変換し、アプリ全体で共有する。

### 5-3. `src/data/fetcher.py`

MEXC Contract REST API からローソク足、Funding Rate、サーバー時刻を取得する関数を提供する。`fetch_klines()` は interval ごとに `INTERVAL_MAP` (`4h→Hour4`, `1h→Hour1`, `15m→Min15`) を使い、未確定足を除外する。`fetch_funding_rate()` は小数で Funding Rate を返す。`get_server_time()` はサーバー時刻 (Unix ミリ秒) を返す。

### 5-4. `src/data/validator.py`

データの妥当性をチェックする関数群。ローソク足配列の長さ、NaN の有無、タイムスタンプ順序を確認し、異常があれば `False` を返す。判定前に必ず検証を行う。

### 5-5. `src/indicators/*`

EMA、RSI、ATR、Volume Ratio の計算を提供する。各関数は pandas.Series を入力として受け取り、同長の Series を返す。`get_ema_alignment()` は `bullish` / `bearish` / `mixed` を返し、`get_ema20_slope()` は n 本分の傾きを `up` / `down` / `flat` で返す。

### 5-6. `src/analysis/*`

スイング検出 (`structure.py`)、S/R ゾーン抽出 (`support_resistance.py`)、レジーム判定 (`regime.py`)、Phase 分類 (`phase.py`)、スコアリング (`scoring.py`)、confidence 計算 (`confidence.py`)、RR 評価 (`rr.py`)、定性コンテキスト算出 (`qualitative.py`) を含む。各モジュールは独立した関数として設計し、依存関係を明確にする。RR 評価では entry_zone (`low`, `high`) から entry_mid を `(low+high)/2` で算出し、stop_loss、tp1 (entry_mid + RR×stop距離), tp2 (entry_mid + 2×stop距離) を返す。invalid_line は各 setup の `invalid` 理由を説明し、bias=wait の場合は空文字にする。

### 5-7. `src/ai/*`

`advice.py` は機械判定結果と定性コンテキストをまとめて AI 審査モデルに送り、JSON 形式の返答を解析して返す。API エラーやタイムアウト時は `None` を返し、上層で `ai_advice=null` とする。`summary.py` は機械判定・AI 審査結果からメール本文を生成する。長文になり過ぎないように要点を抜粋し、AI 審査の不一致がある場合は注意喚起を入れる。

### 5-8. `src/notification/*`

`trigger.py` は現在結果と `logs/last_result.json`、`logs/last_notified.json` を比較し、通知トリガーを判定する。`email_sender.py` は smtplib によるメール送信を行い、失敗時はメッセージをローカルに保存して再送対象とする。再送処理は次回 `run_cycle()` の冒頭で行い、最大 3 回まで試行する。再送時は件名と本文を再生成する。

### 5-9. `src/storage/*`

`json_store.py` は判定結果 JSON の保存・読み込みを担当する。ファイル名は `YYYYMMDD_HHMMSS.json` とし、`logs/signals/` に 90 日間保存する。`csv_logger.py` は CSV への追記を行い、行項目はセクション [7. JSON スキーマ](#7-json-スキーマ) のうち主要項目と勝敗評価指標を記録する。`cleanup.py` は `LOG_RETENTION_*` に基づき古いファイルを削除する。

### 5-10. `backtest/` 下

`runner.py` はヒストリカルデータを読み込み、アルゴリズムを順次適用して結果を生成する。`evaluator.py` は真の価格推移と RR に基づき勝敗・RR の実現値を評価し、CSV に追記する。バックテスト時はメール送信せず結果出力のみを行う。

---

## 6. アルゴリズム仕様

### 6-1. スコアリング

長短それぞれの生スコアを地合い (0〜30)、構造 (0〜30)、トリガー (0〜20)、リスク (-30〜0) の 4 ブロックで計算し、合計を 0〜100 に正規化する。主な加点・減点例は下記のとおりだが、詳細はコード内の設定辞書にまとめる。

- **地合い**: 4H が uptrend/downtrend なら +15、EMA 配列が強気/弱気なら +10、EMA20 傾きが上向き/下向きなら +5、価格が EMA50 上なら +5、200EMA 上下は中立。
- **構造**: 4H で HH/HL 継続 +12、1H 整合 +10、重要ゾーン反発 +8。LH/LL 継続やレジスタンス直下などは相応にマイナス。
- **トリガー**: 15m の高値更新 +8、ボリューム増加 +7、RSI 過熱でない +5。トリガーが未成立なら 0。
- **リスク**: 重要レジスタンス直下 -10、RR 不足 -10、200EMA 攻防中 -8、レンジ中央 -8、ATR 極端低下 -5、長いヒゲ連続 -5。合計は -30 でクリップする。

生スコア (例えば -20〜70) を `score_display = max(0, min(100, (score_raw + 30) / 80 * 100))` で正規化し整数に丸める。`score_gap = long_display_score - short_display_score` を計算し、閾値 (`LONG_SHORT_DIFF_THRESHOLD=10`, `SHORT_LONG_DIFF_THRESHOLD=12`) を超えている側を bias とする。short は long より厳格な閾値を採用する。

### 6-2. Confidence 計算

confidence は環境品質を表し、以下の手順で 0〜100 に計算する。

1. **ベーススコア**: bias が `long` なら `long_display_score`、`short` なら `short_display_score`。bias = `wait` の場合は最大の表示スコアに 0.6 を掛け上限 50 に丸める。
2. **時間足整合ボーナス**: signals_4h/1h/15m が 3 つ一致なら +15、2 つ一致なら +8、1 つ以下なら 0。
3. **レジームの明確さ**: `uptrend`/`downtrend` +10、`transition` 0、`range` -5、`volatile` -10。
4. **Phase 補正**: `trend_following` +5、`pullback` +3、`breakout` 0、`range` -5、`reversal_risk` -10。
5. **RR 品質**: RR ≥ 2.0 +10、1.5–2.0 +5、1.3–1.5 0、<1.3 -15。
6. **反対ゾーンまでの余白**: 反対側の S/R までの距離を ATR14 で割り、1.5 以上なら +5、0.8〜1.5 なら 0、0.8 未満なら -5。
7. **危険ペナルティ**: `critical_zone` は -10、warning フラグ (Funding warning, ATR 極端など) は -5 ずつ減点。

最終値は 0〜100 にクリップし整数に丸める。direction 別通知最低基準として、long は `CONFIDENCE_LONG_MIN=65`、short は `CONFIDENCE_SHORT_MIN=70` を採用する。

### 6-3. Phase 判定

Bias 決定後に次の Phase に分類する。

- `trend_following`: uptrend/downtrend の継続で押し目・戻りが浅く高値更新/安値更新が続いている。
- `pullback`: uptrend/downtrend 中の深い調整からの反発を狙う局面。価格が EMA50〜200 の間にあることが多い。
- `breakout`: レンジを上抜け/下抜けした直後のリテスト成功局面。ブレイク足のボリューム増加やアクションプライスが確認条件となる。
- `range`: 明確なトレンドがなく、価格がサポートとレジスタンスの間で推移している。
- `reversal_risk`: トレンド終盤で逆行リスクが高まり、長いヒゲ連続や RSI 過熱、ダイバージェンスが出ている。警戒を促すため confidence に大きく減点する。

### 6-4. 禁止条件の詳細

禁止条件に該当すると `setup.status=invalid` となり、bias は `wait` になることが多い。主な禁止条件は次のとおり。

- **RR 不足**: `rr_estimate < MIN_RR_RATIO` (1.3)。
- **ATR 極端値**: ATR 比が `MAX_ACCEPTABLE_ATR_RATIO` (2.0) を超えるか `MIN_ACCEPTABLE_ATR_RATIO` (0.3) 未満。
- **Funding Rate 極端**: long 方向で Funding Rate ≥ `FUNDING_LONG_PROHIBITED`、short 方向で Funding Rate ≤ `FUNDING_SHORT_PROHIBITED`。
- **重要ゾーン直近**: エントリーゾーンが重要サポート/レジスタンスと ATR×0.5 以内で重なり、損切り幅が確保できない。
- **複数禁止フラグ**: 上記以外に ATR 比警告や Funding warning 等の warning フラグが 2 つ以上発動したとき。warning フラグの例: Funding Rate が `FUNDING_LONG_WARNING` 以上、`FUNDING_SHORT_WARNING` 以下、ATR 比が `MAX_ACCEPTABLE_ATR_RATIO×0.8` 以上、`MIN_ACCEPTABLE_ATR_RATIO×1.2` 未満など。

---

## 7. JSON スキーマ

判定結果は下記のフィールドを持つ JSON とし、キーの欠落や `null` 以外の型違いを認めない。丸め規則は [4-14](#4-14-丸め規則) に従う。

```json
{
  "timestamp_utc": "2024-01-01T13:05:00Z",            // 処理を開始した UTC 時刻 (ISO 8601)
  "timestamp_jst": "2024-01-01T22:05:00+09:00",        // JST 版 (タイムゾーン付き)
  "server_time_gap_sec": 1.2,                          // 取引所サーバーとローカルの差秒 (正はローカルが遅い)
  "bias": "long",                                    // long/short/wait
  "phase": "pullback",                              // trend_following/pullback/breakout/range/reversal_risk
  "market_regime": "transition",                    // uptrend/downtrend/range/volatile/transition
  "transition_direction": "up",                     // transition の方向 (up/down/"")
  "signals_4h": "long",                             // 各時間足シグナル (long/short/wait)
  "signals_1h": "long",
  "signals_15m": "wait",
  "long_display_score": 72,                          // 0〜100
  "short_display_score": 55,                         // 0〜100
  "score_gap": 17,                                   // long−short の差
  "confidence": 78,                                  // 0〜100
  "agreement_with_machine": "partial",              // agree/partial/disagree
  "critical_zone": false,                            // サポレジ接触フラグ
  "support_zones": [                                 // support ゾーン配列 (強度降順 最大3件)
    { "low": 48250.0, "high": 48400.0, "strength": 5, "source": "4h" },
    { "low": 47100.0, "high": 47250.0, "strength": 3, "source": "1h" }
  ],
  "resistance_zones": [                              // resistance ゾーン配列 (強度降順 最大3件)
    { "low": 49500.0, "high": 49650.0, "strength": 4, "source": "4h" }
  ],
  "long_setup": {
    "status": "ready",                              // ready/watch/invalid
    "entry_zone": { "low": 48320.0, "high": 48380.0 },
    "entry_mid": 48350.0,                            // (low+high)/2
    "stop_loss": 48140.0,                            // price
    "tp1": 48670.0,                                  // price
    "tp2": 48990.0,                                  // price
    "rr_estimate": 2.1,                              // 目標RR
    "entry_to_stop_pct": 0.44,                       // ((entry_mid − stop_loss)/ATR14) 表示 %
    "entry_to_target_pct": 1.5,                     // ((tp1 − entry_mid)/ATR14) 表示 %
    "invalid_reason": ""                            // invalid 時の理由、valid なら空文字
  },
  "short_setup": {
    "status": "invalid",
    "entry_zone": { "low": 0.0, "high": 0.0 },     // invalid の場合 0
    "entry_mid": 0.0,
    "stop_loss": 0.0,
    "tp1": 0.0,
    "tp2": 0.0,
    "rr_estimate": 0.0,
    "entry_to_stop_pct": 0.0,
    "entry_to_target_pct": 0.0,
    "invalid_reason": "RR不足"
  },
  "primary_setup_side": "long",                     // long/short/none
  "primary_setup_status": "ready",                  // ready/watch/invalid/none
  "funding_rate": 0.0002,                             // 現在の Funding Rate (例: 0.0002=0.02%)
  "atr_ratio": 1.15,                                  // 現在 ATR 比 (現在 ATR / 直近平均)
  "volume_ratio": 1.3,                                // 現在 Volume Ratio
  "rr_estimate": 2.1,                                 // bias 方向の RR
  "ai_advice": {
    "decision": "LONG",                            // LONG/SHORT/WAIT/NO_TRADE (大文字)
    "quality": "B",                               // A/B/C
    "confidence": 0.74,                             // 0〜1 の浮動小数
    "notes": "上位足が強い uptrend で押し目完了。Funding Rate が中立。" // 簡潔な理由
  },
  "no_trade_flags": [],                               // 禁止条件・warning の配列
  "reason_for_notification": [ "status_upgraded", "confidence_jump" ], // 通知トリガー理由
  "summary_subject": "[BTC監視] 21:05 long / Confidence 78",        // メール件名
  "summary_body": "...メール本文..."                              // メール本文 (要約・定性文)
}
```

`ai_advice` が `null` の場合、メール本文には「AI 審査に失敗したため機械判定のみで通知します」と追記する。`no_trade_flags` には `RR_insufficient`, `ATR_extreme`, `Funding_prohibited`, `Critical_zone_warning` などを格納し、分析用に利用する。

---

## 8. プロンプト仕様

### 8-1. AI 審査プロンプト (`prompts/advice_prompt.md`)

プロンプトは AI を局面審査員として役割付けし、機械判定と定性コンテキストを基に `decision`, `quality`, `confidence`, `notes` の JSON を返させる。プロンプト内では以下を厳守する。

- 売買推奨ではなく局面評価であることを明示する。
- `decision` は `LONG` / `SHORT` / `WAIT` / `NO_TRADE` から 1 つ選択する。
- `quality` は A/B/C で、A は高品質・B は中間・C は低品質を示す。
- `confidence` は 0〜1 の実数で、0.0 は全く自信がなく 1.0 は非常に自信がある。
- `notes` は 1–2 文で簡潔に理由を述べ、日本語で返答させる。長文禁止。
- 返答は JSON のみとし余計な説明文を含めない。

### 8-2. 要約生成プロンプト (`prompts/summary_prompt.md`)

プロンプトは機械判定結果と `ai_advice` を入力とし、メール本文を日本語で生成させる。本文は以下のセクションで構成する。

1. **結論と信頼度** – bias、phase、confidence、AI 審査結果の要約。
2. **機械判定サマリー** – long/short スコア、score_gap、signals、market_regime、transition_direction の説明。
3. **指標および環境** – Funding Rate、ATR 比、Volume Ratio、重要サポレジ位置など客観指標。
4. **ロング / ショートセットアップ** – 各 setup.status、entry_zone、stop_loss、tp1/tp2、RR、理由。invalid の場合は理由を明記。
5. **AI 審査結果** – `ai_advice` の decision/quality/confidence/notes、および機械判定との一致状態。
6. **リスクコメント** – critical_zone や no_trade_flags、Warning 条件を説明し、見送り推奨箇所があれば強調する。

本文は客観的な文体とし、断定的な買い推奨は避ける。長さは 400〜700 文字を目安とし、見出しや箇条書きを使って読みやすさを確保する。

---

## 9. 実装順序

実装は以下の順序で行うことを推奨する。各ステップはユニットテストを含めて完了させてから次に進む。

1. ディレクトリとモジュールの雛形を作成し、`.env` の読み込みとバリデーション (`config.py`) を実装する。
2. データ取得 (`fetcher.py`) と検証 (`validator.py`) を実装し、MEXC API との通信を確認する。サーバー時刻誤差をログに記録できるようにする。
3. 指標計算モジュール (`indicators/`) を実装し、EMA/RSI/ATR/Volume Ratio の計算が正しいことを pandas の rolling 計算で検証する。
4. 構造判定、S/R 抽出・統合、レジーム判定、Phase 判定、スコアリング、Confidence 計算、RR 評価、禁止条件チェックを段階的に実装し、サンプルデータでユニットテストを行う。
5. AI 連携 (`ai/`) を実装し、OpenAI API から正しい形式の JSON を受け取れることを確認する。API エラー時のフォールバックも実装する。
6. 通知トリガー判定 (`notification/trigger.py`) とメール送信 (`email_sender.py`) を実装し、ダミー SMTP で送信テストを行う。
7. JSON 保存・CSV ログ (`storage/`) を実装し、各フィールドが正しく保存・読み込めることを確認する。古いログの削除を実装する。
8. バックテストフレームワーク (`backtest/`) を実装し、ヒストリカルデータでアルゴリズムを検証する。AI 審査の効果検証は最後に実施する。
9. summary_prompt と advice_prompt の内容を調整し、出力の品質を確認する。

---

## 10. テスト戦略

テストはユニットテスト、ドライランテスト、バックテストの 3 層で構成する。

### 10-1. ユニットテスト

- 指標計算 (EMA/RSI/ATR/Volume Ratio) が数値計算ライブラリの出力と一致するか。
- 構造判定 (HH/HL/LH/LL) と S/R 抽出が事前に用意したケースで正しいか。
- スコアリングの個別項目が期待通りの加点・減点を行うか。
- Confidence 計算で各項目のボーナス・ペナルティが正しく反映されるか。
- Phase 判定、禁止条件チェック、setup.status 判定が境界条件を含めて正しいか。
- JSON スキーマに対し欠落や型違いがないか。

### 10-2. ドライランテスト

ドライランでは Live API を利用しながらメール送信を行わず、判定結果とログ保存のみを行う。一定期間 (少なくとも 2 週間) 実行し、以下を確認する。

- 通知が過剰または不足していないか。
- bias 別に long/short/wait の発生比率が妥当か。
- confidence 帯別の勝率・敗率が期待と整合するか。
- AI 審査が `WAIT` や `NO_TRADE` を返す頻度が高すぎないか。
- エラー処理と再送ロジックが正常に機能するか。

### 10-3. バックテスト

バックテストではヒストリカルデータに対してアルゴリズムを適用し、以下の評価指標を取得する。

- bias 別勝率、平均 RR、confidence 帯別勝率。
- 見送り (WAIT/NO_TRADE) が損失回避にどれだけ貢献したか。
- 禁止条件の効果、phase 別期待値の違い。
- AI 一致状態 (agree/partial/disagree) と勝率の相関。
- 通知トリガーごとの有効性 (status_upgraded, bias_changed, confidence_jump 等)。

バックテストでパラメータを調整する場合は、変更履歴を文書化し本仕様書の更新履歴に追記する。

---

## 11. サンプル JSON

セクション [7. JSON スキーマ](#7-json-スキーマ) に示した JSON はサンプルとして完成形に近い。AI 審査がエラーになった場合のサンプルは以下のようになる。

```json
{
  "timestamp_utc": "2024-01-01T13:05:00Z",
  "timestamp_jst": "2024-01-01T22:05:00+09:00",
  ...,
  "ai_advice": null,
  "reason_for_notification": ["ai_error"],
  "summary_subject": "[BTC監視] 13:05 short / Confidence 71 ⚠️ AI審査:機械判定のみ",
  "summary_body": "AI 審査 API エラーのため機械判定のみで通知します。..."
}
```

---

## 12. 更新履歴

- **v1.1 (本書)**: 設計書 v4.0 と実装仕様書 v1.0 の不整合を解消。score 差分閾値をロング 10 点 / ショート 12 点に統一し【先行資料では 15/20 であった】、AI モデルを `gpt-4o-mini` と `gpt-4o` に分割しタイムアウトを 5 秒、リトライ回数を 3 回に変更【先行資料では 15 秒・2 回】。サーバー時刻誤差の許容値を ±2 秒に変更【先行資料では ±10 秒】。AI エラー時の `ai_advice` を `null` に統一しフォールバック JSON を廃止。バックテスト時の AI キャッシュ方針を初版は無効とし、代表サンプル検証時にのみ利用する方式とした。setup.status の判定条件を厳密化し、primary_setup の決定ロジックを bias 依存から左右比較に拡張。通知トリガーと抑制条件を明確化し、sample JSON を追加。
