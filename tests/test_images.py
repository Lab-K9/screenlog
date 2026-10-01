import json
import os
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import Quartz
from Foundation import NSURL

from screenlog import images as images_mod
from screenlog.config import DEFAULT_IMAGE_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
from screenlog.doctor import build_doctor_report
from screenlog.images import (
    IMAGE_DIFF_THRESHOLD,
    ImageStore,
    cleanup_old_images,
    image_usage,
)
from screenlog.logger import cleanup_old_logs
from screenlog.ocr import OCRResult
from screenlog.recorder import process_capture
from screenlog.runtime import load_runtime_settings


def make_png(path: Path, width: int, height: int, *, shade: int = 0) -> Path:
    """テスト用に、縞模様のPNGをQuartzで作る。shadeで中身を変えられる。"""
    cs = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(
        None, width, height, 8, 0, cs, Quartz.kCGImageAlphaPremultipliedLast
    )
    for i in range(0, width, 50):
        value = ((i // 50 * 40) + shade) % 256 / 255.0
        Quartz.CGContextSetRGBFillColor(ctx, value, 1 - value, 0.5, 1)
        Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(i, 0, 50, height))
    image = Quartz.CGBitmapContextCreateImage(ctx)
    url = NSURL.fileURLWithPath_(str(path))
    dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(dest, image, None)
    assert Quartz.CGImageDestinationFinalize(dest)
    return path


def image_size(path: Path) -> tuple[int, int]:
    src = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(str(path)), None)
    props = Quartz.CGImageSourceCopyPropertiesAtIndex(src, 0, None)
    return int(props["PixelWidth"]), int(props["PixelHeight"])


TS = datetime.fromisoformat("2026-10-01T10:00:00+09:00")


def stub_encoder(src, dest):
    Path(dest).write_bytes(b"jpeg")
    return (10, 10)


class ImageSaveTests(unittest.TestCase):
    def test_image_saved_downscaled_half_width(self):
        with TemporaryDirectory() as tmp:
            src = make_png(Path(tmp) / "src.png", 3024, 1964)
            store = ImageStore(Path(tmp) / "images")
            saved = store.save(str(src), TS)

            self.assertIsNotNone(saved)
            saved_path = Path(saved)
            self.assertTrue(saved_path.is_absolute())
            self.assertEqual(saved_path.parent.name, "2026-10-01")
            self.assertEqual(saved_path.suffix, ".jpg")
            width, height = image_size(saved_path)
            self.assertEqual(width, 1512)
            self.assertAlmostEqual(height, 982, delta=2)

    def test_small_image_not_downscaled(self):
        with TemporaryDirectory() as tmp:
            src = make_png(Path(tmp) / "src.png", 1600, 900)
            store = ImageStore(Path(tmp) / "images")
            saved = store.save(str(src), TS)

            self.assertEqual(image_size(Path(saved)), (1600, 900))

    def test_similar_frame_not_saved(self):
        with TemporaryDirectory() as tmp:
            src = make_png(Path(tmp) / "src.png", 800, 600)
            store = ImageStore(Path(tmp) / "images")
            first = store.save(str(src), TS)
            second = store.save(str(src), TS.replace(minute=1))

            self.assertIsNotNone(first)
            # 未保存のときは直前に保存した同一画面の画像パスを返す
            self.assertEqual(second, first)
            self.assertEqual(len(list((Path(tmp) / "images").rglob("*.jpg"))), 1)

    def test_changed_frame_saved(self):
        with TemporaryDirectory() as tmp:
            a = make_png(Path(tmp) / "a.png", 800, 600, shade=0)
            b = make_png(Path(tmp) / "b.png", 800, 600, shade=120)
            store = ImageStore(Path(tmp) / "images")
            first = store.save(str(a), TS)
            second = store.save(str(b), TS.replace(minute=1))

            self.assertNotEqual(first, second)
            self.assertEqual(len(list((Path(tmp) / "images").rglob("*.jpg"))), 2)

    def test_diff_threshold_is_fixed(self):
        self.assertEqual(IMAGE_DIFF_THRESHOLD, 2.0)
        self.assertTrue(images_mod.frames_similar(bytes([10] * 1024), bytes([11] * 1024)))
        self.assertFalse(images_mod.frames_similar(bytes([10] * 1024), bytes([13] * 1024)))
        self.assertFalse(images_mod.frames_similar(None, bytes([10] * 1024)))

    def test_same_second_filename_does_not_overwrite(self):
        with TemporaryDirectory() as tmp:
            sig = iter([bytes([0] * 1024), bytes([200] * 1024)])
            store = ImageStore(
                Path(tmp) / "images", encoder=stub_encoder, thumbnailer=lambda p: next(sig)
            )
            first = store.save("x.png", TS)
            second = store.save("x.png", TS)
            self.assertNotEqual(first, second)

    def test_save_failure_returns_none_and_keeps_state(self):
        def failing(src, dest):
            raise OSError("No space left on device")

        with TemporaryDirectory() as tmp:
            store = ImageStore(
                Path(tmp) / "images",
                encoder=failing,
                thumbnailer=lambda p: bytes([0] * 1024),
            )
            self.assertIsNone(store.save("x.png", TS))
            self.assertIsNone(store.last_path)


