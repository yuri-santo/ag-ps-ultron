# Arquitetura do Ultron (estado atual)

> **Atualização — set/2026:** o agente **roda localmente no WSL Debian** do
> notebook (Windows 11, apelido *Saitama*), como serviço systemd. A versão
> "VPS" descrita em `README.md`/`NETWORK.md`/`INSTALL.md` é **histórica**;
> este documento é o retrato de como está hoje. Segredos, e-mails, IDs de chat
> e domínios reais foram trocados por placeholders.

**Limite operacional:** Hermes, Ultron, seus perfis, Telegram e 9Router rodam
inteiramente no notebook local (WSL Debian/Windows). A VPS `finaro-vps` não
faz parte desta instalação e não deve ser usada para diagnosticar, implantar
ou reiniciar o Ultron.

## Visão de 1 minuto

Um único agente (**Hermes/Ultron**) roda 24/7 dentro do WSL do notebook. Você
fala com ele por **Telegram**, por **e-mail**, pelo **HermesDesktop** (app de
voz no PC) e por um **Stream Deck** (PWA num celular fixo na LAN). Ele escolhe o
modelo por um **gateway próprio (9Router)**, consulta uma **memória** persistente,
e **toda resposta passa por uma revisão obrigatória** antes de sair. Um time de
**21 especialistas** (perfis) é convocado por um **conselho** para pesquisa e
decisão, com um verificador de fatos (**Frank**) para as alegações que importam.

> **Retrato completo por tema:** [AGENTS.md](AGENTS.md) (os 21 agentes) ·
> [TOOLS.md](TOOLS.md) (13 plugins e ferramentas) · [AUTOMACOES.md](AUTOMACOES.md)
> (o que roda sozinho) · [INTEGRACOES.md](INTEGRACOES.md) (tudo com que conversa) ·
> [DATABASES.md](DATABASES.md) (bancos) · [HOMELAB.md](HOMELAB.md) (containers) ·
> [DASHBOARD.md](DASHBOARD.md) (painéis).

```
   Telefone (Telegram)      HermesDesktop (voz, PC)      Stream Deck (celular LAN)
          │                        │                            │
          └───────────────┬────────┴───────────────┬────────────┘
                          ▼                         ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │  WSL Debian (systemd)  —  notebook "Saitama" (Windows 11)                   │
 │                                                                            │
 │  hermes-gateway.service ──── modelo ───▶ 9Router (127.0.0.1:20130)         │
 │   │  Telegram / e-mail / Home Assistant   └─▶ Gemini · Claude · GPT-OSS ·  │
 │   │                                            OpenRouter (fallback)        │
 │   ├─▶ Revisão obrigatória (model_review.py) ── revisor independente ▶ ✔/�　│
 │   ├─▶ Conselho SDD ──▶ especialistas (perfis) ──▶ Frank (checagem)         │
 │   ├─▶ ferramentas dos plugins (ver TOOLS.md)                               │
 │   ├─▶ ai-memory (docker :49374)   ·   Obsidian vault (MCP)                 │
 │   └─▶ meeting_copilot (grava Teams ▶ transcreve ▶ diariza ▶ ATA)          │
 │                                                                            │
 │  hermes-dashboard.service (127.0.0.1:9119)  —  chat, arquivos, cron, MCP    │
 │  timers: monitor (10min) · auditoria (semanal) · backup restic (diário)    │
 └───────────────────────────────────────────────────────────────────────────┘
                          ▲                         ▲
          âncora de logon │                         │ HTTP LAN :8090
     .hermes-autostart.vbs│                         │
   (Tarefa Agendada)      │                    Stream Deck server (Windows)
                          │                    abre tudo no PC (nunca no celular)
                    mantém o WSL vivo
```

## Componentes

### Núcleo
- **Hermes Agent** — framework de agente (Python) da NousResearch. CLI própria,
  gateway de mensageria (Telegram, e-mail, WhatsApp, Slack…), segredos, sessões
  e sistema de skills (`SKILL.md`). Roda como `hermes-gateway.service`
  (systemd de usuário root) dentro do WSL. Home em `/root/.hermes`.
- **hermes-dashboard.service** — painel web em `127.0.0.1:9119` (CHAT, FILES,
  CRON, PLUGINS, MCP). É a "mesa de controle" do agente.
- **9Router** — gateway HTTP compatível com a API da OpenAI (`127.0.0.1:20130`).
  O Hermes aponta o "custom endpoint" para ele; o 9Router roteia para Gemini,
  Claude, GPT-OSS (via antigravity) ou OpenRouter, com fallback.
