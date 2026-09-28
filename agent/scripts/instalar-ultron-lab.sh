#!/usr/bin/env bash
# Repara o painel do Hermes, instala o ultron_lab e sobe o homelab leve no WSL Debian.
# Disparado por iniciar-instalacao.sh via systemd-run (sobrevive ao reinício do gateway).
set -uo pipefail
REPO=/mnt/c/Users/yurim/ultron-team-20260913
HOME_H=/root/.hermes
LAB=/opt/agent-stacks/homelab
TS=$(date +%Y%m%dT%H%M%S)
LOG="$REPO/wsl/logs/instalacao-$TS.log"
mkdir -p "$REPO/wsl/logs"
exec > >(tee -a "$LOG") 2>&1
passo() { echo; echo "######## $*  ($(date +%T))"; }
falha() { echo "FALHOU: $*"; echo "RESULTADO=falhou etapa=\"$*\" log=$LOG" > "$REPO/wsl/logs/ultimo-resultado.txt"; exit 1; }
mem_livre() { awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo; }
export PYTHONDONTWRITEBYTECODE=1

[[ $(id -u) -eq 0 ]] || falha "rode como root"
[[ -f $HOME_H/config.yaml ]] || falha "não achei $HOME_H/config.yaml"

passo "0. Painel do Hermes (127.0.0.1:9119) e diagnóstico da transcrição"
echo "Sessões de chat do painel abertas (TUI):"; pgrep -af "ui-tui/dist/entry.js|tui_gateway.entry" | cut -c1-160
echo "Erros recentes do painel:"
journalctl -u hermes-dashboard --since "-4h" --no-pager 2>/dev/null | grep -iE "transcri|timeout|error|exception|stt|whisper" | tail -25 | cut -c1-260
if curl -fsS -m 8 -o /dev/null http://127.0.0.1:9119/; then
  echo "Painel respondendo."
else
  echo "Painel travado: reiniciando hermes-dashboard.service (não mexe no gateway/Telegram)."
  systemctl restart hermes-dashboard.service
  for i in $(seq 1 30); do curl -fsS -m 4 -o /dev/null http://127.0.0.1:9119/ && break; sleep 2; done
  curl -fsS -m 4 -o /dev/null http://127.0.0.1:9119/ && echo "Painel voltou." || echo "AVISO: painel ainda não respondeu."
fi

passo "1. Python do Hermes"
PY=""
GPID=$(systemctl show -p MainPID --value hermes-gateway.service 2>/dev/null)
if [[ -n "$GPID" && "$GPID" != 0 ]]; then
  cand=$(tr '\0' '\n' < /proc/$GPID/cmdline | head -1)
  "$cand" -c "import yaml" 2>/dev/null && PY=$cand
fi
for cand in /opt/hermes-agent-20260924/venv/bin/python /usr/local/lib/hermes-agent/venv/bin/python; do
  [[ -z "$PY" && -x $cand ]] && "$cand" -c "import yaml" 2>/dev/null && PY=$cand
done
[[ -n "$PY" ]] || falha "não achei o Python do Hermes com PyYAML"
echo "Python do Hermes: $PY ($($PY --version 2>&1)); gateway PID $GPID"
"$PY" - <<'PY'
import yaml, json
c = yaml.safe_load(open('/root/.hermes/config.yaml'))
p = c.get('plugins') or {}
print('plugins.enabled:', p.get('enabled'))
print('mcp_servers:', list((c.get('mcp_servers') or {}).keys()))
print('platform_toolsets:', json.dumps(c.get('platform_toolsets'), ensure_ascii=False)[:600])
PY

passo "2. Testes (ultron_team + ultron_lab)"
cd "$REPO" || falha "repo"
"$PY" -m unittest discover -s tests -q || falha "testes"

passo "3. deploy_lab stage"
"$PY" deploy_lab.py stage --dry-run >/dev/null || falha "stage dry-run"
"$PY" deploy_lab.py stage || falha "stage"
passo "4. deploy_lab activate"
"$PY" deploy_lab.py activate --dry-run >/dev/null || falha "activate dry-run"
"$PY" deploy_lab.py activate || falha "activate"

