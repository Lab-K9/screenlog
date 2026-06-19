#!/bin/bash
# Build and install ScreenLog.app to a stable per-user path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEST="${SCREENLOG_APP_DEST:-$HOME/Applications/ScreenLog.app}"
BACKUP=""

cd "$PROJECT_DIR"

if [ -z "${SCREENLOG_CODESIGN_IDENTITY:-}" ]; then
    if security find-identity -v -p codesigning | grep -q '"ScreenLog Local Developer ID"'; then
        export SCREENLOG_CODESIGN_IDENTITY="ScreenLog Local Developer ID"
    fi
fi

./scripts/build-app.sh

mkdir -p "$(dirname "$DEST")"
if [ -d "$DEST" ]; then
    BACKUP="$DEST.backup.$$"
    mv "$DEST" "$BACKUP"
fi

restore_backup() {
    if [ -n "$BACKUP" ] && [ -d "$BACKUP" ]; then
        rm -rf "$DEST"
        mv "$BACKUP" "$DEST"
    fi
}
trap restore_backup ERR

ditto "$PROJECT_DIR/dist/ScreenLog.app" "$DEST"
codesign --verify --deep --strict "$DEST"

if [ -n "$BACKUP" ] && [ -d "$BACKUP" ]; then
    rm -rf "$BACKUP"
fi
trap - ERR

echo "Installed ScreenLog.app: $DEST"
