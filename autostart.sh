#!/bin/bash
# Speakr auto-launch toggle — starts Speakr silently at login via a LaunchAgent.
#   ./autostart.sh enable    install + start now + run at every login
#   ./autostart.sh disable   stop + remove
#   ./autostart.sh status     show current state
set -euo pipefail

SPEAKR_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.speakr.dictation"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$SPEAKR_DIR/.venv/bin/python"
UID_NUM="$(id -u)"

enable() {
  if [ ! -x "$PY" ]; then
    echo "  ✗ venv not found at $PY — run ./install.sh first."
    exit 1
  fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$SPEAKR_DIR/speakr.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SPEAKR_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>$SPEAKR_DIR/speakr.log</string>
    <key>StandardErrorPath</key>
    <string>$SPEAKR_DIR/speakr.log</string>
</dict>
</plist>
EOF
  # Reload cleanly (modern launchctl, fall back to legacy)
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>/dev/null || launchctl load -w "$PLIST"
  launchctl kickstart -k "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  echo "  ✓ Auto-launch enabled — Speakr is running now and starts at every login."
  echo ""
  echo "  If the hotkey doesn't work after a reboot, grant Accessibility to Python:"
  echo "    System Settings → Privacy & Security → Accessibility → +"
  echo "    Add this exact binary:"
  echo "      $PY"
}

disable() {
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null \
    || launchctl unload -w "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "  ✓ Auto-launch disabled and removed."
}

status() {
  if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
    echo "  Auto-launch: ENABLED (loaded)"
  elif [ -f "$PLIST" ]; then
    echo "  Auto-launch: plist present but not loaded"
  else
    echo "  Auto-launch: disabled"
  fi
}

case "${1:-}" in
  enable)  enable  ;;
  disable) disable ;;
  status)  status  ;;
  *) echo "Usage: ./autostart.sh {enable|disable|status}"; exit 1 ;;
esac
