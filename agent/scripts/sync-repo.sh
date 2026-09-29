#!/usr/bin/env bash
# =============================================================================
#  sync-repo.sh — sobe TUDO do Ultron para o GitHub com UM comando.
#
#  Roda dentro do WSL do Ultron (root). Faz, em sequência:
#    1) reconstrói a árvore (plugins, /root/tools em CÓDIGO, perfis, painel, homelab);
#    2) dumpa o ESQUEMA dos bancos (estrutura, ZERO dados);
#    3) sanitiza — troca por placeholders/exemplos: e-mails, IPs, hostnames,
#       telegram-id, tokens, NOME DA EMPRESA (→ "profissional") e nomes de cliente;
#    4) GUARDA DE SEGREDOS + RELATÓRIO DE INFO PESSOAL — aborta se sobrar algo;
#    5) clona o ag-ps-ultron pela deploy key, aplica, commita e faz push.
#
#  Uso:
#      bash /root/.hermes/ultron-repo/sync-repo.sh
#      bash sync-repo.sh --dry-run     # faz tudo menos o push
#
#  REGRA DE OURO: código e ESQUEMA sobem; dado pessoal, segredo, cookie, token,
#  nome de empresa/cliente e banco (.db) NÃO. Se a guarda achar algo, não sobe.
# =============================================================================
set -Eeuo pipefail

REPO_SSH="git@github.com:yuri-santo/ag-ps-ultron.git"
SSH_CONFIG="/root/.hermes/ultron-repo/ssh_config"
WORK="/root/.hermes/ultron-repo"
STAGE="$WORK/stage"; CLONE="$WORK/clone"
LOG="$WORK/logs/sync-$(date +%Y%m%d-%H%M%S).txt"
H="/root/.hermes"

SOURCES=(
  "$H/plugins/harvey_juridico::agent/plugins/harvey_juridico"
  "$H/plugins/ultron_agentes::agent/plugins/ultron_agentes"
  "$H/plugins/ultron_lab::agent/plugins/ultron_lab"
  "$H/plugins/ultron_team::agent/plugins/ultron_team"
  "$H/plugins/ultron_local::agent/plugins/ultron_local"
  "$H/plugins/meeting_copilot::agent/plugins/meeting_copilot"
  "$H/plugins/a_team_workflow::agent/plugins/a_team_workflow"
  "/root/ultron-local/meeting::agent/meeting"
  "/root/ultron-local/stt::agent/stt"
  "/root/ultron-local/security::agent/security"
  "/root/ultron-local/juridico::agent/juridico"
  "/root/ultron-local/homelab::agent/homelab"
  "/root/ultron-local/skills::agent/skills"
  "/root/ultron-local/scripts::agent/scripts"
  "/mnt/d/GIT/streamdeck::panel"
)
TOOLS_SRC="/root/tools"; TOOLS_DST="agent/tools"
SCHEMA_DBS=(
  "/root/saude_yuri.db" "/root/financas_yuri.db" "/root/agenda_yuri.db"
  "$H/memory_store.db" "$H/kanban.db" "$H/projects.db"
  "$H/meeting_copilot/meetings.db" "/root/orchestration_bus.db"
  "/root/tools/tiktok/tiktok_product_radar.db" "/root/tools/youtube/money_engine.db"
)
# Scripts que semeiam DADO PESSOAL (saúde/finanças/prontuário) — ficam de fora.
PERSONAL_SEEDERS='insert_vacinas|insert_infancia|mk_health_agenda_db|registrar_saude_manha|generate_pdf_prontuario|generate_health_summary_pdf|update_vacinas|update_filia'

