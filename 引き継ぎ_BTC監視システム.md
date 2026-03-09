# BTC半自動トレード補佐システム 引き継ぎドキュメント

作成日: 2026-03-09

---

## 1. プロジェクト概要

MEXC取引所のBTCUSDT無期限先物を対象とした**半自動トレード補佐システム**。
4H/1H/15mのマルチタイムフレーム分析で機械的スコアリングを行い、OpenAI（gpt-4o）によるAI審査を経て、メールで売買シグナルを通知する。

---

## 2. ファイルの場所

```
選択フォルダ内の BTC_FX/btc_monitor/
```

### ディレクトリ構成

```
btc_monitor/
├── main.py                  # メインエントリーポイント・スケジューラー
├── config.py                # 環境変数ローダー
├── requirements.txt         # 依存パッケージ
├── .env                     # 認証情報（実設定済み）
├── .env.example             # テンプレート
├── README.md
├── NEXT_TASK.md
├── prompts/
│   ├── advice_prompt.md     # gpt-4o 用システムプロンプト
│   └── summary_prompt.md    # gpt-4o-mini 用システムプロンプト
├── src/
│   ├── data/
│   │   ├── fetcher.py       # MEXC APIデータ取得
│   │   └── validator.py     # データバリデーション
│   ├── indicators/
│   │   ├── ema.py           # EMA20/50/200
│   │   ├── rsi.py           # RSI14
│   │   ├── atr.py           # ATR14
│   │   └── volume.py        # ボリューム比率
│   ├── analysis/
│   │   ├── structure.py     # スイング高安・HH/HL/LH/LL
│   │   ├── support_resistance.py  # S/Rゾーン
│   │   ├── regime.py        # 市場レジーム判定
│   │   ├── scoring.py       # スコアリング・バイアス判定
│   │   ├── phase.py         # フェーズ分類
│   │   ├── confidence.py    # コンフィデンス計算
│   │   ├── rr.py            # エントリー・SL・TP計算
│   │   └── qualitative.py   # 定性的分析
│   ├── ai/
│   │   ├── advice.py        # gpt-4o AI審査
│   │   └── summary.py       # gpt-4o-mini メール本文生成
│   ├── notification/
│   │   ├── trigger.py       # 通知トリガー判定
│   │   └── email_sender.py  # SMTP送信
│   └── storage/
│       ├── json_store.py    # シグナルJSON保存
│       ├── csv_logger.py    # CSV履歴記録
│       └── cleanup.py       # 古いログ削除
├── backtest/
│   ├── runner.py            # バックテスト実行
│   └── evaluator.py         # 結果評価
└── logs/                    # 実行ログ（自動生成）
    ├── signals/             # シグナルJSON（90日保持）
    ├── notifications/       # 通知履歴（180日保持）
    ├── errors/              # エラーログ（180日保持）
    ├── signals_history.csv  # 累積CSV
    ├── heartbeat.txt        # 最終実行時刻
    ├── last_result.json     # 前回結果（通知差分用）
    └── last_notified.json   # 前回通知時刻（クールダウン用）
```

---

## 3. 現在の設定（.env）

| 項目 | 値 |
|------|-----|
| MEXC_SYMBOL | BTC_USDT |
| OPENAI_ADVICE_MODEL | gpt-4o |
| OPENAI_SUMMARY_MODEL | gpt-4o-mini |
| SMTP_HOST | sv16037.xserver.jp |
| SMTP_PORT | 587 |
| SMTP_USER / MAIL_FROM | btc@afrog.jp |
| MAIL_TO | info@afrog.jp |
| TIMEZONE | Asia/Tokyo |
| REPORT_TIMES | 09:05,13:05,17:05,21:05,01:05,05:05 |
| DRYRUN_MODE | false |
| AI_TIMEOUT_SEC | 30 |
| ALERT_COOLDOWN_MINUTES | 60 |

> ⚠️ APIキー・SMTPパスワードは `.env` に直接記述済み。新スレッドで確認する場合は `.env` を直接参照のこと。

---

## 4. インストール済み状態

```bash
# 依存パッケージは導入済み
pip install -r requirements.txt  # 実施済み

# 動作確認済み
- MEXC APIからのデータ取得 ✅
- 指標計算・スコアリング ✅
- AI審査（gpt-4o） ✅
- SMTP メール送信（Xserver） ✅
- ドライラン → 本番モード切替 ✅
```

---

## 5. 既知のバグ修正済み事項

### ① MEXC 1H インターバルエラー
- **問題**: `INTERVAL_MAP["1h"] = "Hour1"` → APIがエラーコード600を返す
- **修正**: `src/data/fetcher.py` の INTERVAL_MAP を以下に変更済み
  ```python
  INTERVAL_MAP = {
      "4h": "Hour4",
      "1h": "Min60",   # ← ここが修正箇所（Hour1はMEXCで無効）
      "15m": "Min15",
  }
  ```

### ② AI タイムアウト
- **問題**: `AI_TIMEOUT_SEC=5` だと OpenAI API がタイムアウト
- **修正**: `.env` で `AI_TIMEOUT_SEC=30` に変更済み

---

## 6. 直近の実行結果（参考）

最終実行: 2026-03-09 18:39 JST（テスト実行）

```
bias           : short
confidence     : 75
market_regime  : downtrend
primary_setup  : short / invalid
AI審査         : NO_TRADE / 品質C / critical zone警告
通知           : 送信済み（info@afrog.jp宛）
通知理由       : bias_changed, confidence_jump
```

---

## 7. 起動方法

### ⚠️ 現在の状態
**システムは停止中**。前回はCoworkセッション内でテスト実行しただけで、常時起動スクリプトは未登録。

### Mac ターミナルで起動する場合

```bash
# btc_monitorディレクトリに移動
cd /path/to/BTC_FX/btc_monitor

# バックグラウンドで起動（ターミナルを閉じても動作継続）
nohup python3 main.py > logs/stdout.log 2>&1 &
echo $! > logs/main.pid

# 停止する場合
kill $(cat logs/main.pid)

# ログ確認
tail -f logs/stdout.log
```

### VPS/サーバーで運用する場合（推奨）

systemdサービスとして登録することで自動再起動・永続稼働が可能。
詳細は前スレッドの「本番起動ガイド」を参照。

---

## 8. 次スレッドへのリクエスト候補

以下のタスクが残っている（必要に応じて依頼すること）：

- [ ] **Macでの自動起動設定**（launchd plist登録）
- [ ] **バックテスト実行**（`backtest/runner.py` の動作確認）
- [ ] **ログ監視ツール追加**（異常検知・アラート）
- [ ] **Webダッシュボード**（シグナル履歴の可視化）
- [ ] **VPSへのデプロイ**（24時間安定稼働）
- [ ] **パラメータ調整**（スコアリング閾値のチューニング）

---

## 9. 新スレッドへの申し送り事項

1. **コードは完成・動作確認済み**。新規実装は不要。
2. **起動するだけで動く**。`python3 main.py` を実行すれば定刻にメールが届く。
3. **.env は設定済み**。APIキー等の再入力は不要（ファイルを確認するだけでOK）。
4. **MEXC認証不要**。パブリックAPIを使用しているため、APIキー登録なしでデータ取得できる。
5. **DRYRUN_MODE=false**。本番モードで動作する。テスト時は `true` に変更すること。

---

_このドキュメントはCoworkセッション引き継ぎ用に自動生成されました。_
