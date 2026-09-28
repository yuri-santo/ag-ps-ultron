#!/usr/bin/env bash
# Upscale com Real-ESRGAN em container (NVIDIA), baseado no Dockerfile do fork do Akita.
#
#   scripts/upscale.sh foto <pasta_entrada> <pasta_saida> [modelo]
#   scripts/upscale.sh video <arquivo.mp4> <pasta_saida> [modelo]
#
# Modelos: RealESRGAN_x4plus (foto real, padrão) | RealESRGAN_x4plus_anime_6B (anime/mangá)
#          realesr-animevideov3 (vídeo de anime)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; . "$ROOT/.env"; set +a; }
VENDOR="${VENDOR_ROOT:-$ROOT/vendor}"
IMAGE=homelab/realesrgan:local

modo="${1:-}"; entrada="${2:-}"; saida="${3:-}"; modelo="${4:-}"
[[ -n "$modo" && -n "$entrada" && -n "$saida" ]] || { sed -n '2,8p' "$0"; exit 1; }
[[ -e "$entrada" ]] || { echo "entrada não existe: $entrada" >&2; exit 1; }
mkdir -p "$saida"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  [[ -d "$VENDOR/Real-ESRGAN" ]] || { echo "rode scripts/clonar-vendors.sh antes" >&2; exit 1; }
  docker build -t "$IMAGE" "$VENDOR/Real-ESRGAN"
fi

PESOS="${DATA_ROOT:-$ROOT/data}/ia/realesrgan-weights"   # pesos baixados na 1ª execução ficam em cache
mkdir -p "$PESOS"
run() {
  docker run --rm --gpus all -v "$1":/app/inputs:ro -v "$(realpath "$saida")":/app/results \
    -v "$PESOS":/app/weights "$IMAGE" "${@:2}"
}

case "$modo" in
  foto)
    run "$(realpath "$entrada")" python3 inference_realesrgan.py -i /app/inputs -o /app/results \
      -n "${modelo:-RealESRGAN_x4plus}" ;;
  video)
    nome="$(basename "$entrada")"
    run "$(realpath "$(dirname "$entrada")")" python3 inference_realesrgan_video.py \
      -i "/app/inputs/$nome" -o /app/results -n "${modelo:-realesr-animevideov3}" ;;
  *) echo "modo inválido: $modo (foto|video)" >&2; exit 1 ;;
esac
echo "Resultado em $saida"
