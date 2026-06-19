"""Shared capture cycle implementation for CLI and menu bar app."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .logger import LogEntry, create_log_entry, update_log_entry
from .ocr import OCRResult, extract_text
from .permissions import screen_recording_preflight
from .quality import apply_capture_quality, classify_capture
from .window import get_window_context


WindowContextProvider = Callable[[], dict]
ScreenshotTaker = Callable[..., str | None]
TextExtractor = Callable[[str], OCRResult]
ScreenshotDeleter = Callable[[str], bool]
ScreenPermissionChecker = Callable[[], bool | None]


@dataclass(frozen=True)
class CaptureCycleResult:
    to_write: LogEntry | None
    current_entry: LogEntry | None
    reason: str
    message: str


def should_flush_entry(
    entry: LogEntry,
    timestamp: datetime,
    *,
    flush_interval_seconds: int,
) -> bool:
    """Return True when a still-open entry should be rotated to disk."""
    start_dt = datetime.fromisoformat(entry["start_time"])
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    return (timestamp - start_dt).total_seconds() >= flush_interval_seconds


def _entry_matches_current(
    previous_entry: LogEntry | None,
    *,
    active_app: str,
    window_title: str,
    ocr_text: str,
) -> bool:
    return (
        previous_entry is not None
        and previous_entry.get("ocr_text") == ocr_text
        and previous_entry.get("working_app", previous_entry.get("active_app")) == active_app
        and previous_entry.get("working_title", previous_entry.get("window_title")) == window_title
    )


def _create_entry(
    *,
    active_app: str,
    window_title: str,
    ocr_result: OCRResult,
    timestamp: datetime,
    window_context: dict,
    screen_recording_allowed: bool | None,
    capture_error: str | None = None,
) -> LogEntry:
    quality = classify_capture(
        ocr_result.text,
        screen_recording_allowed=screen_recording_allowed,
        capture_error=capture_error,
    )
    enriched_context = apply_capture_quality(window_context, quality)
    return create_log_entry(
        active_app=active_app,
        window_title=window_title,
        ocr_text=ocr_result.text,
        ocr_confidence=ocr_result.confidence,
        timestamp=timestamp,
        window_context=enriched_context,
    )


def process_capture(
    previous_entry: LogEntry | None = None,
    *,
    timestamp: datetime | None = None,
    flush_interval_seconds: int = 300,
    window_context_provider: WindowContextProvider = get_window_context,
    screenshot_taker: ScreenshotTaker | None = None,
    text_extractor: TextExtractor = extract_text,
    screenshot_deleter: ScreenshotDeleter | None = None,
    screen_permission_checker: ScreenPermissionChecker = screen_recording_preflight,
) -> CaptureCycleResult:
    """Run one capture cycle and return the entry state transition."""
    if timestamp is None:
        timestamp = datetime.now()
    if screenshot_taker is None or screenshot_deleter is None:
        from .capture import delete_screenshot, take_screenshot

        if screenshot_taker is None:
            screenshot_taker = take_screenshot
        if screenshot_deleter is None:
            screenshot_deleter = delete_screenshot

    screen_recording_allowed = screen_permission_checker()
    window_context = window_context_provider()
    active_app = str(window_context.get("working_app") or "Unknown")
    window_title = str(window_context.get("working_title") or "Unknown")
    window_id = window_context.get("window_id")

    if screen_recording_allowed is False:
        current_entry = _create_entry(
            active_app=active_app,
            window_title=window_title,
            ocr_result=OCRResult(text="", confidence=None),
            timestamp=timestamp,
            window_context=window_context,
            screen_recording_allowed=screen_recording_allowed,
            capture_error="Screen Recording permission is not granted",
        )
        return CaptureCycleResult(
            to_write=previous_entry,
            current_entry=current_entry,
            reason="screen_permission_denied",
            message="Screen Recording permission is not granted",
        )

    screenshot_path = screenshot_taker(window_id=window_id if isinstance(window_id, int) else None)
    if screenshot_path is None:
        current_entry = _create_entry(
            active_app=active_app,
            window_title=window_title,
            ocr_result=OCRResult(text="", confidence=None),
            timestamp=timestamp,
            window_context=window_context,
            screen_recording_allowed=screen_recording_allowed,
            capture_error="Screenshot capture failed",
        )
        return CaptureCycleResult(
            to_write=previous_entry,
            current_entry=current_entry,
            reason="capture_failed",
            message="Screenshot capture failed",
        )

    try:
        ocr_result = text_extractor(screenshot_path)
        same_entry = _entry_matches_current(
            previous_entry,
            active_app=active_app,
            window_title=window_title,
            ocr_text=ocr_result.text,
        )

        if same_entry and previous_entry is not None:
            if should_flush_entry(
                previous_entry,
                timestamp,
                flush_interval_seconds=flush_interval_seconds,
            ):
                current_entry = _create_entry(
                    active_app=active_app,
                    window_title=window_title,
                    ocr_result=ocr_result,
                    timestamp=timestamp,
                    window_context=window_context,
                    screen_recording_allowed=screen_recording_allowed,
                )
                return CaptureCycleResult(
                    to_write=previous_entry,
                    current_entry=current_entry,
                    reason="flush_interval",
                    message=f"Flushed continuing entry for {active_app}",
                )

            current_entry = update_log_entry(
                entry=previous_entry,
                new_timestamp=timestamp,
                new_confidence=ocr_result.confidence,
            )
            return CaptureCycleResult(
                to_write=None,
                current_entry=current_entry,
                reason="continuing",
                message=f"Continuing {active_app}",
            )

        current_entry = _create_entry(
            active_app=active_app,
            window_title=window_title,
            ocr_result=ocr_result,
            timestamp=timestamp,
            window_context=window_context,
            screen_recording_allowed=screen_recording_allowed,
        )
        reason = "new" if previous_entry is None else "changed"
        return CaptureCycleResult(
            to_write=previous_entry,
            current_entry=current_entry,
            reason=reason,
            message=f"Captured {active_app}",
        )

    except Exception as e:
        current_entry = _create_entry(
            active_app=active_app,
            window_title=window_title,
            ocr_result=OCRResult(text="", confidence=None),
            timestamp=timestamp,
            window_context=window_context,
            screen_recording_allowed=screen_recording_allowed,
            capture_error=str(e),
        )
        return CaptureCycleResult(
            to_write=previous_entry,
            current_entry=current_entry,
            reason="error",
            message=f"Capture cycle error: {e}",
        )

    finally:
        screenshot_deleter(screenshot_path)