class ImageCycleTests(unittest.TestCase):
    def _run(self, store, *, idle_seconds=0, previous=None, ocr_text="hello", ts=TS):
        return process_capture(
            previous_entry=previous,
            timestamp=ts,
            window_context_provider=lambda: {
                "working_app": "Codex",
                "working_title": "Codex",
                "window_id": 1,
            },
            screenshot_taker=lambda window_id=None: "/tmp/screenlog-test.png",
            text_extractor=lambda path: OCRResult(text=ocr_text, confidence=0.9),
            screenshot_deleter=lambda path: True,
            screen_permission_checker=lambda: True,
            idle_seconds_provider=lambda: idle_seconds,
            image_store=store,
        )

    def test_log_entry_has_image_path(self):
        with TemporaryDirectory() as tmp:
            store = ImageStore(
                Path(tmp) / "images", encoder=stub_encoder, thumbnailer=lambda p: bytes(1024)
            )
            result = self._run(store)
            path = result.current_entry["image_path"]
            self.assertTrue(Path(path).exists())
            self.assertEqual(path, store.last_path)
            # JSONLにシリアライズできる
            json.dumps(result.current_entry)

    def test_similar_frame_reuses_previous_image_path(self):
        with TemporaryDirectory() as tmp:
            store = ImageStore(
                Path(tmp) / "images", encoder=stub_encoder, thumbnailer=lambda p: bytes(1024)
            )
            first = self._run(store, ocr_text="a")
            second = self._run(
                store, ocr_text="b", previous=first.current_entry, ts=TS.replace(minute=1)
            )
            self.assertEqual(
                second.current_entry["image_path"], first.current_entry["image_path"]
            )
            self.assertEqual(len(list((Path(tmp) / "images").rglob("*.jpg"))), 1)

    def test_idle_cycle_saves_no_image(self):
        with TemporaryDirectory() as tmp:
            store = ImageStore(
                Path(tmp) / "images", encoder=stub_encoder, thumbnailer=lambda p: bytes(1024)
            )
            result = self._run(store, idle_seconds=10_000)
            self.assertNotIn("image_path", result.current_entry)
            self.assertEqual(list((Path(tmp) / "images").rglob("*.jpg")), [])

    def test_ocr_runs_on_full_size_before_downscale(self):
        order = []

        def extractor(path):
            order.append("ocr")
            return OCRResult(text="t", confidence=0.9)

        def encoder(src, dest):
            order.append("encode")
            Path(dest).write_bytes(b"j")
            return (1, 1)

        with TemporaryDirectory() as tmp:
            store = ImageStore(
                Path(tmp) / "images", encoder=encoder, thumbnailer=lambda p: bytes(1024)
            )
            process_capture(
                timestamp=TS,
                window_context_provider=lambda: {"working_app": "A", "working_title": "B"},
                screenshot_taker=lambda window_id=None: "/tmp/full.png",
                text_extractor=extractor,
                screenshot_deleter=lambda path: True,
                screen_permission_checker=lambda: True,
                idle_seconds_provider=lambda: 0,
                image_store=store,
            )
        self.assertEqual(order, ["ocr", "encode"])

    def test_image_save_failure_does_not_break_cycle(self):
        def failing(src, dest):
            raise OSError("disk full")

        deleted = []
        with TemporaryDirectory() as tmp:
            store = ImageStore(
                Path(tmp) / "images", encoder=failing, thumbnailer=lambda p: bytes(1024)
            )
            result = process_capture(
                timestamp=TS,
                window_context_provider=lambda: {"working_app": "A", "working_title": "B"},
                screenshot_taker=lambda window_id=None: "/tmp/full.png",
                text_extractor=lambda path: OCRResult(text="t", confidence=0.9),
                screenshot_deleter=lambda path: deleted.append(path) or True,
                screen_permission_checker=lambda: True,
                idle_seconds_provider=lambda: 0,
                image_store=store,
            )
        self.assertEqual(result.reason, "new")
        self.assertEqual(result.current_entry["ocr_text"], "t")
        self.assertEqual(result.current_entry["capture_status"], "ok")
        self.assertIsNone(result.current_entry.get("image_path"))
        self.assertEqual(deleted, ["/tmp/full.png"])

    def test_store_that_raises_does_not_break_cycle(self):
        class Boom:
            def save(self, *a, **k):
                raise RuntimeError("boom")

        result = self._run(Boom())
        self.assertEqual(result.reason, "new")
        self.assertEqual(result.current_entry["capture_status"], "ok")


