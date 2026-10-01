"""作業画面の画像保存モジュール（縮小JPEG・差分判定・保持期間）"""

import shutil
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .config import validate_image_retention_days

# 原寸幅がこれ以下なら縮小しない（非Retina外部モニタ等）。超えたら横幅を半分にする。
DOWNSCALE_MIN_WIDTH = 1600
DOWNSCALE_RATIO = 0.5
JPEG_QUALITY = 0.7
# 差分判定用サムネイルの一辺（グレースケール）
THUMBNAIL_SIZE = 32
# サムネイルの平均絶対差（0〜255）がこの値未満なら「ほぼ同じ画面」として保存しない
IMAGE_DIFF_THRESHOLD = 2.0

Encoder = Callable[[str, Path], Any]
Thumbnailer = Callable[[str], bytes | None]


def get_images_dir() -> Path:
    """画像保存先ルート（作成はしない）。"""
    return Path.home() / "Library" / "Application Support" / "ScreenLog" / "images"


def _load_cg_image(path: str):
    import Quartz
    from Foundation import NSURL

    source = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(str(path)), None)
    if source is None:
        raise OSError(f"Cannot open image: {path}")
    return source


def encode_downscaled_jpeg(src_path: str, dest_path: Path) -> tuple[int, int]:
    """PNGを横幅半分（幅<=DOWNSCALE_MIN_WIDTHなら原寸）のJPEGにして保存する。

    戻り値は保存した画像の (幅, 高さ)。
    """
    import objc
    import Quartz
    from Foundation import NSURL

    with objc.autorelease_pool():
        source = _load_cg_image(src_path)
        props = Quartz.CGImageSourceCopyPropertiesAtIndex(source, 0, None)
        width = int(props["PixelWidth"])
        height = int(props["PixelHeight"])

        if width > DOWNSCALE_MIN_WIDTH:
            max_pixel = int(round(max(width, height) * DOWNSCALE_RATIO))
            options = {
                Quartz.kCGImageSourceCreateThumbnailFromImageAlways: True,
                Quartz.kCGImageSourceCreateThumbnailWithTransform: True,
                Quartz.kCGImageSourceThumbnailMaxPixelSize: max_pixel,
            }
            image = Quartz.CGImageSourceCreateThumbnailAtIndex(source, 0, options)
        else:
            image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
        if image is None:
            raise OSError(f"Cannot decode image: {src_path}")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        url = NSURL.fileURLWithPath_(str(dest_path))
        dest = Quartz.CGImageDestinationCreateWithURL(url, "public.jpeg", 1, None)
        if dest is None:
            raise OSError(f"Cannot create JPEG destination: {dest_path}")
        Quartz.CGImageDestinationAddImage(
            dest, image, {Quartz.kCGImageDestinationLossyCompressionQuality: JPEG_QUALITY}
        )
        if not Quartz.CGImageDestinationFinalize(dest):
            raise OSError(f"Cannot write JPEG: {dest_path}")
        return (Quartz.CGImageGetWidth(image), Quartz.CGImageGetHeight(image))


def gray_thumbnail(src_path: str) -> bytes | None:
    """差分判定用に THUMBNAIL_SIZE 四方のグレースケール画素列を返す。"""
    import objc
    import Quartz

    with objc.autorelease_pool():
        source = _load_cg_image(src_path)
        image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
        if image is None:
            return None
        size = THUMBNAIL_SIZE
        buffer = bytearray(size * size)
        gray = Quartz.CGColorSpaceCreateDeviceGray()
        ctx = Quartz.CGBitmapContextCreate(
            buffer, size, size, 8, size, gray, Quartz.kCGImageAlphaNone
        )
        if ctx is None:
            return None
        Quartz.CGContextSetInterpolationQuality(ctx, Quartz.kCGInterpolationMedium)
        Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, size, size), image)
        return bytes(buffer)


def frames_similar(
    previous: bytes | None,
    current: bytes | None,
    threshold: float = IMAGE_DIFF_THRESHOLD,
) -> bool:
    """2枚のサムネイルの平均絶対差が閾値未満ならほぼ同じ画面とみなす。"""
    if previous is None or current is None or len(previous) != len(current) or not current:
        return False
    total = sum(abs(a - b) for a, b in zip(previous, current))
    return total / len(current) < threshold


class ImageStore:
    """OCR済みスクリーンショットを縮小JPEGとして日付フォルダに保存する。

    直前に保存した画像とほぼ同じ画面なら保存せず、その画像のパスを返す。
    失敗しても例外は投げず None を返す（撮影・OCRのループを止めない）。
    """

    def __init__(
        self,
        images_dir: Path | None = None,
        *,
        encoder: Encoder = encode_downscaled_jpeg,
        thumbnailer: Thumbnailer = gray_thumbnail,
    ) -> None:
        self.images_dir = images_dir if images_dir is not None else get_images_dir()
        self._encoder = encoder
        self._thumbnailer = thumbnailer
        self._last_thumbnail: bytes | None = None
        self.last_path: str | None = None
        self._lock = threading.Lock()

    def _destination(self, timestamp: datetime) -> Path:
        day_dir = self.images_dir / timestamp.strftime("%Y-%m-%d")
        base = timestamp.strftime("%H%M%S")
        candidate = day_dir / f"{base}.jpg"
        counter = 1
        while candidate.exists():
            candidate = day_dir / f"{base}_{counter}.jpg"
            counter += 1
        return candidate

    def save(self, src_path: str, timestamp: datetime) -> str | None:
        """保存した（または直前と同一画面の）画像の絶対パスを返す。失敗時はNone。"""
        with self._lock:
            try:
                thumbnail = self._thumbnailer(src_path)
                if (
                    self.last_path is not None
                    and Path(self.last_path).exists()
                    and frames_similar(self._last_thumbnail, thumbnail)
                ):
                    return self.last_path

                dest = self._destination(timestamp)
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    self._encoder(src_path, dest)
                except BaseException:
                    dest.unlink(missing_ok=True)
                    raise
                self._last_thumbnail = thumbnail
                self.last_path = str(dest)
                return self.last_path
            except Exception as e:
                print(f"Failed to save screenshot image: {e}")
                return None


def cleanup_old_images(
    retention_days: int,
    *,
    images_dir: Path | None = None,
    today: date | None = None,
) -> int:
    """保持期間より古い日付フォルダ（YYYY-MM-DD）だけを削除する。削除数を返す。"""
    retention_days = validate_image_retention_days(retention_days)
    root = images_dir if images_dir is not None else get_images_dir()
    if not root.is_dir():
        return 0
    cutoff = (today or date.today()) - timedelta(days=retention_days)
    deleted = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            folder_date = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date < cutoff:
            try:
                shutil.rmtree(child)
                print(f"Deleted old images: {child.name}")
                deleted += 1
            except Exception as e:
                print(f"Failed to delete images {child}: {e}")
    return deleted


def image_usage(images_dir: Path | None = None) -> dict[str, Any]:
    """画像フォルダの合計容量・ファイル数・最古の日付を返す。"""
    root = images_dir if images_dir is not None else get_images_dir()
    total = 0
    count = 0
    oldest: str | None = None
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir():
                continue
            try:
                datetime.strptime(child.name, "%Y-%m-%d")
            except ValueError:
                continue
            for f in child.rglob("*"):
                try:
                    if f.is_file():
                        total += f.stat().st_size
                        count += 1
                except OSError:
                    continue
            if oldest is None or child.name < oldest:
                oldest = child.name
    return {
        "path": str(root),
        "total_bytes": total,
        "file_count": count,
        "oldest_date": oldest,
    }
