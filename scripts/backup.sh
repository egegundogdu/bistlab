#!/bin/zsh
# Database backup: backups/bistlab-YYYY-MM-DD-HHMM.sql.gz
# Restore: gunzip -c FILE | docker compose exec -T db psql -U bistlab -d bistlab
set -e
cd "$(dirname "$0")/.."
mkdir -p backups
file="backups/bistlab-$(date +%Y-%m-%d-%H%M).sql.gz"
docker compose exec -T db pg_dump -U bistlab -d bistlab | gzip > "$file"
echo "Yedek: $file ($(du -h "$file" | cut -f1))"
