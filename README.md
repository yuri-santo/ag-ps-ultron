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
| **[AGENTS.md](AGENTS.md)** | O time: ~20 especialistas, papel de cada um e as regras do conselho. |
| **[TOOLS.md](TOOLS.md)** | Todas as ferramentas por plugin, skills, automações (timers) e fontes externas. |
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

## Nota sobre os documentos históricos
`INSTALL.md`, `NETWORK.md` e `RUNBOOK.md` descrevem a fase em que o agente rodava
numa VPS com túneis para casa. A implantação atual é **local no WSL**; use
[ARCHITECTURE.md](ARCHITECTURE.md) como fonte da verdade.
