#!/bin/zsh
# Installs the macOS launchd agent for daily backups. Usage: ./scripts/install_backup_agent.sh [saat]
# To remove: launchctl bootout gui/$(id -u)/com.bistlab.backup && rm ~/Library/LaunchAgents/com.bistlab.backup.plist
set -e
ROOT="${0:A:h:h}"
LABEL=com.bistlab.backup
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HOUR=${1:-21}
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/backups"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/zsh</string><string>$ROOT/scripts/nightly_backup.sh</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$ROOT/backups/launchd.out</string>
  <key>StandardErrorPath</key><string>$ROOT/backups/launchd.err</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed: daily at $HOUR:00 — $PLIST"
