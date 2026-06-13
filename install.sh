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

# ── Language selection ────────────────────────────────────────────────────────
echo ""
echo "  ─── Language ─────────────────────────────────────────────────────────"
echo ""
echo "  What language do you speak? Speakr will transcribe and correct grammar"
echo "  in that language. You can change this any time in .speakr.conf"
echo ""
echo "    1) Auto-detect  (switches per recording — works for any language)"
echo "    2) English"
echo "    3) German   / Deutsch"
echo "    4) Spanish  / Español"
echo "    5) French   / Français"
echo "    6) Italian  / Italiano"
echo "    7) Portuguese / Português"
echo "    8) Dutch    / Nederlands"
echo "    9) Other    (I'll set the code manually)"
echo ""
read -rp "  Choice [1]: " lang_choice
lang_choice="${lang_choice:-1}"

case "$lang_choice" in
  1) SPEAKR_LANG="auto" ;;
  2) SPEAKR_LANG="en"   ;;
  3) SPEAKR_LANG="de"   ;;
  4) SPEAKR_LANG="es"   ;;
  5) SPEAKR_LANG="fr"   ;;
  6) SPEAKR_LANG="it"   ;;
  7) SPEAKR_LANG="pt"   ;;
  8) SPEAKR_LANG="nl"   ;;
  9)
    echo ""
    read -rp "  Enter language code (e.g. ja, zh, ko, ru, ar): " SPEAKR_LANG
    SPEAKR_LANG="${SPEAKR_LANG:-auto}"
    ;;
  *) SPEAKR_LANG="auto" ;;
esac

# Write config — env vars always override this file if set manually
cat > "$SPEAKR_DIR/.speakr.conf" <<EOF
# Speakr config — edit any time, or re-run install.sh to reconfigure
# Language codes: en de es fr it pt nl auto (or any Whisper language code)
SPEAKR_LANG=$SPEAKR_LANG
EOF

echo "  ✓ Language set to '$SPEAKR_LANG' (saved to .speakr.conf)"

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

# ── Auto-launch at login ──────────────────────────────────────────────────────
echo ""
echo "  ─── Auto-launch ──────────────────────────────────────────────────────"
echo ""
echo "  Start Speakr automatically at login? The mic icon just appears in your"
echo "  menu bar every time you boot — no need to run a command."
echo ""
read -rp "  Enable auto-launch? [Y/n]: " autostart_choice
autostart_choice="${autostart_choice:-Y}"
if [[ "$autostart_choice" =~ ^[Yy] ]]; then
  bash "$SPEAKR_DIR/autostart.sh" enable
else
  echo "  Skipped. Enable any time with: ./autostart.sh enable"
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
echo "  Change language any time: edit $SPEAKR_DIR/.speakr.conf"
echo "  Or re-run: ./install.sh"
echo ""
echo "  Hold Right Option (⌥) anywhere to record. Release to paste."
echo ""