DRY_RUN=0; [[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1
mkdir -p "$WORK/logs"; exec > >(tee -a "$LOG") 2>&1
say(){ printf '\n\033[1;35m» %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m! %s\033[0m\n' "$*"; }
die(){ printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
trap 'die "falhou na linha $LINENO (ver $LOG)"' ERR
say "Ultron · sync-repo ($(date '+%F %T'))"

EXCLUDES=(
  --exclude ".git" --exclude "__pycache__" --exclude "*.pyc"
  --exclude ".env" --exclude "*.env" --exclude "config.yaml"
  --exclude "accounts.json" --exclude "secrets*" --exclude "*.key" --exclude "*.pem"
  --exclude "id_ed25519*" --exclude "id_rsa*" --exclude "deploy_key*"
  --exclude "*cookie*" --exclude "*token*" --exclude "client_secret*"
  --exclude "credenciais*" --exclude "auth.json" --exclude "*.session"
  --exclude "*.db" --exclude "*.sqlite*" --exclude "state.db"
  --exclude "memories" --exclude "sessions" --exclude "*.log"
  --exclude "SOUL.md" --exclude "*venv*" --exclude "site-packages"
  --exclude "node_modules" --exclude "*.zip" --exclude "*.tmp"
)

# 1a) fontes de código inteiras
say "1a  reconstruindo em $STAGE"; rm -rf "$STAGE"; mkdir -p "$STAGE"
for pair in "${SOURCES[@]}"; do
  src="${pair%%::*}"; dst="${pair##*::}"
  [[ -e "$src" ]] || { warn "ausente: $src"; continue; }
  mkdir -p "$STAGE/$dst"; rsync -a "${EXCLUDES[@]}" "$src"/ "$STAGE/$dst"/; echo "  ✓ $dst"
done

# A revisao vive em dois lugares no Hermes atual. Atualiza apenas esses arquivos;
# testes e patches versionados em agent/review continuam preservados.
mkdir -p "$STAGE/agent/review"
cp -a /root/ultron-local/model_review.py "$STAGE/agent/review/model_review.py"
cp -a /opt/hermes-agent-20260924/agent/ultron_review_gate.py "$STAGE/agent/review/ultron_review_gate.py"

# 1b) /root/tools: só código, sem dado/segredo, sem seeders pessoais
say "1b  varrendo tools (só código)"
if [[ -d "$TOOLS_SRC" ]]; then
  ( cd "$TOOLS_SRC" && find . -type f \
      \( -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.yaml' -o -name '*.yml' -o -name '*.js' -o -name '*.ps1' \) \
      -not -path '*/__pycache__/*' -not -path '*venv*/*' -not -path '*/site-packages/*' \
      -not -name '*cookie*' -not -name '*token*' -not -name 'client_secret*' \
      -print0 ) | while IFS= read -r -d '' f; do
        base=$(basename "$f")
        echo "$base" | grep -qE "$PERSONAL_SEEDERS" && continue    # pula seeders pessoais
        mkdir -p "$STAGE/$TOOLS_DST/$(dirname "$f")"
        cp -a "$TOOLS_SRC/$f" "$STAGE/$TOOLS_DST/$f"
      done
  echo "  ✓ $(find "$STAGE/$TOOLS_DST" -type f 2>/dev/null | wc -l) arquivos de código"
fi

# 1c) perfis: só profile.yaml
say "1c  perfis (só profile.yaml)"
for d in "$H"/profiles/*/; do
  n=$(basename "$d"); [[ "$n" == .* ]] && continue
  [[ -f "$d/profile.yaml" ]] && { mkdir -p "$STAGE/agent/profiles/$n"; cp -a "$d/profile.yaml" "$STAGE/agent/profiles/$n/profile.yaml"; }
done

# 2) esquema dos bancos (sem dados)
say "2  esquema dos bancos"; mkdir -p "$STAGE/agent/db-schemas"
if command -v sqlite3 >/dev/null; then
  for db in "${SCHEMA_DBS[@]}"; do
    [[ -f "$db" ]] || continue; name=$(basename "$db" .db)
    { echo "-- $name — SOMENTE ESQUEMA (sem dados)"; sqlite3 "$db" ".schema"; } > "$STAGE/agent/db-schemas/$name.sql" 2>/dev/null
  done
fi

# 3) sanitizar (segredos + info pessoal + nome de empresa/cliente)
say "3  sanitizando"
find "$STAGE" -type f \( -name "*.py" -o -name "*.md" -o -name "*.js" -o -name "*.json" \
  -o -name "*.yaml" -o -name "*.yml" -o -name "*.sh" -o -name "*.ps1" -o -name "*.sql" \
  -o -name "*.env.example" -o -name "*.txt" \) -print0 | while IFS= read -r -d '' f; do
    sed -i -E \
      -e 's/[Ee]asy[Ss]apers/profissional/g' \
      -e 's/[Tt]yrolit/CLIENTE/g' -e 's/[Rr]izzotti/CLIENTE/g' \
      -e 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/exemplo@exemplo.com/g' \
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
# renomeia arquivos/pastas que carreguem o nome da empresa
find "$STAGE" -depth -iname '*easysapers*' | while read -r p; do
  np=$(echo "$p" | sed -E 's/[Ee]asy[Ss]apers/profissional/g'); [[ "$p" != "$np" ]] && mv -n "$p" "$np"
done
echo "  ✓ sanitização + renome aplicados"

# 4) guarda de segredos + relatório de info pessoal
say "4  guarda de segredos + info pessoal"
SECRET_PATTERNS=(
  'AA[A-Za-z0-9_-]{30,}' '(sk|ghp|gho|xoxb|xoxp)-[A-Za-z0-9]{16,}' 'AIza[A-Za-z0-9_-]{20,}'
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  '(password|passwd|secret|api_key|apikey)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"' ]{6,}'
  '23\.21\.118\.175'
)
PERSONAL_PATTERNS=( '[Ee]asy[Ss]apers' '[Tt]yrolit' '[Rr]izzotti'
  '[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook)\.[A-Za-z]{2,}' )
HITS=0
for p in "${SECRET_PATTERNS[@]}" "${PERSONAL_PATTERNS[@]}"; do
  if grep -RInE "$p" "$STAGE" 2>/dev/null | grep -v 'SEU_\|exemplo\|placeholder\|VPS_WINDOWS_IP\|CLIENTE\|profissional'; then
    warn "resíduo: /$p/"; HITS=$((HITS+1))
  fi
done
[[ "$HITS" -gt 0 ]] && die "bloqueado ($HITS padrão(ões) sobraram). Corrija a fonte/regra e rode de novo."
echo "  ✓ nada sensível encontrado"

# 5) clonar, aplicar, commitar, push (preserva docs de topo, assets/, docs/)
say "5  publicando"
export GIT_SSH_COMMAND="ssh -F $SSH_CONFIG"; rm -rf "$CLONE"
git clone --depth 1 "$REPO_SSH" "$CLONE"
for d in agent/plugins agent/meeting agent/stt agent/security \
         agent/juridico agent/homelab agent/skills agent/scripts agent/tools \
         agent/profiles agent/db-schemas panel; do
  [[ -d "$STAGE/$d" ]] || continue
  rm -rf "${CLONE:?}/$d"; mkdir -p "$(dirname "$CLONE/$d")"; cp -a "$STAGE/$d" "$CLONE/$d"
done
rsync -a "$STAGE/agent/review/" "$CLONE/agent/review/"
cd "$CLONE"; git add -A
if git diff --cached --quiet; then echo "  ✓ nada mudou"; exit 0; fi
git -c user.name='Ultron' -c user.email='ultron@localhost' commit -m "sync: retrato completo $(date '+%F %H:%M')"
if [[ "$DRY_RUN" == "1" ]]; then warn "--dry-run: sem push."; git --no-pager show --stat --oneline HEAD | head -80; exit 0; fi
git push origin HEAD; echo "  ✓ push enviado"; git --no-pager log --oneline -1
say "pronto. log em $LOG"
