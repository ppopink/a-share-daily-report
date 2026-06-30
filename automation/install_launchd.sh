#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/lisijia/Desktop/k线选股"
AGENT_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$PROJECT_DIR/automation/logs"
PLISTS=(
  "com.ppopink.ashare.intraday.plist"
  "com.ppopink.ashare.close.plist"
)

mkdir -p "$AGENT_DIR"
mkdir -p "$LOG_DIR"

chmod +x "$PROJECT_DIR/automation/run_auto_report.py"

for plist in "${PLISTS[@]}"; do
  src="$PROJECT_DIR/automation/$plist"
  dst="$AGENT_DIR/$plist"
  label="${plist%.plist}"

  echo "Installing $label"
  cp "$src" "$dst"

  launchctl bootout "gui/$(id -u)" "$dst" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$dst"
  launchctl enable "gui/$(id -u)/$label"
done

echo
echo "Installed launchd jobs:"
launchctl print "gui/$(id -u)" | grep "com.ppopink.ashare" || true
echo
echo "Logs:"
echo "  $LOG_DIR/intraday.log"
echo "  $LOG_DIR/close.log"
