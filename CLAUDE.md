# ScreenLog

macOS作業ログ自動生成ツール。1分間隔でスクリーンショット取得、ローカルOCR（Vision Framework）でテキスト化し、jsonlファイルに記録する。

## 技術スタック

- Python 3.13 + venv
- macOS Vision Framework（OCR）
- PyObjC（objc, Quartz, Vision, Foundation, AppKit, CoreFoundation）
- rumps（メニューバーアプリ）
- py2app（.appバンドル生成）

## ビルド & デプロイ

### ビルド手順

```bash
source venv/bin/activate
rm -rf build dist
python setup.py py2app
```

### ビルド後の必須手順: PyObjCTools の手動コピー

`PyObjCTools` は namespace package（`__init__.py` がない）のため、py2app が自動でバンドルに含められない。**ビルドのたびに手動コピーが必要。**

```bash
TARGET="dist/ScreenLog.app/Contents/Resources/lib/python3.13/PyObjCTools"
SOURCE="venv/lib/python3.13/site-packages/PyObjCTools"
mkdir -p "$TARGET"
cp "$SOURCE"/*.py "$TARGET/"
touch "$TARGET/__init__.py"
```

### ビルド後の検証

アプリ起動前に、PyObjCのimportが正しく動作するか必ず確認する:

```bash
PYTHONPATH="dist/ScreenLog.app/Contents/Resources/lib/python3.13:dist/ScreenLog.app/Contents/Resources/lib/python3.13/lib-dynload" \
dist/ScreenLog.app/Contents/MacOS/python -c "
import objc; print('objc OK')
import Vision; print('Vision OK')
import Quartz; print('Quartz OK')
from Foundation import NSURL; print('Foundation OK')
from AppKit import NSWorkspace; print('AppKit OK')
"
```

全て OK と出ることを確認してからアプリを起動する。

### 起動

```bash
open dist/ScreenLog.app
```

### 既知の注意点

- **setup.py の `packages` リストに PyObjC 関連パッケージを含めること。** py2app の `includes` だけでは `.so` ファイルしかコピーされず、Python ファイル（`__init__.py` 等）が欠落して `import objc` が失敗する。
- 新しい PyObjC フレームワーク（例: CoreBluetooth）を使う場合は、`setup.py` の `packages` にも追加すること。
- Python バージョンを更新した場合、手動コピーのパス（`python3.13` 部分）も合わせて更新すること。

## データ

- ログ保存先: `~/Library/Application Support/ScreenLog/logs/YYYY-MM-DD.jsonl`
- 一時スクリーンショット: `~/Library/Application Support/ScreenLog/tmp/`（処理後に自動削除）
- ログ保持期間: 30日（起動時に古いログを自動削除）
