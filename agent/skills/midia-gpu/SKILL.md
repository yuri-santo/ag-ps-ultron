---
name: midia-gpu
description: Upscale, vídeo por IA, legendas e conversão com a GPU local
version: 1.0.0
metadata:
  hermes:
    category: ultron-lab
    tags: [midia, gpu, upscale, video, ffmpeg, legendas, comfyui]
---

# Mídia com GPU no homelab

Ferramentas do Akita empacotadas no homelab de Yuri. Tudo roda no WSL Debian (cenário pc) ou no
servidor, a partir de `/opt/agent-stacks/homelab`. Trabalhos longos: avise o tempo estimado e rode em
segundo plano; não segure a conversa esperando.

## Escolha rápida

| Pedido | Ferramenta | Como |
| --- | --- | --- |
| Aumentar resolução de foto | Real-ESRGAN | `scripts/upscale.sh foto <pasta_in> <pasta_out>` |
| Foto/print de anime ou mangá | Real-ESRGAN anime | `scripts/upscale.sh foto <in> <out> RealESRGAN_x4plus_anime_6B` |
| Vídeo de anime em lote | Video2X CUDA (Batch-Anime-Upscaler) | README do vendor; entrada/saída em pastas |
| Vídeo curto a partir de uma imagem | FramePack | `homelab.sh up ia` com perfil `gerar`; UI em http://127.0.0.1:7860 |
| Gerar/editar imagem | ComfyUI | PC: ComfyUI-Easy-Install nativo; servidor: perfil `gerar`, porta 8188 |
| Converter/cortar/comprimir vídeo | easy-ffmpeg | `easy-ffmpeg entrada.mkv mp4 --web` (ou `--compress`, `--start 1:30 --duration 90`; `--dry-run` mostra o comando) |
| Baixar/sincronizar legendas | easy-subtitle | `easy-subtitle init` (idiomas no YAML) e depois `easy-subtitle run /pasta/filmes` (extrai, baixa e sincroniza com `alass`) |

## Regras

- Confirme GPU antes de trabalho pesado: `nvidia-smi` no WSL. Sem GPU, avise que vai ser lento ou inviável.
- Primeira execução baixa modelos grandes (FramePack ~30 GB; ComfyUI até ~250 GB se não enxugar
  `models.conf`). Pergunte antes de iniciar um download desses.
- Não sobrescreva originais: saída sempre em pasta separada.
- Rostos de pessoas reais: não gere nem troque rosto de terceiros sem consentimento; nada de deepfake.
- Conteúdo de terceiros (filme, anime comprado) é para uso pessoal; não publique o resultado.
- Entregue o caminho do arquivo gerado e o tamanho; se falhar, mostre as últimas linhas do log.
