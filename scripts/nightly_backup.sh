#!/bin/zsh
# Called daily by launchd: back up the database, keep the last KEEP backups, log the result.
# If Docker is down the backup is skipped and logged; 7 skipped days in a row raise YD-02 in the self-audit.
set -u
ROOT="${0:A:h:h}"
cd "$ROOT" || exit 1
mkdir -p backups
LOG="$ROOT/backups/nightly.log"
KEEP=14
stamp() { date "+%Y-%m-%d %H:%M:%S"; }

if ! docker info >/dev/null 2>&1; then
  echo "$(stamp) SKIPPED: Docker is not running" >> "$LOG"
  exit 0
fi
docker compose up -d db >> "$LOG" 2>&1 < /dev/null
sleep 5
if ./scripts/backup.sh >> "$LOG" 2>&1 < /dev/null; then
  echo "$(stamp) OK: $(ls -t backups/bistlab-*.sql.gz | head -1)" >> "$LOG"
else
  echo "$(stamp) ERROR: backup.sh failed" >> "$LOG"
  exit 1
fi
ls -t backups/bistlab-*.sql.gz | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f -- "$old" && echo "$(stamp) eski yedek silindi: $old" >> "$LOG"
done
