#!/bin/bash
# Clishe installer - clones (or updates) the repo into ~/.clishe-src and
# symlinks the launcher onto your PATH.
set -euo pipefail

REPO_URL="https://github.com/Sym-jay/clishe.git"
INSTALL_DIR="$HOME/.clishe-src"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/clishe"

echo "Installing Clishe..."

if ! command -v git &> /dev/null; then
    echo "Error: git is required. Install it and re-run this script." >&2
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required. Install it and re-run this script." >&2
    exit 1
fi

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Existing install found - updating..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/clishe.sh" "$LAUNCHER"
chmod +x "$INSTALL_DIR/clishe.sh" "$INSTALL_DIR/clishe_brain.py" "$LAUNCHER"

echo ""
echo "Clishe installed to $INSTALL_DIR"
echo "Launcher linked at $LAUNCHER"
echo ""

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "NOTE: $BIN_DIR is not on your PATH yet. Add this to your ~/.bashrc or ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then restart your shell, or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
else
    echo "Run 'clishe' to get started."
fi
