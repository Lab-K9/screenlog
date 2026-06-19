"""Runtime settings shared by CLI and menu bar app."""

from dataclasses import dataclass
from typing import Any

from .config import (
    DEFAULT_FLUSH_INTERVAL,
    DEFAULT_INTERVAL,
    DEFAULT_RETENTION_DAYS,
    get_config,
    validate_interval,
    validate_retention_days,
)


@dataclass(frozen=True)
class RuntimeSettings:
    interval: int
    retention_days: int
    flush_interval: int


def load_runtime_settings(config: dict[str, Any] | None = None) -> RuntimeSettings:
    """Load and validate shared ScreenLog runtime settings."""
    source = get_config() if config is None else dict(config)
    interval = validate_interval(int(source.get("interval", DEFAULT_INTERVAL)))
    retention_days = validate_retention_days(
        int(source.get("retention_days", DEFAULT_RETENTION_DAYS))
    )
    flush_interval = validate_interval(
        int(source.get("flush_interval", DEFAULT_FLUSH_INTERVAL))
    )

    return RuntimeSettings(
        interval=interval,
        retention_days=retention_days,
        flush_interval=flush_interval,
    )
