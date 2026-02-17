#!/usr/bin/env python3
"""ScreenLog - py2app エントリポイント"""

import atexit
import sys
import os

# ファイルハンドルを保持（クローズ用）
_stdout_file = None
_stderr_file = None


def _cleanup_file_handles():
    """アプリ終了時にファイルハンドルをクローズ"""
    global _stdout_file, _stderr_file
    try:
        if _stdout_file is not None and not _stdout_file.closed:
            _stdout_file.flush()
            _stdout_file.close()
        if _stderr_file is not None and not _stderr_file.closed:
            _stderr_file.flush()
            _stderr_file.close()
    except Exception:
        pass  # 終了時のエラーは無視


# アプリバンドル内のリソースパスを設定
if getattr(sys, 'frozen', False):
    # py2appでビルドされたアプリとして実行されている場合
    app_dir = os.path.dirname(sys.executable)
    # ログ出力先を設定
    log_dir = os.path.expanduser('~/ScreenLog')
    os.makedirs(log_dir, exist_ok=True)

    # stdout/stderrをファイルにリダイレクト（UTF-8エンコーディングを指定）
    _stdout_file = open(os.path.join(log_dir, 'screenlog.log'), 'a', buffering=1, encoding='utf-8')
    _stderr_file = open(os.path.join(log_dir, 'screenlog.error.log'), 'a', buffering=1, encoding='utf-8')
    sys.stdout = _stdout_file
    sys.stderr = _stderr_file

    # 終了時にファイルハンドルをクローズするように登録
    atexit.register(_cleanup_file_handles)

from screenlog.menubar_app import main

if __name__ == "__main__":
    main()
