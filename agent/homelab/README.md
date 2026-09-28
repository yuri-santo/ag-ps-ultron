# Homelab do Ultron

Esqueleto de homelab em Docker Compose inspirado no home server do Akita
("Migrando meu Home Server com Claude Code", 49 containers em 15 stacks) e nos
repositórios dele, adaptado ao ambiente do Yuri:

- **Cenário `pc` (agora):** Windows san-saitama, Docker Engine dentro do WSL **Debian**, o mesmo
  WSL onde o Hermes/Ultron roda como root. Tudo escuta em `127.0.0.1`.
- **Cenário `servidor` (futuro):** máquina Linux dedicada, mesmo layout. Migrar = backup restic +
  restore + trocar o `.env`.

Os dois cenários usam `/opt/agent-stacks/homelab` (código) e `/opt/agent-stacks/homelab-data`
(dados), seguindo a convenção `/opt/agent-stacks/<stack>` que já existe no seu WSL.

## Stacks

| Stack | Serviços | Porta (BIND) | Origem |
| --- | --- | --- | --- |
| ia | **ai-memory**, Ollama (`ollama`), FramePack e ComfyUI (`gerar`) | 49374, 11434, 7860, 8188 | ai-memory, FramePack-Docker-CUDA, ComfyUI-Docker-CUDA-preloaded |
| arquivos | Syncthing (ex.: sincronizar o cofre do Obsidian com o celular) | 7104 | home server do Akita |
| midia | Jellyfin (Immich: compose oficial) | 8096 | home server (sem o stack de torrent) |
| monitor | Prometheus, Grafana, node-exporter, cAdvisor | 7106, 7105, 7107 | post do Grafana no home server |

Entre parênteses, o perfil de compose que liga o serviço (`COMPOSE_PROFILES` no `.env`).
No PC ficam só `ia` (ai-memory) e `arquivos` (Syncthing). Uptime Kuma, Portainer, Vaultwarden, FrankMD e
Frank Type foram removidos a pedido do Yuri; os composes antigos estão em `_removidos/`.
O papel do Uptime Kuma ficou com o monitor automático do ultron_lab (alerta no Telegram).
Portas evitadas de propósito porque já estão em uso aí: 8090, 8123, 3080, 1234, 20128, 5001, 9119, 9500.

GPU entra por overlay: `GPU=nvidia` aplica `stacks/ia/compose.nvidia.yml`, `GPU=rocm` aplica
`compose.rocm.yml`, `GPU=none` roda só CPU.

## Instalar (cenário pc)

No WSL Debian, como root:

```bash
mkdir -p /opt/agent-stacks
cp -r /mnt/c/Users/yurim/ultron-team-20260913/homelab /opt/agent-stacks/homelab
cd /opt/agent-stacks/homelab
cp cenarios/pc.env.example .env && chmod 600 .env
$EDITOR .env                      # tokens, GPU
scripts/clonar-vendors.sh         # só se for usar FramePack/ComfyUI/Real-ESRGAN
scripts/homelab.sh check          # valida compose sem subir nada
scripts/homelab.sh up ia
scripts/homelab.sh up all         # sobe HOMELAB_STACKS
```

No Windows, o atalho `scripts\Homelab.ps1 up ia` chama o mesmo script dentro do WSL.

### GPU NVIDIA no WSL

1. Driver NVIDIA atualizado no Windows (não instale driver dentro do WSL).
2. No Debian: instalar `nvidia-container-toolkit`, depois
   `nvidia-ctk runtime configure --runtime=docker` e reiniciar o Docker.
3. Teste: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`.

## Ultron enxergando o homelab

O plugin `ultron_lab` lê `/root/.hermes/ultron_lab/homelab.json` (copiado de
`inventario/homelab.pc.json`). Edite esse arquivo para acrescentar ou tirar serviços; o Ultron e o
monitor só consultam o que está lá. Pergunte "como está o homelab?" ou espere o alerta: o timer
`ultron-lab-monitor.timer` checa a cada 10 minutos e avisa no Telegram quando algo cai ou volta.

Para o ai-memory virar memória do Ultron e dos agentes de código, veja a skill
`memoria-projetos` (bloco `mcp_servers` do Hermes) e, no PC, rode
`ai-memory install-mcp --client claude-code --apply` para o Claude Code usar o mesmo servidor.

## Backup

Duas camadas, como o Akita: snapshot do disco (no servidor com btrfs/snapper; no PC, exporte o WSL
de vez em quando com `wsl --export Debian`) e restic para fora da máquina:

```bash
scripts/backup-restic.sh init      # uma vez
scripts/backup-restic.sh backup    # agende no cron do WSL/servidor
```

Modelos de IA, caches e métricas ficam fora do backup (rebaixáveis).

## Mídia com GPU

`scripts/upscale.sh foto|video` usa o Real-ESRGAN do fork do Akita. Lista completa de ferramentas na
skill `midia-gpu`.

## Fora do escopo de propósito

- Stack de torrent/*arr (Radarr, Sonarr, Prowlarr, qBittorrent) do home server do Akita.
- FrankMega e Frank FBI em container: exigem build próprio com credenciais Rails suas. O Frank FBI
  virou a ferramenta `ultron_golpe` do Ultron.
- Uptime Kuma, Portainer, Vaultwarden, FrankMD e Frank Type: removidos no PC (Obsidian já cobre notas).
- Apps de desktop/celular (FrankSherlock, frank_go, Frank Karaokê, Frank Manga+): instale direto pelos
  releases de cada repositório.
