#!/usr/bin/env bash
# =============================================================================
#  sync-repo.sh — sobe TUDO do Ultron para o GitHub com UM comando.
#
#  Roda dentro do WSL do Ultron (root). Faz, em sequência:
#    1) reconstrói a árvore do repositório a partir das fontes vivas
#       (plugins, /root/tools em CÓDIGO, perfis, painel, homelab);
#    2) dumpa o ESQUEMA dos bancos (estrutura, ZERO dados);
#    3) sanitiza (troca e-mails/IPs/hostnames/telegram-id/tokens por placeholder);
#    4) GUARDA DE SEGREDOS — aborta se sobrar qualquer segredo de verdade;
#    5) clona o ag-ps-ultron pela deploy key, aplica, commita e faz push.
#
#  Uso:
#      bash /root/.hermes/ultron-repo/sync-repo.sh
#      bash sync-repo.sh --dry-run     # faz tudo menos o push
#
#  REGRA DE OURO: código e ESQUEMA sobem; dado pessoal, segredo, cookie,
#  token e banco (.db) NÃO. Se a guarda achar algo, o push não sai.
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Config (ajuste só se mudar de máquina)
# ---------------------------------------------------------------------------
REPO_SSH="git@github.com:yuri-santo/ag-ps-ultron.git"
SSH_CONFIG="/root/.hermes/ultron-repo/ssh_config"   # aponta p/ a deploy key (443)
WORK="/root/.hermes/ultron-repo"                     # base de trabalho
STAGE="$WORK/stage"                                  # árvore reconstruída
CLONE="$WORK/clone"                                  # repositório clonado
LOG="$WORK/logs/sync-$(date +%Y%m%d-%H%M%S).txt"
H="/root/.hermes"

# Fontes de CÓDIGO (copiadas por inteiro, menos exclusões). "ORIGEM::DESTINO".
SOURCES=(
  "$H/plugins/harvey_juridico::agent/plugins/harvey_juridico"
  "$H/plugins/ultron_agentes::agent/plugins/ultron_agentes"
  "$H/plugins/ultron_lab::agent/plugins/ultron_lab"
  "$H/plugins/ultron_team::agent/plugins/ultron_team"
  "$H/plugins/ultron_local::agent/plugins/ultron_local"
  "$H/plugins/meeting_copilot::agent/plugins/meeting_copilot"
  "$H/plugins/a_team_workflow::agent/plugins/a_team_workflow"
  "/root/ultron-local/review::agent/review"
  "/root/ultron-local/meeting::agent/meeting"
  "/root/ultron-local/stt::agent/stt"
  "/root/ultron-local/security::agent/security"
  "/root/ultron-local/juridico::agent/juridico"
  "/root/ultron-local/homelab::agent/homelab"
  "/root/ultron-local/skills::agent/skills"
  "/root/ultron-local/scripts::agent/scripts"
  "/mnt/d/GIT/streamdeck::panel"
)

# /root/tools entra SÓ como código (varredura por extensão, ver passo 1b).
TOOLS_SRC="/root/tools"
TOOLS_DST="agent/tools"

# Bancos cujo ESQUEMA (não os dados) queremos versionar.
SCHEMA_DBS=(
  "/root/saude_yuri.db" "/root/financas_yuri.db" "/root/agenda_yuri.db"
  "$H/memory_store.db" "$H/kanban.db" "$H/projects.db"
  "$H/meeting_copilot/meetings.db" "/root/orchestration_bus.db"
  "/root/tools/tiktok/tiktok_product_radar.db"
  "/root/tools/youtube/money_engine.db"
)

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