- **Âncora de logon** — `C:\Users\…\.hermes-autostart.vbs` (Tarefa Agendada
  *HermesUltronAutostart*) mantém a distro WSL viva no logon, sem janela. Ver
  `agent/scripts/autostart/`.

### Revisão obrigatória (`agent/review/`)
`model_review.py` é um *broker* de revisão: antes de qualquer resposta sair, um
**revisor independente** (modelo diferente, tier mais alto) avalia o candidato
contra o pedido, evidências e limites. Sem aprovação, a resposta **não sai** —
vira "pendente de revisão" com o motivo. `ultron_review_gate.py` é a ponte que
liga isso ao Hermes. Política em `review-policy.json` (tokens, timeouts, lista
de revisores). Ninguém desativa a revisão; falhas de disponibilidade são
corrigidas, não contornadas.

### Conselho SDD + Frank
`conselho_sdd.md` (plugin `ultron_team`) define o método: para pesquisa,
comparação, recomendação ou decisão de compra, o Ultron (1) reformula a
intenção, (2) convoca 2–4 especialistas para colher **requisitos** antes de
qualquer busca, (3) consolida a spec, (4) investiga usando o **Frank**
(`frank-investigator`) para as alegações decisivas, (5) devolve aos mesmos
especialistas para votarem, (6) entrega com o placar e as ressalvas.

### Memória
- **ai-memory** (docker, `127.0.0.1:49374`, MCP) — memória semântica de
  projetos/decisões confirmadas. Nunca guarda segredo.
- **Obsidian vault** — exposto por MCP (`mcpvault`), sem precisar do Obsidian
  aberto. Leitura/escrita de notas; ações de apagar/mover ficam de fora.

### Reuniões (`meeting_copilot` + `agent/meeting/` + `agent/stt/`)
Grava a reunião do Teams (dois canais: microfone e áudio recebido), transcreve
localmente (faster-whisper, mantido "aquecido" para não estourar o tempo do
HermesDesktop), **diariza** as vozes (sherpa-onnx + pyannote, CPU) e gera a
**ATA formal** em PDF e Word (`render_report.py`, `render_docx.py`), com a
identidade do Ultron. Análise executiva e transcrição integral vão como anexos.

### Stream Deck (`panel/`)
Servidor Python (`server.py`) no Windows, porta `8090`, PWA num celular fixo na
LAN. Desde set/2026, **tudo abre no PC (Saitama)** — links, reuniões (Teams/Zoom
pelo app; Meet/Webex/etc. no navegador do desktop), Outlook, apps — e nada muda
a tela do celular (`desktop_open.py` + `abrir-local.js`). Auth por pareamento
(`deck_auth.py`), checagem de Origin nos POST.

### Homelab (`agent/homelab/`)
Stacks docker (ai-memory, Syncthing e opcionais de IA/mídia) e um inventário
que o `ultron_homelab` consulta para dizer o que está no ar. Cenários para o PC
atual e para um servidor dedicado futuro.

### Segurança e backup (`agent/security/`)
- **Auditoria semanal** (`auditar.py`, timer domingo) — Lynis (hardening),
  Trivy (vulnerabilidades) e Gitleaks (segredos em arquivo); avisa no Telegram
  quando aparece algo novo. Não corrige sozinho.
- **Backup diário** (`backup.sh`, timer) — restic criptografado no disco D:,
  com snapshot consistente dos bancos SQLite.

## Fluxo de uma pergunta
1. Mensagem chega (Telegram / voz / deck).
2. Ultron decide: conversa simples → responde; pesquisa/decisão → **conselho**.
3. Convoca especialistas (perfis) via `ultron_team/bridge.py` → `worker.py`
   (cada perfil roda isolado, só com suas ferramentas).
4. Investiga com Frank; consolida.
5. Modelo pelo 9Router.
6. **Revisão obrigatória** aprova ou devolve com correções.
7. Resposta sai; memória guarda só o que foi confirmado.

## O que NÃO está neste repositório (por conter dado pessoal)
- `config.yaml`, `.env`, `accounts.json`, tokens e chaves — segredos.
- Bancos pessoais: finanças, saúde, agenda, cortes de vídeo.
- `SOUL.md` dos 20 perfis (contêm contexto pessoal, médico e financeiro). O
  papel de cada um está em `AGENTS.md`; os 3 perfis de e-mail/reunião (sem dado
  sensível) estão em `agent/profiles/` como exemplo do formato.
- Ledger de revisões, `deck-meetings-private.json`, preferências operacionais.
