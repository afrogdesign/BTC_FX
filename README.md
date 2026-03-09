# BTC_FX

このリポジトリは、BTC の半自動トレード補佐システムを管理するプロジェクトです。

実装本体は [`btc_monitor/`](./btc_monitor) にあります。  
ルートには、プロジェクト全体の入口になる資料を置いています。

## 主な中身

- `btc_monitor/`
  BTC 監視・判定・通知の本体コードです。
- `BTC半自動トレード補佐システム_CODEX実装仕様書_完全版_v1.1.md`
  システムの仕様書です。

## まず見る場所

1. [`btc_monitor/README.md`](./btc_monitor/README.md)
   セットアップ方法、起動方法、構成の説明があります。
2. [`btc_monitor/main.py`](./btc_monitor/main.py)
   実行の入口です。
3. [`btc_monitor/NEXT_TASK.md`](./btc_monitor/NEXT_TASK.md)
   今後の作業メモです。

## 補足

このシステムは「売買判断を補佐する」ためのもので、自動発注そのものは行いません。  
実際の投資判断は自己責任で行ってください。
