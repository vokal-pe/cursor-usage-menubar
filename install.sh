#!/usr/bin/env bash
# install.sh — one-shot installer for cursor-usage-menubar
# Usage: bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.petrvokal.cursor-usage-menubar.plist"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
# launchd cannot read ~/Documents (TCC) — install a copy here instead
INSTALL_DIR="$HOME/Library/Application Support/cursor-usage/menubar"

echo "==> Installing cursor-usage-menubar…"

# 0. Deploy app outside Documents (LaunchAgent + privacy)
echo "--> Copying app to Application Support…"
mkdir -p "$INSTALL_DIR"
for f in app.py login_window.py requirements.txt start.sh; do
    cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
done

# 1. Python deps
echo "--> Installing Python dependencies…"
pip3 install -r "$INSTALL_DIR/requirements.txt" --quiet

# 2. LaunchAgent (volitelné)
echo ""
read -r -p "Start automatically on login? [Y/n] " AUTOSTART
AUTOSTART="${AUTOSTART:-Y}"

if [[ "$AUTOSTART" =~ ^[Yy]$ ]]; then
    echo "--> Installing LaunchAgent (auto-start on login)…"
    mkdir -p "$LAUNCH_AGENTS"
    sed "s|INSTALL_DIR|$INSTALL_DIR|g" "$SCRIPT_DIR/$PLIST_NAME" \
        > "$LAUNCH_AGENTS/$PLIST_NAME"
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || \
        launchctl unload "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/$PLIST_NAME" 2>/dev/null || \
        launchctl load "$LAUNCH_AGENTS/$PLIST_NAME"
    echo ""
    echo "✅  Done! The app will start automatically on login."
else
    echo "--> Skipping auto-start. To start manually: bash \"$INSTALL_DIR/start.sh\""
    echo ""
    echo "✅  Done! Starting the app now…"
    pkill -f "$INSTALL_DIR/app.py" 2>/dev/null || true
    bash "$INSTALL_DIR/start.sh" &
fi

# Stop any stale instance from repo path or older installs
pkill -f "cursor-usage-menubar/app.py" 2>/dev/null || true

echo "   Look for the Cursor usage icon in your menu bar."
