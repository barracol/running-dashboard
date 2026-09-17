#!/bin/sh
set -eu
DATA_DIR="${RUNNING_DATA_DIR:-/data}"
BACKUP_DIR="${RUNNING_BACKUP_DIR:-/backups}"
KEEP_DAYS="${RUNNING_BACKUP_KEEP_DAYS:-30}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
sqlite3 "$DATA_DIR/running.db" ".backup '$BACKUP_DIR/running-$STAMP.db'"
tar -czf "$BACKUP_DIR/uploads-$STAMP.tar.gz" -C "$DATA_DIR" uploads
find "$BACKUP_DIR" -type f -mtime "+$KEEP_DAYS" -delete
echo "Backup completato: $STAMP"
