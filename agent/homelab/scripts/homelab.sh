#!/usr/bin/env bash
# Orquestra os stacks do homelab com o cenário do .env (pc ou servidor).
#
#   scripts/homelab.sh up all            # sobe HOMELAB_STACKS na ordem
#   scripts/homelab.sh up ia             # um stack
#   scripts/homelab.sh ps|logs|pull|down|config <stack|all>
#   scripts/homelab.sh check             # valida .env e compose sem subir nada
#
# Roda no WSL Debian (cenário pc) ou no servidor Linux, como root ou usuário no grupo docker.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${HOMELAB_ENV:-$ROOT/.env}"
ALL_STACKS=(ia arquivos midia monitor)

die() { echo "homelab: $*" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || die "sem $ENV_FILE. Copie um cenário: cp cenarios/pc.env.example .env"
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

: "${DATA_ROOT:?DATA_ROOT vazio no .env}"
: "${PUID:?}" "${PGID:?}"
GPU="${GPU:-none}"

if [[ "${BIND:-127.0.0.1}" != "127.0.0.1" && -z "${AI_MEMORY_AUTH_TOKEN:-}" ]]; then
  die "BIND=${BIND} expõe o ai-memory na rede: defina AI_MEMORY_AUTH_TOKEN (openssl rand -hex 32)"
fi

dirs_for() {
  case "$1" in
    ia)        echo "ia/ai-memory ia/ollama ia/framepack/hf_download ia/framepack/outputs ia/comfyui/models ia/comfyui/custom_nodes ia/comfyui/output ia/comfyui/input" ;;
    arquivos)  echo "arquivos/syncthing" ;;
    midia)     echo "midia/jellyfin/config midia/jellyfin/cache" ;;
    monitor)   echo "monitor/prometheus monitor/grafana" ;;
    *)         echo "" ;;
  esac
}

prepare() {
  local stack="$1" d
  for d in $(dirs_for "$stack"); do
    [[ -d "$DATA_ROOT/$d" ]] || install -d -m 0750 -o "$PUID" -g "$PGID" "$DATA_ROOT/$d"
  done
}

compose() {
  local stack="$1"; shift
  local dir="$ROOT/stacks/$stack"
  [[ -f "$dir/compose.yml" ]] || die "stack desconhecido: $stack"
  local files=(-f "$dir/compose.yml")
  case "$GPU" in
    nvidia) [[ -f "$dir/compose.nvidia.yml" ]] && files+=(-f "$dir/compose.nvidia.yml") ;;
    rocm)   [[ -f "$dir/compose.rocm.yml" ]] && files+=(-f "$dir/compose.rocm.yml") ;;
    none)   ;;
    *)      die "GPU inválido: $GPU (use nvidia, rocm ou none)" ;;
  esac
  docker compose --env-file "$ENV_FILE" --project-directory "$dir" "${files[@]}" "$@"
}

stacks_from() {
  if [[ "$1" == all ]]; then
    # shellcheck disable=SC2086
    echo ${HOMELAB_STACKS:-ia arquivos}
  else
    echo "$1"
  fi
}

action="${1:-}"; target="${2:-all}"
case "$action" in
  up)
    for s in $(stacks_from "$target"); do prepare "$s"; echo "== up $s"; compose "$s" up -d --remove-orphans; done ;;
  down)
    for s in $(stacks_from "$target"); do echo "== down $s"; compose "$s" down; done ;;
  ps|pull|config)
    for s in $(stacks_from "$target"); do echo "== $action $s"; compose "$s" "$action"; done ;;
  logs)
    compose "$target" logs --tail=200 -f ;;
  check)
    for s in "${ALL_STACKS[@]}"; do compose "$s" config --quiet && echo "ok  $s"; done ;;
  *)
    sed -n '2,9p' "$0"; exit 1 ;;
esac
