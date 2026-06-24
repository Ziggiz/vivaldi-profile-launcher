#!/bin/bash
# Builds "Vivaldi Profiles.app" from launcher.applescript.
#
# The app is self-contained: the core CLI (and optional config.json + icon) are
# copied into the .app bundle. The GUI finds the CLI via its own bundle path, so
# the app can be moved freely – and the project folder can be moved/deleted –
# without breaking it.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLI_PATH="$REPO_DIR/vivaldi_profiles.py"
APP_NAME="Vivaldi Profiles.app"
SRC="$REPO_DIR/launcher.applescript"
APP="$REPO_DIR/$APP_NAME"
RES="$APP/Contents/Resources"

if [[ ! -f "$CLI_PATH" ]]; then
  echo "Could not find $CLI_PATH" >&2
  exit 1
fi

rm -rf "$APP"
osacompile -o "$APP" "$SRC"

# Copy the CLI into the bundle (makes the app self-contained).
cp "$CLI_PATH" "$RES/vivaldi_profiles.py"
echo "CLI copied into the bundle."

# Copy config.json if present (otherwise the CLI's defaults are used).
if [[ -f "$REPO_DIR/config.json" ]]; then
  cp "$REPO_DIR/config.json" "$RES/config.json"
  echo "config.json copied into the bundle."
fi

# Set the app icon if AppIcon.icns exists (osacompile uses applet.icns).
ICON="$REPO_DIR/AppIcon.icns"
if [[ -f "$ICON" ]]; then
  cp "$ICON" "$RES/applet.icns"
  echo "Icon set from: $ICON"
fi

# Nudge Finder/Dock to refresh the icon cache.
touch "$APP"

echo "Built self-contained app: $APP"
