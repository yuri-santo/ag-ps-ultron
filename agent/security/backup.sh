#!/usr/bin/env bash
# Backup diário criptografado (restic) do Hermes/Ultron para o disco D:, fora do disco virtual do WSL.
set -uo pipefail
export RESTIC_REPOSITORY=${RESTIC_REPOSITORY:-/mnt/d/Backups/ultron-restic}
export RESTIC_PASSWORD_FILE=${RESTIC_PASSWORD_FILE:-/root/.config/restic/ultron.pass}
OUT=/root/ultron-local/seguranca; SNAP=/root/ultron-local/backups/db-snapshots
mkdir -p "$OUT" "$SNAP"; chmod 700 "$OUT" "$SNAP"
inicio=$(date +%s); erro=""
# bancos SQLite copiados de forma consistente (mesmo com o Hermes rodando)
for db in /root/*.db /root/.hermes/state.db /root/.hermes/profiles/*/state.db; do
  [ -f "$db" ] || continue
  dest="$SNAP/$(echo "$db" | sed 's#^/##; s#/#__#g')"
  sqlite3 "$db" ".timeout 20000" ".backup '$dest'" 2>/dev/null || erro="$erro sqlite:$db"
done
restic backup --quiet --tag diario \
  --exclude '/root/.hermes/**/audio_cache' --exclude '/root/.hermes/**/image_cache' --exclude '/root/.hermes/**/cache' \
  --exclude '/root/.hermes/**/logs' --exclude '**/node_modules' --exclude '**/__pycache__' --exclude '**/.venv' \
  --exclude '/root/.hermes/**/sandboxes' --exclude '/root/.hermes/**/state.db*' --exclude '/root/.hermes/**/*retired-wal*' --exclude '/root/.hermes/skills-reference-*' --exclude '/root/.hermes/**/*.db-wal' \
  --exclude '/opt/agent-stacks/**/models' --exclude '/opt/agent-stacks/homelab-data/_removidos-*' \
  /root/.hermes /root/ultron-local /opt/agent-stacks /root/tools/stt /root/.config/restic/README 2>"$OUT/backup.err" || erro="$erro restic_backup"
restic forget --quiet --tag diario --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune >/dev/null 2>>"$OUT/backup.err" || erro="$erro restic_forget"
if [ "$(date +%u)" = 6 ]; then restic check --read-data-subset=5% >/dev/null 2>>"$OUT/backup.err" || erro="$erro restic_check"; fi
ultimo=$(restic snapshots --latest 1 --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); s=d[-1] if d else {}; print(json.dumps({'id': s.get('short_id'), 'hora': s.get('time','')[:19]}))" 2>/dev/null || echo '{}')
stats=$(restic stats --mode raw-data --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(round(d.get('total_size',0)/1e9,2))" 2>/dev/null || echo null)
python3 - "$OUT/backup.json" "$ultimo" "$stats" "$erro" "$(( $(date +%s) - inicio ))" <<'PY'
import json, sys, time, os
path, ultimo, tamanho, erro, dur = sys.argv[1:]
data = {'data': time.strftime('%Y-%m-%dT%H:%M:%S'), 'repositorio': os.environ.get('RESTIC_REPOSITORY'), 'ultimo_snapshot': json.loads(ultimo or '{}'),
        'tamanho_armazenado_gb': None if tamanho == 'null' else float(tamanho), 'erros': erro.split(), 'duracao_s': int(dur), 'ok': not erro.strip()}
open(path, 'w').write(json.dumps(data, ensure_ascii=False, indent=1)); os.chmod(path, 0o600)
print(json.dumps(data, ensure_ascii=False))
PY
if [ -n "$erro" ]; then
  PYTHONPATH=/root/.hermes/plugins python3 -c "
from ultron_lab.monitor import telegram_from_env
t = telegram_from_env('/root/.hermes')
t and t.send('Backup diário do Ultron falhou: $erro. Detalhes em /root/ultron-local/seguranca/backup.err')" 2>/dev/null
  exit 1
fi
