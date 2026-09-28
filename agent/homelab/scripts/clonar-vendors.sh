#!/usr/bin/env bash
# Clona (ou atualiza) os repositórios do Akita que o homelab constrói localmente.
# Revise o código antes do primeiro build: é software de terceiros rodando com GPU.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; . "$ROOT/.env"; set +a; }
VENDOR="${VENDOR_ROOT:-$ROOT/vendor}"
mkdir -p "$VENDOR"

REPOS=(
  FramePack-Docker-CUDA            # vídeo a partir de imagem (NVIDIA)
  ComfyUI-Docker-CUDA-preloaded    # ComfyUI em container (servidor)
  Real-ESRGAN                      # upscale de imagem/vídeo (scripts/upscale.sh)
  Batch-Anime-Upscaler-Video2K-Docker-CUDA  # upscale de vídeos em lote
  FrankSherlock                    # indexador de fotos com IA (app desktop / build)
  FrankMega                        # compartilhamento de arquivos com link temporário (Rails)
)

for repo in "${REPOS[@]}"; do
  dest="$VENDOR/$repo"
  if [[ -d "$dest/.git" ]]; then
    echo "== atualizando $repo"; git -C "$dest" pull --ff-only
  else
    echo "== clonando $repo"; git clone --depth 1 "https://github.com/akitaonrails/$repo.git" "$dest"
  fi
done
echo "Vendors em $VENDOR"
