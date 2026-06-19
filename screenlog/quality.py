"""Capture quality classification."""

from typing import Any, TypedDict


MENU_ONLY_TEXTS = {
    "Codex\nFile\nEdit\nView\nWindow\nHelp",
    "Obsidian\nFile\nEdit\nInsert\nFormat\nView\nWindow\nHelp",
    "Chrome\nファイル\n編集\n表示\n履歴\nブックマーク\nプロファイル\nタブ ウィンドウ\nヘルプ",
    "Slack\nファイル\n編集\n表示\n開始\n履歴\nウィンドウ\nヘルプ",
}

MENU_TOKENS = {
    "File",
    "Edit",
    "View",
    "Window",
    "Help",
    "ファイル",
    "編集",
    "表示",
    "ウィンドウ",
    "ヘルプ",
}


class CaptureQuality(TypedDict):
    capture_status: str
    capture_error: str | None
    ocr_length: int
    is_suspicious: bool
    screen_recording_allowed: bool | None


def _compact_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def looks_like_menu_only(text: str) -> bool:
    """Return True when OCR looks like only the macOS menu bar was captured."""
    normalized = "\n".join(_compact_lines(text))
    if normalized in MENU_ONLY_TEXTS:
        return True

    lines = _compact_lines(text)
    if not lines or len(lines) > 12:
        return False

    token_hits = sum(1 for line in lines if line in MENU_TOKENS)
    return token_hits >= 4 and len(normalized) < 120


def classify_capture(
    ocr_text: str,
    *,
    screen_recording_allowed: bool | None = None,
    capture_error: str | None = None,
) -> CaptureQuality:
    """Classify one capture result into a loggable diagnostic status."""
    text = ocr_text or ""
    ocr_length = len(text.strip())

    if screen_recording_allowed is False:
        status = "screen_permission_denied"
        suspicious = True
    elif capture_error:
        status = "capture_failed"
        suspicious = True
    elif ocr_length == 0:
        status = "empty_ocr"
        suspicious = True
    elif looks_like_menu_only(text):
        status = "suspicious_menu_only"
        suspicious = True
    else:
        status = "ok"
        suspicious = False

    return {
        "capture_status": status,
        "capture_error": capture_error,
        "ocr_length": ocr_length,
        "is_suspicious": suspicious,
        "screen_recording_allowed": screen_recording_allowed,
    }


def apply_capture_quality(
    context: dict[str, Any],
    quality: CaptureQuality,
) -> dict[str, Any]:
    """Return window context augmented with capture quality fields."""
    updated = dict(context)
    updated.update(quality)
    return updated
