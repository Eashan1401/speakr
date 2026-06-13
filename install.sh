#!/bin/bash
set -euo pipefail

SPEAKR_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  Speakr — free local voice dictation for macOS"
echo "  ───────────────────────────────────────────────"
echo ""

# ── Homebrew ──────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  echo "  Homebrew not found. Install it from https://brew.sh, then re-run this script."
  exit 1
fi
echo "  ✓ Homebrew found."

# ── Java (LanguageTool needs it for grammar correction) ───────────────────────
if [ ! -d "/opt/homebrew/opt/openjdk" ] && ! command -v java &>/dev/null; then
  echo "  Installing Java (needed for grammar correction, one-time ~200 MB)…"
  brew install openjdk
fi
echo "  ✓ Java found."

# Add Java to PATH for this session
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

# ── Python ────────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "  Python 3 not found. Installing…"
  brew install python
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  ✓ Python $PY_VER found."

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "$SPEAKR_DIR/.venv" ]; then
  echo "  Creating virtual environment…"
  python3 -m venv "$SPEAKR_DIR/.venv"
fi

source "$SPEAKR_DIR/.venv/bin/activate"
echo "  Installing Python dependencies…"
pip install -q --upgrade pip
pip install -q -r "$SPEAKR_DIR/requirements.txt"
echo "  ✓ Dependencies installed."

# ── Shell alias ───────────────────────────────────────────────────────────────
ALIAS_LINE="alias speakr='cd $SPEAKR_DIR && source .venv/bin/activate && python speakr.py'"
SHELL_RC="$HOME/.zshrc"
[ -n "${BASH_VERSION:-}" ] && SHELL_RC="$HOME/.bashrc"

if ! grep -q "alias speakr=" "$SHELL_RC" 2>/dev/null; then
  echo "" >> "$SHELL_RC"
  echo "# speakr: free local voice dictation" >> "$SHELL_RC"
  echo "$ALIAS_LINE" >> "$SHELL_RC"
  echo "  ✓ Added 'speakr' command to $SHELL_RC (restart terminal or run: source $SHELL_RC)"
else
  echo "  ✓ 'speakr' alias already in $SHELL_RC."
fi

# ── One-time permission instructions ─────────────────────────────────────────
echo ""
echo "  ─── One-time macOS permission (required) ─────────────────────────────"
echo ""
echo "  System Settings → Privacy & Security → Accessibility"
echo "  Click + and add your terminal app (Terminal, iTerm2, Warp, etc.)"
echo ""
echo "  Microphone: macOS will prompt automatically on first run."
echo ""
echo "  ─── Done! ────────────────────────────────────────────────────────────"
echo ""
echo "  Run Speakr:"
echo "    speakr"
echo ""
echo "  Or directly:"
echo "    cd $SPEAKR_DIR && source .venv/bin/activate && python speakr.py"
echo ""
echo "  Hold Right Option (⌥) anywhere to record. Release to paste."
echo ""
