#!/bin/zsh
# Spustí Cursor Usage menu bar app
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$APP_DIR/app.py"
