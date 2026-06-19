"""スクリーンキャプチャモジュール"""

import gc
import os
import uuid
from pathlib import Path
from datetime import datetime

def get_tmp_dir() -> Path:
    """一時ファイル用ディレクトリを取得"""
    # macOS標準のApplication Supportディレクトリを使用
    tmp_dir = Path.home() / "Library" / "Application Support" / "ScreenLog" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def screenshot_file_path(tmp_dir: Path, timestamp: str | None = None) -> Path:
    """衝突しにくい一時スクリーンショットパスを作る。"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique = uuid.uuid4().hex[:12]
    return tmp_dir / f"screenshot_{timestamp}_{os.getpid()}_{unique}.png"


def cleanup_tmp_screenshots(
    *,
    max_age_seconds: int = 24 * 60 * 60,
    now: float | None = None,
) -> int:
    """古いScreenLog一時スクリーンショットを削除する。"""
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be greater than or equal to 0")

    tmp_dir = get_tmp_dir()
    current_time = now if now is not None else datetime.now().timestamp()
    deleted_count = 0
    for path in tmp_dir.glob("screenshot_*.png"):
        try:
            age_seconds = current_time - path.stat().st_mtime
            if age_seconds > max_age_seconds:
                path.unlink()
                deleted_count += 1
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"Failed to delete old screenshot: {e}")
    return deleted_count


def take_screenshot(window_id: int | None = None) -> str | None:
    """
    スクリーンショットを撮影し、一時ファイルのパスを返す

    Args:
        window_id: ウィンドウID。指定された場合はそのウィンドウのみをキャプチャ。
                   Noneの場合は画面全体をキャプチャ。

    Returns:
        str | None: 一時ファイルのパス。失敗した場合はNone
    """
    tmp_dir = get_tmp_dir()
    filepath = screenshot_file_path(tmp_dir)

    image = None
    bitmap = None
    png_data = None

    try:
        import objc
        import Quartz
        from AppKit import NSBitmapImageRep, NSPNGFileType

        # Autoreleaseプール内で実行してメモリリークを防ぐ
        with objc.autorelease_pool():
            # Quartz APIを使用してスクリーンキャプチャ
            if window_id is not None:
                # 特定ウィンドウをキャプチャ
                image = Quartz.CGWindowListCreateImage(
                    Quartz.CGRectNull,  # ウィンドウの境界を自動取得
                    Quartz.kCGWindowListOptionIncludingWindow,
                    window_id,
                    Quartz.kCGWindowImageDefault
                )

                # ウィンドウキャプチャが失敗した場合、フルスクリーンにフォールバック
                if image is None:
                    image = Quartz.CGWindowListCreateImage(
                        Quartz.CGRectInfinite,
                        Quartz.kCGWindowListOptionOnScreenOnly,
                        Quartz.kCGNullWindowID,
                        Quartz.kCGWindowImageDefault
                    )
            else:
                # 画面全体をキャプチャ
                image = Quartz.CGWindowListCreateImage(
                    Quartz.CGRectInfinite,
                    Quartz.kCGWindowListOptionOnScreenOnly,
                    Quartz.kCGNullWindowID,
                    Quartz.kCGWindowImageDefault
                )

            if image is None:
                print("Failed to capture screen image")
                return None

            # CGImageをPNGファイルに保存
            bitmap = NSBitmapImageRep.alloc().initWithCGImage_(image)
            if bitmap is None:
                print("Failed to create bitmap from image")
                return None

            png_data = bitmap.representationUsingType_properties_(NSPNGFileType, None)
            if png_data is None:
                print("Failed to create PNG data")
                return None

            png_data.writeToFile_atomically_(str(filepath), True)

            if not filepath.exists():
                print("Screenshot file was not created")
                return None

            return str(filepath)

    except Exception as e:
        print(f"Screenshot capture error: {e}")
        return None

    finally:
        # Autoreleaseプールがオブジェクトを解放するため、
        # Python参照のクリアとGCのみ実行
        image = None
        bitmap = None
        png_data = None
        gc.collect()


def delete_screenshot(filepath: str) -> bool:
    """
    一時スクリーンショットファイルを削除

    Args:
        filepath: 削除するファイルのパス

    Returns:
        bool: 削除成功した場合True
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        print(f"Failed to delete screenshot: {e}")
        return False
