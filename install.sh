#!/usr/bin/env bash
# install.sh — one-shot installer for cursor-usage-menubar
# Usage: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.petrvokal.cursor-usage-menubar.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "==> Installing cursor-usage-menubar…"

# 1. Python deps
echo "--> Installing Python dependencies…"
pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet

# 2. LaunchAgent
echo "--> Installing LaunchAgent (auto-start on login)…"
mkdir -p "$LAUNCH_AGENTS"

# Patch the plist so it points to the actual install location
sed "s|SCRIPT_DIR|$SCRIPT_DIR|g" "$SCRIPT_DIR/$PLIST_NAME" \
    > "$LAUNCH_AGENTS/$PLIST_NAME"

launchctl unload "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || true
launchctl load   "$LAUNCH_AGENTS/$PLIST_NAME"

echo ""
echo "✅  Done! The app is now running and will start automatically on login."
echo "   Look for the Cursor usage icon in your menu bar."
