#!/bin/bash
set -euo pipefail

echo ""
echo "  Speakr — free local voice dictation for macOS"
echo "  ───────────────────────────────────────────────"
echo ""

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 not found. Install via https://www.python.org or: brew install python"
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER found."

if [ ! -d ".venv" ]; then
  echo "  Creating virtual environment…"
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "  Installing dependencies (first run downloads ~74MB Whisper model on launch)…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "  ✓ Installation complete!"
echo ""
echo "  ─── Required permissions (one-time setup) ────────────────────────────"
echo ""
echo "  1. Accessibility (for global hotkeys):"
echo "     System Settings → Privacy & Security → Accessibility"
echo "     Click '+' and add your terminal app (Terminal.app, iTerm2, Warp, etc.)"
echo ""
echo "  2. Microphone: macOS will prompt automatically on first run."
echo ""
echo "  ─── Run ──────────────────────────────────────────────────────────────"
echo ""
echo "  source .venv/bin/activate && python speakr.py"
echo ""
echo "  Add a shell alias (optional):"
echo "  echo \"alias speakr='cd $(pwd) && source .venv/bin/activate && python speakr.py'\" >> ~/.zshrc"
echo ""
echo "  ─── Usage ────────────────────────────────────────────────────────────"
echo ""
echo "  Hold Right Option (⌥) to record. Release to transcribe and paste."
echo ""
echo "  Model sizes (via SPEAKR_MODEL env var):"
echo "    tiny     ~39 MB   fastest, lower accuracy"
echo "    base     ~74 MB   default — good balance"
echo "    small   ~244 MB   better accuracy"
echo "    medium  ~769 MB   great accuracy"
echo "    large-v3  1.5 GB  best accuracy"
echo ""
echo "  Example: SPEAKR_MODEL=small python speakr.py"
echo ""