mkdir -p "$WORK/logs"
exec > >(tee -a "$LOG") 2>&1
say(){ printf '\n\033[1;35m» %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m! %s\033[0m\n' "$*"; }
die(){ printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
trap 'die "falhou na linha $LINENO (ver $LOG)"' ERR

say "Ultron · sync-repo  ($(date '+%F %T'))"

# Exclusões duras — nunca copiar segredo/estado/dado/lixo
EXCLUDES=(
  --exclude ".git" --exclude "__pycache__" --exclude "*.pyc"
  --exclude ".env" --exclude "*.env" --exclude "config.yaml"
  --exclude "accounts.json" --exclude "secrets*" --exclude "*.key" --exclude "*.pem"
  --exclude "id_ed25519*" --exclude "id_rsa*" --exclude "deploy_key*"
  --exclude "*cookie*" --exclude "*token*" --exclude "client_secret*"
  --exclude "credenciais*" --exclude "auth.json" --exclude "*.session"
  --exclude "*.db" --exclude "*.sqlite*" --exclude "state.db"
  --exclude "memories" --exclude "sessions" --exclude "*.log"
  --exclude "SOUL.md"                    # SOUL dos perfis = contexto pessoal
  --exclude "*venv*" --exclude "site-packages" --exclude "node_modules"
  --exclude "*.zip" --exclude "*.tmp"
)

# ---------------------------------------------------------------------------
# 1a) Reconstruir a árvore (fontes de código inteiras)
# ---------------------------------------------------------------------------
say "1a  reconstruindo a árvore em $STAGE"
rm -rf "$STAGE"; mkdir -p "$STAGE"
for pair in "${SOURCES[@]}"; do
  src="${pair%%::*}"; dst="${pair##*::}"
  if [[ ! -e "$src" ]]; then warn "fonte ausente, pulando: $src"; continue; fi
  mkdir -p "$STAGE/$dst"
  rsync -a "${EXCLUDES[@]}" "$src"/ "$STAGE/$dst"/
  echo "  ✓ $src → $dst"
done

# ---------------------------------------------------------------------------
# 1b) /root/tools: SÓ código (py/sh/md/yaml/yml/js/ps1), sem dado/segredo
# ---------------------------------------------------------------------------
say "1b  varrendo $TOOLS_SRC (só código)"
if [[ -d "$TOOLS_SRC" ]]; then
  ( cd "$TOOLS_SRC" && find . -type f \
      \( -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.yaml' -o -name '*.yml' -o -name '*.js' -o -name '*.ps1' \) \
      -not -path '*/__pycache__/*' -not -path '*venv*/*' -not -path '*/site-packages/*' \
      -not -name '*cookie*' -not -name '*token*' -not -name 'client_secret*' \
      -print0 ) | while IFS= read -r -d '' f; do
        mkdir -p "$STAGE/$TOOLS_DST/$(dirname "$f")"
        cp -a "$TOOLS_SRC/$f" "$STAGE/$TOOLS_DST/$f"
      done
  echo "  ✓ código de tools copiado ($(find "$STAGE/$TOOLS_DST" -type f 2>/dev/null | wc -l) arquivos)"
fi

# ---------------------------------------------------------------------------
# 1c) Perfis: só profile.yaml (papel), nunca SOUL.md/estado/memória
# ---------------------------------------------------------------------------
say "1c  perfis (só profile.yaml)"
for d in "$H"/profiles/*/; do
  n=$(basename "$d")
  [[ "$n" == .* ]] && continue
  if [[ -f "$d/profile.yaml" ]]; then
    mkdir -p "$STAGE/agent/profiles/$n"
    cp -a "$d/profile.yaml" "$STAGE/agent/profiles/$n/profile.yaml"
  fi
done
echo "  ✓ $(ls -d "$STAGE"/agent/profiles/*/ 2>/dev/null | wc -l) perfis"

# ---------------------------------------------------------------------------
# 2) Esquema dos bancos (estrutura, ZERO dados)
# ---------------------------------------------------------------------------
say "2  esquema dos bancos (sem dados)"
mkdir -p "$STAGE/agent/db-schemas"
if command -v sqlite3 >/dev/null; then
  for db in "${SCHEMA_DBS[@]}"; do
    [[ -f "$db" ]] || continue
    name=$(basename "$db" .db)
    { echo "-- $db — SOMENTE ESQUEMA (sem dados) — $(date -Is)";
      sqlite3 "$db" ".schema"; } > "$STAGE/agent/db-schemas/$name.sql" 2>/dev/null
    echo "  ✓ $name.sql"
  done
else warn "sqlite3 ausente — pulando esquemas"; fi

# ---------------------------------------------------------------------------
# 3) Sanitizar
# ---------------------------------------------------------------------------
say "3  sanitizando (placeholders)"
find "$STAGE" -type f \( -name "*.py" -o -name "*.md" -o -name "*.js" \
  -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.sh" \
  -o -name "*.ps1" -o -name "*.sql" -o -name "*.env.example" -o -name "*.txt" \) -print0 \
| while IFS= read -r -d '' f; do
    sed -i -E \
      -e 's/[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook|easysapers)[A-Za-z0-9.-]*/SEU_EMAIL@exemplo.com/g' \
      -e 's/\b[0-9]{7,10}(:AA[A-Za-z0-9_-]{20,})/SEU_TELEGRAM_ID\1/g' \
      -e 's/\bAA[A-Za-z0-9_-]{30,}\b/SEU_BOT_TOKEN/g' \
      -e 's/\b(sk|pk|ghp|gho|xoxb|xoxp|AIza)[-_][A-Za-z0-9_-]{16,}/SEU_TOKEN/g' \
      -e 's/\b23\.21\.118\.175\b/VPS_WINDOWS_IP/g' \
      -e 's/\b10\.(99|200)\.[0-9]{1,3}\.[0-9]{1,3}\b/10.x.x.x/g' \
      -e 's/192\.168\.[0-9]{1,3}\.[0-9]{1,3}/192.168.x.x/g' \
      -e 's/\b10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b/10.x.x.x/g' \
      -e 's/EC2AMAZ-[A-Z0-9]+/EC2_HOST/g' \
      "$f"
  done
echo "  ✓ sanitização aplicada"

# ---------------------------------------------------------------------------
# 4) GUARDA DE SEGREDOS — aborta se sobrar algo real
# ---------------------------------------------------------------------------
say "4  guarda de segredos"
PATTERNS=(
  'AA[A-Za-z0-9_-]{30,}'                         # bot token telegram
  '(sk|ghp|gho|xoxb|xoxp)-[A-Za-z0-9]{16,}'      # openai/github/slack
  'AIza[A-Za-z0-9_-]{20,}'                        # google api key
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  '[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook)\.[A-Za-z]{2,}'
  '(password|passwd|secret|api_key|apikey)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"' ]{6,}'
  '23\.21\.118\.175'
)
HITS=0
for p in "${PATTERNS[@]}"; do
  if grep -RInE "$p" "$STAGE" 2>/dev/null | grep -v 'SEU_\|exemplo\|placeholder\|VPS_WINDOWS_IP'; then
    warn "possível segredo: /$p/"; HITS=$((HITS+1))
  fi
done
[[ "$HITS" -gt 0 ]] && die "guarda de segredos bloqueou o push ($HITS padrão(ões)). Corrija a fonte e rode de novo."
echo "  ✓ nada de segredo encontrado"

# ---------------------------------------------------------------------------
# 5) Clonar, aplicar, commitar, push
# ---------------------------------------------------------------------------
say "5  publicando no ag-ps-ultron"
export GIT_SSH_COMMAND="ssh -F $SSH_CONFIG"
rm -rf "$CLONE"
git clone --depth 1 "$REPO_SSH" "$CLONE"

# Substitui só o que foi reconstruído; preserva docs de topo, assets/ e docs/.
for d in agent/plugins agent/review agent/meeting agent/stt agent/security \
         agent/juridico agent/homelab agent/skills agent/scripts agent/tools \
         agent/profiles agent/db-schemas panel; do
  [[ -d "$STAGE/$d" ]] || continue
  rm -rf "${CLONE:?}/$d"; mkdir -p "$(dirname "$CLONE/$d")"; cp -a "$STAGE/$d" "$CLONE/$d"
done

cd "$CLONE"
git add -A
if git diff --cached --quiet; then
  echo "  ✓ nada mudou — repositório já está atualizado"; exit 0
fi
git -c user.name='Ultron' -c user.email='ultron@localhost' \
    commit -m "sync: retrato completo do agente $(date '+%F %H:%M')"

if [[ "$DRY_RUN" == "1" ]]; then
  warn "--dry-run: commit local feito, push NÃO enviado."
  git --no-pager show --stat --oneline HEAD | head -60; exit 0
fi
git push origin HEAD
echo "  ✓ push enviado"
git --no-pager log --oneline -1
say "pronto. log em $LOG"
