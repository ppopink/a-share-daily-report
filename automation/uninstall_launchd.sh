#!/bin/bash
set -euo pipefail

AGENT_DIR="$HOME/Library/LaunchAgents"
PLISTS=(
  "com.ppopink.ashare.intraday.plist"
  "com.ppopink.ashare.close.plist"
)

for plist in "${PLISTS[@]}"; do
  dst="$AGENT_DIR/$plist"
  label="${plist%.plist}"
  echo "Uninstalling $label"
  launchctl bootout "gui/$(id -u)" "$dst" >/dev/null 2>&1 || true
  rm -f "$dst"
done

echo "Done."
