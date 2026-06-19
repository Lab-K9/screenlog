"""LaunchAgent helpers for starting ScreenLog at login."""

from __future__ import annotations

import argparse
import plistlib
from pathlib import Path


LAUNCH_AGENT_LABEL = "com.screenlog.app"


def default_app_path(home: Path | None = None) -> Path:
    """Return the stable per-user app install path."""
    root = home if home is not None else Path.home()
    return root / "Applications" / "ScreenLog.app"


def default_launch_agent_path(home: Path | None = None) -> Path:
    """Return the per-user LaunchAgent plist path."""
    root = home if home is not None else Path.home()
    return root / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def render_launch_agent_plist(app_path: Path) -> dict:
    """Render a LaunchAgent plist that opens ScreenLog.app at login."""
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": ["/usr/bin/open", "-a", str(app_path)],
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "ScreenLog.launchd.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "ScreenLog.launchd.err.log"),
    }


def write_launch_agent_plist(plist_path: Path, *, app_path: Path) -> bool:
    """Write the LaunchAgent plist."""
    try:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_bytes(plistlib.dumps(render_launch_agent_plist(app_path)))
        return True
    except OSError as e:
        print(f"Warning: Could not write LaunchAgent plist {plist_path}: {e}")
        return False


def remove_launch_agent_plist(plist_path: Path) -> bool:
    """Remove the LaunchAgent plist if present."""
    try:
        plist_path.unlink(missing_ok=True)
        return True
    except OSError as e:
        print(f"Warning: Could not remove LaunchAgent plist {plist_path}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="ScreenLog LaunchAgent helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--app-path", type=Path, default=default_app_path())
    install_parser.add_argument("--plist-path", type=Path, default=default_launch_agent_path())

    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("--plist-path", type=Path, default=default_launch_agent_path())

    subparsers.add_parser("path")

    args = parser.parse_args()
    if args.command == "install":
        if write_launch_agent_plist(args.plist_path, app_path=args.app_path):
            print(args.plist_path)
            return 0
        return 1
    if args.command == "uninstall":
        if remove_launch_agent_plist(args.plist_path):
            print(args.plist_path)
            return 0
        return 1
    if args.command == "path":
        print(default_launch_agent_path())
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
