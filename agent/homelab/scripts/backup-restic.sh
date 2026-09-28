#!/usr/bin/env bash
# Backup off-machine com restic (camada 2 do esquema do Akita; camada 1 = snapshots do disco).
# Guarda configs e dados pequenos; ignora o que se baixa de novo (modelos, caches, imagens Docker).
#
#   RESTIC_REPOSITORY e RESTIC_PASSWORD_FILE vêm do .env
#   scripts/backup-restic.sh init|backup|snapshots|check
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; . "$ROOT/.env"; set +a
: "${RESTIC_REPOSITORY:?defina RESTIC_REPOSITORY no .env}"
: "${RESTIC_PASSWORD_FILE:?defina RESTIC_PASSWORD_FILE no .env}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

case "${1:-backup}" in
  init) restic init ;;
  backup)
    restic backup "$DATA_ROOT" "$ROOT/.env" "$ROOT/stacks" \
      --tag homelab --one-file-system \
      --exclude "$DATA_ROOT/ia/ollama" \
      --exclude "$DATA_ROOT/ia/framepack/hf_download" \
      --exclude "$DATA_ROOT/ia/comfyui/models" \
      --exclude "$DATA_ROOT/midia/jellyfin/cache" \
      --exclude "$DATA_ROOT/monitor/prometheus"
    restic forget --tag homelab --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune ;;
  snapshots) restic snapshots --tag homelab ;;
  check) restic check ;;
  *) echo "uso: $0 init|backup|snapshots|check" >&2; exit 1 ;;
esac
