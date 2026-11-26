#!/bin/zsh
# launchd tarafından her gün çağrılır: veritabanı yedeği al, son KEEP yedeği tut, sonucu kaydet.
# Docker kapalıysa yedek atlanır ve kaydedilir; 7 gün üst üste atlanırsa öz denetimde YD-02 bulgu verir.
set -u
ROOT="${0:A:h:h}"
cd "$ROOT" || exit 1
mkdir -p backups
LOG="$ROOT/backups/nightly.log"
KEEP=14
stamp() { date "+%Y-%m-%d %H:%M:%S"; }

if ! docker info >/dev/null 2>&1; then
  echo "$(stamp) ATLANDI: Docker çalışmıyor" >> "$LOG"
  exit 0
fi
docker compose up -d db >> "$LOG" 2>&1 < /dev/null
sleep 5
if ./scripts/backup.sh >> "$LOG" 2>&1 < /dev/null; then
  echo "$(stamp) OK: $(ls -t backups/bistlab-*.sql.gz | head -1)" >> "$LOG"
else
  echo "$(stamp) HATA: backup.sh başarısız" >> "$LOG"
  exit 1
fi
ls -t backups/bistlab-*.sql.gz | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f -- "$old" && echo "$(stamp) eski yedek silindi: $old" >> "$LOG"
done
