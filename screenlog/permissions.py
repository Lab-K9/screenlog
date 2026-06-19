"""macOS privacy permission helpers."""

from dataclasses import dataclass
from typing import Callable


PermissionChecker = Callable[[], bool | None]
PermissionRequester = Callable[[], bool | None]


@dataclass(frozen=True)
class ScreenRecordingAccessResult:
    allowed: bool | None
    requested: bool


def screen_recording_preflight() -> bool | None:
    """
    Return the current Screen Recording permission state if the API is available.

    `None` means the status could not be determined in the current runtime.
    """
    try:
        import Quartz

        checker = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
        if checker is None:
            return None
        return bool(checker())
    except Exception:
        return None


def request_screen_recording_access() -> bool | None:
    """
    Ask macOS to show the Screen Recording permission flow when available.

    `None` means the request API could not be called in the current runtime.
    """
    try:
        import Quartz

        requester = getattr(Quartz, "CGRequestScreenCaptureAccess", None)
        if requester is None:
            return None
        return bool(requester())
    except Exception:
        return None


def ensure_screen_recording_access(
    *,
    checker: PermissionChecker = screen_recording_preflight,
    requester: PermissionRequester = request_screen_recording_access,
) -> ScreenRecordingAccessResult:
    """Request Screen Recording access only when macOS reports it is denied."""
    allowed = checker()
    if allowed is not False:
        return ScreenRecordingAccessResult(allowed=allowed, requested=False)

    requested_allowed = requester()
    return ScreenRecordingAccessResult(allowed=requested_allowed, requested=True)
