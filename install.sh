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

# 2. LaunchAgent (volitelné)
echo ""
read -r -p "Start automatically on login? [Y/n] " AUTOSTART
AUTOSTART="${AUTOSTART:-Y}"

if [[ "$AUTOSTART" =~ ^[Yy]$ ]]; then
    echo "--> Installing LaunchAgent (auto-start on login)…"
    mkdir -p "$LAUNCH_AGENTS"
    sed "s|SCRIPT_DIR|$SCRIPT_DIR|g" "$SCRIPT_DIR/$PLIST_NAME" \
        > "$LAUNCH_AGENTS/$PLIST_NAME"
    launchctl unload "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || true
    launchctl load   "$LAUNCH_AGENTS/$PLIST_NAME"
    echo ""
    echo "✅  Done! The app will start automatically on login."
else
    echo "--> Skipping auto-start. To start manually: python3 $SCRIPT_DIR/app.py"
    echo ""
    echo "✅  Done! Starting the app now…"
    python3 "$SCRIPT_DIR/app.py" &
fi

echo "   Look for the Cursor usage icon in your menu bar."
