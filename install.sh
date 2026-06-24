#!/bin/bash
# One-command installer for the Vivaldi Profile Launcher (macOS).
#
# Run from a checked-out copy:
#     ./install.sh
#
# …or straight from the internet:
#     curl -fsSL https://raw.githubusercontent.com/Ziggiz/vivaldi-profile-launcher/main/install.sh | bash
#
# It builds the app locally (so macOS won't flag it as an untrusted download)
# and installs it to /Applications.

set -euo pipefail

REPO="Ziggiz/vivaldi-profile-launcher"
APP_NAME="Vivaldi Profiles.app"
TARBALL="https://github.com/$REPO/archive/refs/heads/main.tar.gz"

say() { printf '\033[1;31m▸\033[0m %s\n' "$1"; }
err() { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; }

# 1. Require python3 (ships with the Command Line Tools).
if ! command -v /usr/bin/python3 >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  err "python3 was not found."
  echo "  Install Apple's Command Line Tools first, then re-run this:" >&2
  echo "      xcode-select --install" >&2
  exit 1
fi

# 2. Locate the source: a local checkout, or download it.
SCRIPT_SRC="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_SRC" && -f "$(cd "$(dirname "$SCRIPT_SRC")" && pwd)/launcher.applescript" ]]; then
  SRC_DIR="$(cd "$(dirname "$SCRIPT_SRC")" && pwd)"
  say "Building from local checkout: $SRC_DIR"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  say "Downloading source …"
  curl -fsSL "$TARBALL" | tar -xz -C "$TMP"
  SRC_DIR="$(find "$TMP" -maxdepth 1 -type d -name '*vivaldi-profile-launcher*' | head -1)"
  if [[ -z "$SRC_DIR" ]]; then
    err "Could not unpack the downloaded source."
    exit 1
  fi
  say "Building from downloaded source."
fi

# 3. Build the app.
say "Building \"$APP_NAME\" …"
( cd "$SRC_DIR" && bash build_app.sh >/dev/null )

# 4. Install to /Applications.
say "Installing to /Applications …"
rm -rf "/Applications/$APP_NAME"
cp -R "$SRC_DIR/$APP_NAME" "/Applications/$APP_NAME"
touch "/Applications/$APP_NAME"

# 5. Refresh the icon cache.
killall Dock Finder >/dev/null 2>&1 || true

say "Done!"
echo
echo "  Open it from Spotlight (⌘-Space → \"Vivaldi Profiles\") or /Applications."
echo
echo "  Tip: to create new profiles from a template, make a Vivaldi profile named"
echo "  \"Default-template\" with your preferred bookmarks/Speed Dial first."
