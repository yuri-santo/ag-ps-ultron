#!/usr/bin/env bash
# =============================================================================
#  sync-repo.sh — sobe TUDO do Ultron para o GitHub com UM comando.
#
#  Roda dentro do WSL do Ultron (root). Faz, em sequência:
#    1) reconstrói a árvore do repositório a partir das fontes vivas;
#    2) sanitiza (troca e-mails/IPs/hostnames/telegram-id reais por placeholder);
#    3) GUARDA DE SEGREDOS — aborta se sobrar qualquer segredo de verdade;
#    4) clona o ag-ps-ultron pela deploy key, aplica, commita e faz push.
#
#  Uso:
#      bash /root/.hermes/ultron-repo/sync-repo.sh
#      bash sync-repo.sh --dry-run     # faz tudo menos o push
#
#  Nada de segredo entra no repositório. Se a guarda achar algo, o push não sai.
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

# Fontes vivas (uma por linha: "ORIGEM::DESTINO_NO_REPO"). Origem ausente é
# apenas avisada, não quebra o sync.
SOURCES=(
  "/root/.hermes/plugins/harvey_juridico::agent/plugins/harvey_juridico"
  "/root/.hermes/plugins/ultron_agentes::agent/plugins/ultron_agentes"
  "/root/.hermes/plugins/ultron_lab::agent/plugins/ultron_lab"
  "/root/.hermes/plugins/ultron_team::agent/plugins/ultron_team"
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

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

mkdir -p "$WORK/logs"
exec > >(tee -a "$LOG") 2>&1
say(){ printf '\n\033[1;35m» %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m! %s\033[0m\n' "$*"; }
die(){ printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

trap 'die "falhou na linha $LINENO (ver $LOG)"' ERR

say "Ultron · sync-repo  ($(date '+%F %T'))"

# ---------------------------------------------------------------------------
# 1) Reconstruir a árvore
# ---------------------------------------------------------------------------
say "1/4  reconstruindo a árvore em $STAGE"
rm -rf "$STAGE"; mkdir -p "$STAGE"

# Exclusões duras — nunca copiar segredo/estado/lixo
EXCLUDES=(
  --exclude ".git" --exclude "__pycache__" --exclude "*.pyc"
  --exclude ".env" --exclude "*.env" --exclude "config.yaml"
  --exclude "accounts.json" --exclude "secrets*" --exclude "*.key"
  --exclude "id_ed25519" --exclude "id_rsa" --exclude "*.pem"
  --exclude "*.db" --exclude "*.sqlite*" --exclude "state.db"
  --exclude "memories" --exclude "sessions" --exclude "*.log"
  --exclude "SOUL.md"                    # SOUL dos perfis = contexto pessoal
  --exclude "*.zip" --exclude "*.tmp" --exclude "node_modules"
)

for pair in "${SOURCES[@]}"; do
  src="${pair%%::*}"; dst="${pair##*::}"
  if [[ ! -e "$src" ]]; then warn "fonte ausente, pulando: $src"; continue; fi
  mkdir -p "$STAGE/$dst"
  rsync -a "${EXCLUDES[@]}" "$src"/ "$STAGE/$dst"/
  echo "  ✓ $src → $dst"
done

# Perfis de e-mail/reunião entram SÓ como exemplo de formato (sem SOUL sensível).
# Se os 3 perfis de exemplo existirem no repo atual, mantemos os que já estão
# versionados (ver passo 4, que só substitui o que foi reconstruído).

# Docs e arquivos de topo que vivem no próprio repo (não são reconstruídos das
# fontes vivas): README, ARCHITECTURE, AGENTS, TOOLS, CREDITS, assets/, docs/.
# Eles são preservados do clone no passo 4.

# ---------------------------------------------------------------------------
# 2) Sanitizar
# ---------------------------------------------------------------------------
say "2/4  sanitizando (placeholders)"
# Ordem importa: específico → genérico.
find "$STAGE" -type f \( -name "*.py" -o -name "*.md" -o -name "*.js" \
  -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.sh" \
  -o -name "*.ps1" -o -name "*.env.example" -o -name "*.txt" \) -print0 \
| while IFS= read -r -d '' f; do
    sed -i -E \
      -e 's/[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook|easysapers)[A-Za-z0-9.-]*/SEU_EMAIL@exemplo.com/g' \
      -e 's/\b[0-9]{7,10}\b(:AA[A-Za-z0-9_-]{20,})/SEU_TELEGRAM_ID\1/g' \
      -e 's/\bAA[A-Za-z0-9_-]{30,}\b/SEU_BOT_TOKEN/g' \
      -e 's/\b(sk|pk|ghp|gho|xoxb|xoxp)-[A-Za-z0-9_-]{16,}/SEU_TOKEN/g' \
      -e 's/192\.168\.[0-9]{1,3}\.[0-9]{1,3}/192.168.x.x/g' \
      -e 's/10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/10.x.x.x/g' \
      "$f"
  done
echo "  ✓ sanitização aplicada"

# ---------------------------------------------------------------------------
# 3) GUARDA DE SEGREDOS — aborta se sobrar algo real
# ---------------------------------------------------------------------------
say "3/4  guarda de segredos"
PATTERNS=(
  'AA[A-Za-z0-9_-]{30,}'                 # bot token telegram
  '(sk|ghp|gho|xoxb|xoxp)-[A-Za-z0-9]{16,}'
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  '[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook)\.[A-Za-z]{2,}'
  'password\s*[:=]\s*["'"'"'][^"'"'"']{4,}'
)
HITS=0
for p in "${PATTERNS[@]}"; do
  if grep -RInE "$p" "$STAGE" 2>/dev/null; then
    warn "possível segredo: /$p/"
    HITS=$((HITS+1))
  fi
done
[[ "$HITS" -gt 0 ]] && die "guarda de segredos bloqueou o push ($HITS padrão(ões)). Corrija a fonte e rode de novo."
echo "  ✓ nada de segredo encontrado"

# ---------------------------------------------------------------------------
# 4) Clonar, aplicar, commitar, push
# ---------------------------------------------------------------------------
say "4/4  publicando no ag-ps-ultron"
export GIT_SSH_COMMAND="ssh -F $SSH_CONFIG"
rm -rf "$CLONE"
git clone --depth 1 "$REPO_SSH" "$CLONE"

# Substitui só o que foi reconstruído; preserva docs de topo, assets/ e docs/.
for pair in "${SOURCES[@]}"; do
  dst="${pair##*::}"
  [[ -d "$STAGE/$dst" ]] || continue
  rm -rf "${CLONE:?}/$dst"
  mkdir -p "$(dirname "$CLONE/$dst")"
  cp -a "$STAGE/$dst" "$CLONE/$dst"
done

cd "$CLONE"
git add -A
if git diff --cached --quiet; then
  echo "  ✓ nada mudou — repositório já está atualizado"; exit 0
fi

git -c user.name='Ultron' -c user.email='ultron@localhost' \
    commit -m "sync: retrato do agente $(date '+%F %H:%M')"

if [[ "$DRY_RUN" == "1" ]]; then
  warn "--dry-run: commit feito localmente, push NÃO enviado."
  git --no-pager log --oneline -1
  exit 0
fi

git push origin HEAD
echo "  ✓ push enviado"
git --no-pager log --oneline -1
say "pronto. log em $LOG"
