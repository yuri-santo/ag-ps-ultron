<p align="center">
  <img src="assets/banner.svg" alt="Ultron — agente de IA pessoal" width="100%">
</p>

<p align="center"><b>Ultron</b> — agente de IA pessoal (Hermes), local no WSL, com time de especialistas, revisão obrigatória, Stream Deck e copiloto de reuniões.</p>

<p align="center">
  <img src="https://img.shields.io/badge/agente-Hermes-7c5cff" alt="hermes">
  <img src="https://img.shields.io/badge/execu%C3%A7%C3%A3o-WSL%20local-22c55e" alt="wsl">
  <img src="https://img.shields.io/badge/router-9Router-3da9fc" alt="9router">
  <img src="https://img.shields.io/badge/mensageria-Telegram%20%2B%20e--mail-26A5E4" alt="telegram">
  <img src="https://img.shields.io/badge/painel-Stream%20Deck%20PWA-1c1f28" alt="pwa">
  <img src="https://img.shields.io/badge/uso-pessoal-8d96a8" alt="uso pessoal">
</p>

> **Privado.** Este repositório é o retrato do agente: código, arquitetura,
> ferramentas, painel e automações. **Nenhum segredo, chave, e-mail real ou
> banco de dados pessoal está aqui** — foram trocados por placeholders ou
> deixados de fora (ver o fim de [ARCHITECTURE.md](ARCHITECTURE.md)).

## Comece por aqui

| Documento | O que tem |
|---|---|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | O retrato atual: WSL local, 9Router, revisão obrigatória, conselho, memória, reuniões, Stream Deck, segurança. Com diagrama. |
| **[AGENTS.md](AGENTS.md)** | O time: os **21 especialistas** com nome, personalidade e especialidade + regras do conselho. |
| **[TOOLS.md](TOOLS.md)** | Ferramentas por plugin + os **13 plugins** do Hermes, painel, skills, reuniões e automações. |
| **[AUTOMACOES.md](AUTOMACOES.md)** | Tudo que roda sozinho: crons e timers (saúde, finanças, conteúdo, monitores, backup). |
| **[INTEGRACOES.md](INTEGRACOES.md)** | Tudo com que o agente conversa: M365, Google Fit, NotebookLM, Telegram, TikTok, YouTube, etc. |
| **[DATABASES.md](DATABASES.md)** | Os bancos: estrutura e finalidade (o **dado pessoal fica privado**). |
| **[HOMELAB.md](HOMELAB.md)** | Os containers Docker que sustentam o Ultron (9Router, Frank, RAG, ai-memory, flowsint…). |
| **[DASHBOARD.md](DASHBOARD.md)** | O dashboard do Hermes (todas as abas) e o Stream Deck. |
| **[CREDITS.md](CREDITS.md)** | O que é de terceiros: cada projeto com o link do repositório e para que o Ultron usa. |
| **[agent/](agent/)** | O código: plugins, revisão, reuniões, transcrição, segurança, homelab, skills, testes, scripts. |
| **[panel/](panel/)** | O Stream Deck (servidor Python no Windows + PWA). |
| **[docs/](docs/)** | Notas de evolução (ferramentas adotadas do GitHub, changelog do ultron_lab). |

## O que o sistema faz
- **Conversa** por Telegram, e-mail, voz (HermesDesktop) e Stream Deck — tudo o
  **mesmo** agente, rodando no WSL do notebook.
- **Escolhe o modelo** por um gateway próprio (9Router → Gemini/Claude/GPT-OSS/OpenRouter).
- **Revisa toda resposta** com um revisor independente antes de entregar.
- **Convoca um time** de especialistas (jurídico, finanças, SAP, dev, saúde,
  segurança…) por um conselho, com verificação de fatos (Frank).
- **Jurídico de verdade** (Harvey): lei pelo Vade Mecum + Planalto, processos no
  DataJud, intimações no DJEN, prazos pelo CPC, jurisprudência oficial.
- **Finanças de verdade** (Bigode/Buffett/Tron): Banco Central, BrasilAPI, B3.
- **Reuniões**: grava o Teams, transcreve e diariza local, gera **ATA formal**
  em PDF e Word.
- **Stream Deck**: um celular na LAN que abre tudo **no PC**, nunca no celular.
- **Anti-golpe**: detector determinístico de phishing em mensagens e e-mails.
- **Se cuida sozinho**: monitor a cada 10 min, auditoria de segurança semanal,
  backup criptografado diário.

## Estrutura
```
agent/
  plugins/        ultron_team · ultron_lab · harvey_juridico · ultron_agentes
  review/         revisão obrigatória (broker + gate)
  meeting/        ATA em PDF e Word
  stt/            transcrição (Parakeet) e diarização (pyannote)
  security/       auditoria (Lynis/Trivy/Gitleaks) e backup (restic)
  homelab/        stacks docker + inventário
  skills/         SKILL.md
  scripts/        instaladores e âncora de logon (WSL)
  juridico/       indexador do Vade Mecum
  tests/          testes
panel/            Stream Deck (server.py + PWA)
docs/             notas de evolução
```

## Rodar / instalar
O agente é o **Hermes** (NousResearch). A instalação base do Hermes e do
9Router está em [INSTALL.md](INSTALL.md) *(histórico: descreve o cenário VPS; hoje
roda no WSL do notebook)*. Os plugins deste repositório são instalados com
`agent/deploy_lab.py` / `agent/deploy.py` e os scripts em `agent/scripts/`.

## Subir tudo de novo (1 comando)
Quando o agente mudar, o retrato deste repositório se atualiza sozinho com:
```bash
bash agent/scripts/sync-repo.sh          # reconstrói, sanitiza, guarda de segredos, push
bash agent/scripts/sync-repo.sh --dry-run  # faz tudo menos o push
```
O script troca e-mails/IPs/tokens reais por placeholder e **aborta o push** se a
guarda de segredos achar qualquer coisa sensível.

## Nota sobre os documentos históricos
`INSTALL.md`, `NETWORK.md` e `RUNBOOK.md` descrevem a fase em que o agente rodava
numa VPS com túneis para casa. A implantação atual é **local no WSL**; use
[ARCHITECTURE.md](ARCHITECTURE.md) como fonte da verdade.
