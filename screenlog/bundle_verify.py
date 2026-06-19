"""App bundle signature verification helpers."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


Runner = Callable[..., subprocess.CompletedProcess[str]]


class BundleSignatureError(RuntimeError):
    """Raised when an app bundle signature does not satisfy requirements."""


@dataclass(frozen=True)
class BundleSignature:
    """Parsed code signature information for an app bundle."""

    identifier: str | None
    team_identifier: str | None


def parse_codesign_details(output: str) -> dict[str, str]:
    """Parse ``codesign -dv`` key/value output."""
    details: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key:
            details[key] = value
    return details


def _normalize_team_identifier(value: str | None) -> str | None:
    if value is None or value == "not set" or value == "":
        return None
    return value


def verify_bundle_signature(
    app_path: Path,
    *,
    require_team_id: bool = False,
    expected_team_id: str | None = None,
    runner: Runner = subprocess.run,
) -> BundleSignature:
    """Verify codesign validity and optional TeamIdentifier requirements."""
    verify_result = runner(
        ["codesign", "--verify", "--deep", "--strict", str(app_path)],
        capture_output=True,
        text=True,
    )
    if verify_result.returncode != 0:
        message = verify_result.stderr.strip() or verify_result.stdout.strip()
        raise BundleSignatureError(f"codesign verification failed: {message}")

    details_result = runner(
        ["codesign", "-dv", str(app_path)],
        capture_output=True,
        text=True,
    )
    if details_result.returncode != 0:
        message = details_result.stderr.strip() or details_result.stdout.strip()
        raise BundleSignatureError(f"codesign details failed: {message}")

    details = parse_codesign_details(details_result.stdout + details_result.stderr)
    signature = BundleSignature(
        identifier=details.get("Identifier"),
        team_identifier=_normalize_team_identifier(details.get("TeamIdentifier")),
    )

    if require_team_id and signature.team_identifier is None:
        raise BundleSignatureError(
            "TeamIdentifier is not set. Use an Apple-issued Developer ID certificate "
            "for stable macOS permission binding."
        )

    if expected_team_id and signature.team_identifier != expected_team_id:
        actual = signature.team_identifier or "not set"
        raise BundleSignatureError(
            f"TeamIdentifier mismatch: expected {expected_team_id}, got {actual}"
        )

    return signature


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ScreenLog.app code signature")
    parser.add_argument("app_path", type=Path)
    parser.add_argument("--require-team-id", action="store_true")
    parser.add_argument("--expected-team-id")
    args = parser.parse_args()

    try:
        signature = verify_bundle_signature(
            args.app_path,
            require_team_id=args.require_team_id,
            expected_team_id=args.expected_team_id,
        )
    except BundleSignatureError as e:
        print(f"Signature verification failed: {e}")
        return 1

    team_identifier = signature.team_identifier or "not set"
    print(
        "Signature OK: "
        f"identifier={signature.identifier or 'unknown'} "
        f"team_identifier={team_identifier}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
