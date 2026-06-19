# ScreenLog

macOS上で動作する作業ログ自動生成ツール。スクリーンショットを定期的に取得し、ローカルOCRでテキスト化して保存する。

## 特徴

- **完全ローカル処理**: スクリーンショット・OCR処理はすべてローカルで完結（外部APIを使わない）
- **自動記録**: 設定可能な間隔（デフォルト5分）でバックグラウンド動作
- **診断可能な記録**: 空OCR・画面収録権限不足・メニューバーのみの疑いもログに残す
- **日本語・英語対応**: macOS Vision Frameworkによる高精度OCR
- **AI連携前提**: 蓄積されたログをAIに渡して作業時間をまとめられる

## 必要条件

- macOS 12.0以降
- Python 3.10以降
- 画面収録権限（Screen Recording）
- アクセシビリティ権限（Accessibility）

## インストール

```bash
# リポジトリをクローン
cd /path/to/screenlog

# 仮想環境を作成（推奨）
python3 -m venv venv
source venv/bin/activate

# 依存ライブラリをインストール
pip install -r requirements.txt
```

## 使い方

### 起動

常用は Mac アプリ版に寄せる。画面収録権限は `Terminal` や `python` と `ScreenLog.app` で別扱いになるため、常用入口を混ぜない。

```bash
open /Applications/ScreenLog.app
```

CLI は開発・診断用として使う。

```bash
# 起動スクリプトを使用（デフォルト: 5分間隔）
./scripts/start-background.sh

# キャプチャ間隔を指定して起動（秒単位）
./scripts/start-background.sh --interval 60    # 1分間隔
./scripts/start-background.sh --interval 300   # 5分間隔
./scripts/start-background.sh --interval 600   # 10分間隔

# または直接実行
python -m screenlog.main

# キャプチャ間隔を指定（秒）
python -m screenlog.main -i 60

# 同じ画面が続く場合も5分ごとにログを分割保存
python -m screenlog.main -i 60 --flush-interval 300

# 1回だけキャプチャして終了
python -m screenlog.main --once

# ウィンドウ判定・権限・直近ログを診断
python -m screenlog.doctor

# 設定をファイルに保存（次回以降のデフォルトになる）
python -m screenlog.main -i 60 --flush-interval 300 --save-config
```

### 停止

`Ctrl+C` で停止。

### ログの確認

ログは `~/Library/Application Support/ScreenLog/logs/` に日付別のJSONLファイルとして保存される。

```bash
# 今日のログを確認
cat ~/Library/Application\ Support/ScreenLog/logs/$(date +%Y-%m-%d).jsonl

# 整形して表示
cat ~/Library/Application\ Support/ScreenLog/logs/$(date +%Y-%m-%d).jsonl | jq .
```

## ログ形式

各エントリはJSON形式で1行ずつ保存される。

```json
{
  "schema_version": 2,
  "start_time": "2026-05-12T11:01:06+09:00",
  "end_time": "2026-05-12T11:01:06+09:00",
  "duration_minutes": 1,
  "snapshot_count": 1,
  "active_app": "Visual Studio Code",
  "window_title": "main.py - MyProject",
  "focused_app": "tldv",
  "focused_title": "Floating recorder",
  "working_app": "Visual Studio Code",
  "working_title": "main.py - MyProject",
  "capture_mode": "working_window",
  "selection_reason": "first_non_excluded_visible_window",
  "capture_status": "ok",
  "capture_error": null,
  "ocr_length": 56,
  "is_suspicious": false,
  "screen_recording_allowed": true,
  "ocr_text": "def process_screenshot():\n    # スクリーンショットを処理する...",
  "avg_ocr_confidence": 0.85,
  "top_windows": []
}
```

`active_app` / `window_title` は後方互換のため残しているが、v2では実作業の判定には `working_app` / `working_title` を使う。`focused_app` はmacOSが前面とみなしたアプリで、tldvなどの補助アプリが入る場合がある。

`capture_status` は `ok` / `empty_ocr` / `suspicious_menu_only` / `screen_permission_denied` / `capture_failed` のいずれか。空OCRも診断目的で保存する。

## AIによる作業まとめ

ログファイルをAI（Claude等）に直接渡す代わりに、まずLLM向けMarkdownへ整形する：

```bash
python -m screenlog.summarize
python -m screenlog.summarize -d 2026-05-12 -n 3
```

毎日確認するための日次サマリーを `~/daily-notes/JOURNAL/Daily/` に保存する：

```bash
python -m screenlog.summarize --daily-note
python -m screenlog.summarize -d 2026-05-12 --daily-note
```

日次サマリーには、推定プロジェクト、時間帯別の作業、怪しい判定、確認メモが含まれる。ログ品質のズレに気づいたらIssueや改善メモにする。

出力をAIに渡して、以下のようなプロンプトで要約させる：

```
以下は今日の作業ログです。JSONLファイルの各行がスクリーンショットから取得した情報です。
これを読み取って、何時から何時に何をしていたかを時系列でまとめてください。
細かいエントリは適宜集約し、作業の切り替わりがわかるようにしてください。

---
[JSONLファイルの内容をここに貼り付け]
```

### 診断

アプリ名がtldvやloginwindowに偏る、ウィンドウタイトルがUnknownになる、ログ更新が止まっている場合は以下を実行する：

```bash
python -m screenlog.doctor
python -m screenlog.doctor --json
```

`focused` はOS上の前面アプリ、`working` はScreenLogが実作業と判断したアプリを表す。両者がズレる場合でも、`working` が実作業に近ければ正常。

`health_status` が `screen_permission_denied` の場合は画面収録権限を確認する。`stale_log` の場合は常駐プロセス、flush interval、直近の `capture_status` を確認する。

## 権限設定

初回実行時に以下の権限を求められる：

1. **画面収録（Screen Recording）**
   - システム設定 > プライバシーとセキュリティ > 画面収録
   - 常用する `ScreenLog.app` を許可
   - 権限変更後は `ScreenLog.app` を再起動する

2. **アクセシビリティ（Accessibility）**
   - システム設定 > プライバシーとセキュリティ > アクセシビリティ
   - 常用する `ScreenLog.app` を許可

Macアプリを再ビルドして置き換える場合は、同じBundle IDと安定したコード署名を維持する。ad-hoc署名のまま頻繁に置き換えると、macOSの権限紐付けが不安定になりやすい。

## ファイル構成

```
~/Library/Application Support/ScreenLog/
├── logs/
│   ├── 2024-12-21.jsonl
│   ├── 2024-12-22.jsonl
│   └── 2024-12-23.jsonl
├── tmp/                      # 一時ファイル（自動削除）
└── config.json               # interval / retention_days / flush_interval
```

## ライセンス

MIT License
