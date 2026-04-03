#!/bin/bash
set -euo pipefail

REPO="rsnemmen/koreader-merge"
SCRIPT_URL="https://raw.githubusercontent.com/${REPO}/main/merge_koreader.py"
CMD_NAME="merge_koreader"

# Check for Python 3.6+
PYTHON=""
for cmd in python python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        ver=$("$cmd" -c 'import sys; print(sys.version_info[:2] >= (3,6))' 2>/dev/null || true)
        if [ "$ver" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.6+ is required but not found." >&2
    exit 1
fi

# Pick install directory
if [ -w /usr/local/bin ]; then
    INSTALL_DIR="/usr/local/bin"
else
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
fi

INSTALL_PATH="$INSTALL_DIR/$CMD_NAME"

# Download
echo "Downloading ${CMD_NAME}..."
curl -fsSL "$SCRIPT_URL" -o "$INSTALL_PATH"

# Fix shebang to use generic python
sed -i.bak '1s|#!.*python.*|#!/usr/bin/env python|' "$INSTALL_PATH"
rm -f "${INSTALL_PATH}.bak"

# Make executable
chmod +x "$INSTALL_PATH"

echo ""
echo "Installed: $INSTALL_PATH"
echo ""
echo "Usage:"
echo "  ${CMD_NAME} file1.lua file2.lua -o output.lua"
echo ""
echo "Optional features:"
echo "  pip install ebooklib   # for --render-html"
echo "  pip install PyMuPDF    # for --render-pdf"

# Warn if ~/.local/bin is not on PATH
if [ "$INSTALL_DIR" = "$HOME/.local/bin" ]; then
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *)
            echo ""
            echo "NOTE: Add ~/.local/bin to your PATH:"
            echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
            ;;
    esac
fi