class ImageRetentionTests(unittest.TestCase):
    def test_default_retention_values(self):
        self.assertEqual(DEFAULT_IMAGE_RETENTION_DAYS, 30)
        settings = load_runtime_settings({})
        self.assertEqual(settings.image_retention_days, 30)
        self.assertEqual(settings.retention_days, DEFAULT_RETENTION_DAYS)
        custom = load_runtime_settings({"retention_days": 400, "image_retention_days": 7})
        self.assertEqual(custom.image_retention_days, 7)
        self.assertEqual(custom.retention_days, 400)

    def test_image_retention_independent_of_log_retention(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            images_dir = root / "images"
            logs_dir = root / "logs"
            for d in ("2026-08-01", "2026-09-01", "2026-09-15", "2026-10-01", "not-a-date"):
                (images_dir / d).mkdir(parents=True)
                (images_dir / d / "a.jpg").write_bytes(b"x")
            logs_dir.mkdir()
            for d in ("2026-08-01", "2026-10-01"):
                (logs_dir / f"{d}.jsonl").write_text("{}\n", encoding="utf-8")

            deleted = cleanup_old_images(
                30, images_dir=images_dir, today=date(2026, 10, 1)
            )

            # 2026-10-01 - 30日 = 2026-09-01。それより古い日付フォルダのみ削除
            self.assertEqual(deleted, 1)
            self.assertFalse((images_dir / "2026-08-01").exists())
            self.assertTrue((images_dir / "2026-09-01").exists())
            self.assertTrue((images_dir / "2026-09-15").exists())
            self.assertTrue((images_dir / "2026-10-01").exists())
            self.assertTrue((images_dir / "not-a-date").exists())
            # 文字ログは画像の掃除では触られない
            self.assertTrue((logs_dir / "2026-08-01.jsonl").exists())

            # 文字ログの掃除（400日）も画像に影響しない
            with patch("screenlog.logger.get_log_dir", return_value=logs_dir):
                cleanup_old_logs(days=400)
            self.assertTrue((images_dir / "2026-09-01").exists())

    def test_cleanup_missing_dir_is_noop(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                cleanup_old_images(30, images_dir=Path(tmp) / "none", today=date(2026, 10, 1)),
                0,
            )

    def test_invalid_retention_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                cleanup_old_images(0, images_dir=Path(tmp), today=date(2026, 10, 1))


class ImageDoctorTests(unittest.TestCase):
    def test_image_usage_empty(self):
        with TemporaryDirectory() as tmp:
            usage = image_usage(Path(tmp) / "none")
            self.assertEqual(usage["total_bytes"], 0)
            self.assertEqual(usage["file_count"], 0)
            self.assertIsNone(usage["oldest_date"])

    def test_doctor_reports_image_usage(self):
        with TemporaryDirectory() as tmp:
            images_dir = Path(tmp) / "images"
            (images_dir / "2026-09-20").mkdir(parents=True)
            (images_dir / "2026-10-01").mkdir(parents=True)
            (images_dir / "2026-09-20" / "a.jpg").write_bytes(b"x" * 100)
            (images_dir / "2026-10-01" / "b.jpg").write_bytes(b"x" * 50)

            with patch("screenlog.doctor.get_window_context", return_value={}):
                report = build_doctor_report(
                    now=datetime.fromisoformat("2026-10-01T10:00:00+09:00"),
                    latest_log_path=None,
                    screen_permission_checker=lambda: True,
                    config={"interval": 60, "flush_interval": 300},
                    images_dir=images_dir,
                )

            usage = report["images"]
            self.assertEqual(usage["total_bytes"], 150)
            self.assertEqual(usage["file_count"], 2)
            self.assertEqual(usage["oldest_date"], "2026-09-20")
            self.assertEqual(usage["path"], str(images_dir))
            json.dumps(report, default=str)


if __name__ == "__main__":
    unittest.main()
