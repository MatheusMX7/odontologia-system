#!/bin/bash
# Backup periódico do PostgreSQL (LGPD: disponibilidade e integridade dos dados).
# Agende via cron, por exemplo (todo dia às 02:30):  30 2 * * * /caminho/backend/scripts/backup.sh
# Defina DATABASE_URL_PG no formato do pg_dump: postgresql://usuario:senha@host:5432/odontologia
set -euo pipefail
DEST="${BACKUP_DIR:-$(dirname "$0")/../../backups}"; KEEP_DAYS="${KEEP_DAYS:-30}"
mkdir -p "$DEST"; chmod 700 "$DEST"
FILE="$DEST/odontologia_$(date +%Y%m%d_%H%M%S).dump"
pg_dump --format=custom --no-owner "${DATABASE_URL_PG:?defina DATABASE_URL_PG}" > "$FILE"
chmod 600 "$FILE"
# Descarte seguro: remove backups mais antigos que a política de retenção
find "$DEST" -name 'odontologia_*.dump' -mtime +"$KEEP_DAYS" -delete
echo "Backup gerado: $FILE (retenção: ${KEEP_DAYS} dias)"