passo "5. Homelab em $LAB (RAM livre: $(mem_livre) MB)"
HOMELAB=nao
SUBIU=""
if command -v docker >/dev/null; then
  HOMELAB=sim
  if [[ -d $LAB && ! -f $LAB/.ultron-lab-managed ]]; then falha "$LAB existe e não é gerenciado pelo ultron-lab"; fi
  mkdir -p "$LAB"
  cp -r "$REPO/homelab/." "$LAB/"
  find "$LAB/scripts" -name '*.sh' -exec sed -i 's/\r$//' {} + -exec chmod 755 {} +
  echo 20260927 > "$LAB/.ultron-lab-managed"
  if [[ ! -f $LAB/.env ]]; then
    cp "$LAB/cenarios/pc.env.example" "$LAB/.env"
    sed -i "s|^FRANK_TYPE_SECRET=.*|FRANK_TYPE_SECRET=$(openssl rand -hex 64)|" "$LAB/.env"
    if docker info 2>/dev/null | grep -qi 'runtimes:.*nvidia'; then sed -i 's|^GPU=.*|GPU=nvidia|' "$LAB/.env"; fi
    echo ".env criado ($(grep '^GPU=' $LAB/.env))."
  else
    echo ".env já existia: mantido."
  fi
  chmod 600 "$LAB/.env"
  bash "$LAB/scripts/homelab.sh" check || falha "compose check"
  for s in core ia arquivos seguranca diversao; do
    livre=$(mem_livre)
    if (( livre < 1200 )); then echo "RAM livre ${livre} MB < 1200: stack $s e seguintes ficam para depois."; break; fi
    passo "5.$s up (RAM livre ${livre} MB)"
    if bash "$LAB/scripts/homelab.sh" up "$s"; then SUBIU="$SUBIU $s"; else echo "AVISO: stack $s não subiu por completo"; fi
  done
  sleep 10
  docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'uptime-kuma|portainer|ai-memory|syncthing|frankmd|vaultwarden|frank-type'
  echo "RAM livre depois: $(mem_livre) MB"
fi

passo "6. ai-memory como MCP do Hermes"
MCP=nao
for i in $(seq 1 30); do curl -fsS -m 3 http://127.0.0.1:49374/healthz >/dev/null 2>&1 && break; sleep 2; done
if curl -fsS -m 3 http://127.0.0.1:49374/healthz >/dev/null 2>&1; then
  if "$PY" -c "import mcp" 2>/dev/null; then
    "$PY" - <<'PY' && MCP=sim
import shutil, time, yaml
from pathlib import Path
path = Path('/root/.hermes/config.yaml')
config = yaml.safe_load(path.read_text()) or {}
servers = config.get('mcp_servers') or {}
config['mcp_servers'] = servers
if 'ai_memory' not in servers:
    backup = path.with_name('config.yaml.bak-ai-memory-' + time.strftime('%Y%m%dT%H%M%S'))
    shutil.copy2(path, backup)
    servers['ai_memory'] = {'url': 'http://127.0.0.1:49374/mcp', 'tools': {'include': [
        'memory_briefing', 'memory_query', 'memory_read_page', 'memory_recent', 'memory_status',
        'memory_handoff_list', 'memory_handoff_accept', 'memory_handoff_begin', 'memory_write_page']}}
    rendered = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    yaml.safe_load(rendered)
    tmp = path.with_name('.config.yaml.ai-memory.tmp'); tmp.write_text(rendered); tmp.chmod(0o600); tmp.replace(path)
    print('mcp_servers.ai_memory adicionado; backup em', backup)
else:
    print('mcp_servers.ai_memory já existia')
PY
  else
    echo "Pacote 'mcp' ausente no Python do Hermes: MCP do ai-memory não configurado."
  fi
else
  echo "ai-memory não respondeu em /healthz: MCP não configurado."
fi

passo "7. Reiniciar o gateway (Telegram cai por alguns segundos)"
RESTART=nao
INICIO=$(date '+%Y-%m-%d %H:%M:%S')
if systemctl restart hermes-gateway.service; then RESTART=systemd; fi
for i in $(seq 1 30); do systemctl is-active --quiet hermes-gateway.service && break; sleep 2; done
sleep 15
echo "gateway: $(systemctl is-active hermes-gateway.service)"
journalctl -u hermes-gateway --since "$INICIO" --no-pager 2>/dev/null | grep -iE "ultron_lab|plugin.*(load|error|fail)|Traceback|mcp.*ai_memory" | tail -30 | cut -c1-260

passo "8. Verificação do plugin instalado no ambiente real"
"$PY" - <<'PY'
import json, sys, types
sys.path.insert(0, '/root/.hermes/plugins')
sys.modules['hermes_constants'] = types.SimpleNamespace(get_hermes_home=lambda: '/root/.hermes')
import yaml
settings = yaml.safe_load(open('/root/.hermes/config.yaml'))['plugins']['entries']['ultron_lab']['settings']
class Ctx:
    tools = {}
    def get_config(self, k, d=None): return settings.get(k, d)
    def register_tool(self, **kw): self.tools[kw['name']] = kw
    def register_system_prompt_section(self, *a, **k): pass
import ultron_lab
ctx = Ctx(); ultron_lab.register(ctx)
print('ferramentas:', sorted(ctx.tools))
g = json.loads(ctx.tools['ultron_golpe']['handler']({'texto': 'Oi mãe, mudei de número, me faz um pix agora?'}))
print('ultron_golpe:', g['status'], g['score'], g['veredito'])
h = json.loads(ctx.tools['ultron_homelab']['handler']({}))
print('ultron_homelab:', h.get('status'), 'no ar', h.get('no_ar'), 'fora', h.get('fora'))
PY
echo "painel: $(curl -fsS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:9119/ 2>&1)"

echo "RESULTADO=ok homelab=$HOMELAB stacks=[${SUBIU# }] mcp=$MCP reinicio=$RESTART log=$LOG" | tee "$REPO/wsl/logs/ultimo-resultado.txt"
