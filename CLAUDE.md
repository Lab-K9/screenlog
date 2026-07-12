# ScreenLog

macOS作業ログ自動生成ツール。1分間隔でスクリーンショット取得、ローカルOCR（Vision Framework）でテキスト化し、jsonlファイルに記録する。

## 技術スタック

- Python 3.13 + venv
- macOS Vision Framework（OCR）
- PyObjC（objc, Quartz, Vision, Foundation, AppKit, CoreFoundation, ApplicationServices）
- rumps（メニューバーアプリ）
- py2app（.appバンドル生成）

## ビルド & デプロイ

### ビルド手順

```bash
./scripts/build-app.sh
```

個人利用の常用配置:

```bash
./scripts/install-local-app.sh
```

標準の配置先は `~/Applications/ScreenLog.app`。`ScreenLog Local Developer ID` がKeychainにある場合は自動で使い、同じBundle IDとローカル署名で更新する。

署名IDがある場合:

```bash
SCREENLOG_CODESIGN_IDENTITY="<codesign identity>" ./scripts/build-app.sh
```

本番運用向けにApple Team IDまで検証する場合:

```bash
SCREENLOG_CODESIGN_IDENTITY="<Apple Developer ID identity>" SCREENLOG_REQUIRE_TEAM_ID=1 ./scripts/build-app.sh
SCREENLOG_CODESIGN_IDENTITY="<Apple Developer ID identity>" SCREENLOG_EXPECTED_TEAM_ID="<Team ID>" ./scripts/build-app.sh
```

### ビルド時の PyObjCTools 同梱

`PyObjCTools` は namespace package（`__init__.py` がない）のため、`scripts/build-app.sh` がビルド後に app bundle へコピーして `__init__.py` を作成する。スクリプトは codesign 検証と PyObjC import 検証も実行する。

### ビルド後の検証

アプリ起動前に、PyObjCのimportが正しく動作するか必ず確認する:

```bash
PYTHONPATH="dist/ScreenLog.app/Contents/Resources/lib/python3.13:dist/ScreenLog.app/Contents/Resources/lib/python3.13/lib-dynload" \
dist/ScreenLog.app/Contents/MacOS/python -c "
import objc; print('objc OK')
import Vision; print('Vision OK')
import Quartz; print('Quartz OK')
import ApplicationServices; print('ApplicationServices OK')
from Foundation import NSURL; print('Foundation OK')
from AppKit import NSWorkspace; print('AppKit OK')
"
```

全て OK と出ることを確認してからアプリを起動する。

### 起動

```bash
open ~/Applications/ScreenLog.app
```

ログイン時に自動起動する場合:

```bash
./scripts/install-launch-agent.sh
./scripts/uninstall-launch-agent.sh
```

### 稼働監視（watchdog）

launch agent は `RunAtLoad` のみで `KeepAlive` が無いため、アプリが落ちると次回ログインまで復帰しない（2026-06-30〜07-08 に7日間ログ欠損した実害、Issue #13）。watchdog（`com.labk9.screenlog-watchdog`）が30分おきに死活監視し、停止していれば自動再起動して macOS 通知する。ログ鮮度（本日分 jsonl が30分以上未更新）も検知する。

```bash
./scripts/install-watchdog.sh
./scripts/uninstall-watchdog.sh
```

- watchdog 動作ログ: `~/Library/Logs/ScreenLog.watchdog.log`
- 再起動失敗時は exit 1 で終了し、`corporateos-doctor.sh` チェック1（com.labk9.* 非ゼロ終了）が検知する
- `corporateos-doctor.sh` チェック13はプロセス死活・ログ鮮度・watchdog ロード状態まで確認する

### 既知の注意点

- **setup.py の `packages` リストに PyObjC 関連パッケージを含めること。** py2app の `includes` だけでは `.so` ファイルしかコピーされず、Python ファイル（`__init__.py` 等）が欠落して `import objc` が失敗する。
- 新しい PyObjC フレームワーク（例: CoreBluetooth）を使う場合は、`setup.py` の `packages` にも追加すること。
- Python バージョンを更新した場合、手動コピーのパス（`python3.13` 部分）も合わせて更新すること。

## データ

- ログ保存先: `~/Library/Application Support/ScreenLog/logs/YYYY-MM-DD.jsonl`
- 一時スクリーンショット: `~/Library/Application Support/ScreenLog/tmp/`（処理後に自動削除）
- ログ保持期間: 30日（起動時に古いログを自動削除）
- 推定ルール: `~/Library/Application Support/ScreenLog/summary-rules.json`
- 診断: `venv/bin/python -m screenlog.doctor`
- v2ログでは `focused_app`（OS上の前面）と `working_app`（ScreenLogが作業実体と判断）を分離する。サマリーや分析では `working_app` を優先する。
