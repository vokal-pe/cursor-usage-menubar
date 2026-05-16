#!/usr/bin/env bash
# uninstall.sh — removes cursor-usage-menubar from auto-start and stops the app
set -euo pipefail

PLIST_NAME="com.petrvokal.cursor-usage-menubar.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "==> Uninstalling cursor-usage-menubar…"

# Stop and unload LaunchAgent
if [ -f "$LAUNCH_AGENTS/$PLIST_NAME" ]; then
    launchctl unload "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || true
    rm -f "$LAUNCH_AGENTS/$PLIST_NAME"
    echo "--> LaunchAgent removed."
else
    echo "--> LaunchAgent not found (already removed?)."
fi

# Kill any running instance
pkill -f "app.py" 2>/dev/null && echo "--> App stopped." || echo "--> App was not running."

echo ""
echo "✅  Done. cursor-usage-menubar has been uninstalled."
echo "   Config is kept at: ~/Library/Application Support/cursor-usage/"
echo "   Remove it manually if you want to delete the saved token."
