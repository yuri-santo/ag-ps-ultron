#!/usr/bin/env bash
# Atualiza o plugin ultron_lab (sem mexer no homelab), roda o monitor uma vez e recarrega o gateway em 150 s.
set -uo pipefail
REPO=/mnt/c/Users/yurim/ultron-team-20260913
TS=$(date +%Y%m%dT%H%M%S)
LOG="$REPO/wsl/logs/atualizar-$TS.log"
exec > >(tee -a "$LOG") 2>&1
export PYTHONDONTWRITEBYTECODE=1
GPID=$(systemctl show -p MainPID --value hermes-gateway.service)
PY=$(tr '\0' '\n' < /proc/$GPID/cmdline | head -1)
"$PY" -c "import yaml" 2>/dev/null || PY=/opt/hermes-agent-20260924/venv/bin/python
cd "$REPO" && "$PY" -m unittest discover -s tests -q || { echo "RESULTADO_ATUALIZAR=falhou testes"; exit 1; }
"$PY" deploy_lab.py stage | grep -E '"changed"|ultron_lab"' | head -3
systemctl start ultron-lab-monitor.service
journalctl -u ultron-lab-monitor.service -n 3 --no-pager | grep alvo | tail -1 | cut -c1-400
PYTHONPATH=/root/.hermes/plugins /usr/local/bin/python3 - <<'PY'
import json
from pathlib import Path
e = json.loads(Path('/root/.hermes/ultron_lab/monitor_estado.json').read_text())
print('email (linha de base, mensagens vistas por conta):', {k: len(v.get('vistos', [])) for k, v in (e.get('email') or {}).items()})
PY
systemd-run --on-active=150 --unit="ultron-lab-restart-$TS" /bin/systemctl restart hermes-gateway.service >/dev/null && echo "reinício do gateway agendado"
echo "RESULTADO_ATUALIZAR=ok log=$LOG"
