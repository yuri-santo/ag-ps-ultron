# Painéis — o dashboard do Hermes e o Stream Deck

O Ultron tem duas interfaces gráficas: o **dashboard web do Hermes** (a mesa de
controle do agente) e o **Stream Deck** (um celular na LAN que abre tudo no PC).

## Dashboard do Hermes (`hermes-dashboard.service`)
Servidor web em **`127.0.0.1:9119`** (só local). É parte do **Hermes**
(NousResearch) — o repositório do Ultron não vendoriza esse código; abaixo está o
mapa das abas para operar o agente. API interna em `/api/*` (ex.: `/api/cron/jobs`,
`/api/status`, `/api/config`), autenticada por token do próprio painel.

| Aba | Rota | Para que serve |
|---|---|---|
| **Chat** | `/chat` | Falar com o agente e ver a atividade das ferramentas ao vivo. |
| **Sessions** | `/sessions` | Sessões ativas e histórico. |
| **Files** | `/files` | Navegar arquivos do agente. |
| **Models** | `/models` | Modelos disponíveis (via 9Router). |
| **Logs** | `/logs` | Logs do gateway. |
| **Cron** | `/cron` | **Agendador**: cria/edita/dispara jobs (é aqui que as automações vivem — ver [AUTOMACOES.md](AUTOMACOES.md)). Suporta "Once", diário, semanal, intervalo e cron custom. |
| **Skills** | `/skills` | Skills instaladas. |
| **Plugins** | `/plugins` | Plugins habilitados (ver [TOOLS.md](TOOLS.md)). |
| **MCP** | `/mcp` | Servidores MCP conectados. |
| **Channels** | `/channels` | Canais de mensageria (Telegram, e-mail…). |
| **Webhooks** | `/webhooks` | Webhooks de entrada. |
| **Pairing** | `/pairing` | Pareamento de dispositivos (Stream Deck, etc.). |
| **Profiles** | `/profiles` | Os 21 perfis (ver [AGENTS.md](AGENTS.md)). |
| **Config** | `/config` | `config.yaml` do agente. |
| **Keys** | `/env` | Variáveis/segredos (nunca versionados). |
| **System** | `/system` | Reiniciar gateway, atualizar Hermes, estado. |
| **Kanban** | `/kanban` | Quadro do time (plugin) — cards, votos, bloqueios do conselho. |
| **Achievements** | `/achievements` | Conquistas (plugin). |

Como o Ultron **executa uma tarefa no WSL** a partir daqui: um job **Cron
"Once"** com o comando `bash .../wsl/disparar.sh <script>.sh` roda o script fora
do gateway (via `systemd-run`) e volta na hora. É esse mecanismo que aplica
patches, roda o inventário e faz o **push do repositório** (ver
`agent/scripts/`).

## Stream Deck (`panel/`)
Servidor Python no Windows (porta **8090**), PWA num celular fixo na LAN. Desde
set/2026, **tudo abre no PC (Saitama)** — nunca no celular.

| Módulo | Papel |
|---|---|
| `server.py` | Servidor HTTP do painel; roteia os botões. |
| `desktop_open.py` + `abrir-local.js` | Abre links, apps e reuniões no desktop (Teams/Zoom pelo app; Meet/Webex no navegador). |
| `deck_auth.py` + `auth.*` | Pareamento do celular + checagem de Origin nos POST. |
| `deck_runtime.py`, `local_runtime.py` | Execução dos comandos de botão. |
| `hub_api.py`, `hub_jobs.py`, `hub_media.py`, `hub_voice.py` | Hub: jobs, mídia (GPU), voz. |
| `finance_proxy.py`, `flow_proxy.py`, `librechat_proxy.py` | Proxies para finanças, flows e LibreChat. |
| `meeting_controls.py`, `audio_controls.py`, `leave-teams.ps1` | Controle de gravação/áudio e saída do Teams. |
| `app_inventory.py`, `read_outlook_cal.ps1` | Inventário de apps e leitura da agenda Outlook. |
| `cockpit*.css/js`, `hub.*`, `deck.html`, `manifest.json` | Interface (cockpit imersivo + PWA instalável). |
| `watchdog.ps1` | Watchdog do painel. |

Fluxo: você toca um botão no celular → `server.py` recebe (com checagem de
Origin e pareamento) → `desktop_open.py` abre o recurso **na tela do PC**.

## `fin-dashboard` (Perseu)
Dashboard financeiro visual (`/root/fin-dashboard/`) construído pelo **Perseu**,
consumindo `financas_yuri.db` — gráficos interativos de orçamento, metas e
carteira. Servido localmente e acessível pelos proxies do painel.
