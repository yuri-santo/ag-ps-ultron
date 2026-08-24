# Ag-PS-Ultron — Agente Pessoal

Sistema de agente de IA pessoal, controlável de qualquer lugar (Telegram) ou
de um painel físico (um celular velho rodando o "Yuri Deck"), rodando 24/7
numa VPS, com acesso a ferramentas próprias (SAP, controle de rede/TV,
agenda).

Este repositório documenta a arquitetura completa do sistema. Assim como no
componente `panel/`, hostnames, IPs, IDs de chat e tokens reais foram
substituídos por placeholders — o objetivo é documentar *como o sistema é
construído*, não expor a infraestrutura real.

## Índice

- [ARCHITECTURE.md](ARCHITECTURE.md) — arquitetura completa: como o
  Hermes, o 9Router, o Telegram, o painel físico e as ferramentas de SAP se
  encaixam.
- [panel/](panel/) — o painel de controle físico (PWA + servidor local no
  Windows). Tem sua própria [ARCHITECTURE.md](panel/ARCHITECTURE.md) e
  [SETUP.md](panel/SETUP.md) detalhados.

## O que o sistema é capaz de fazer

**Conversar por Telegram, de qualquer celular** — o Hermes roda como um
gateway de mensageria persistente na VPS; qualquer mensagem no Telegram
chega ao agente, que responde usando um modelo de IA.

**Rodar 24/7 numa VPS, não no notebook** — o agente não depende do PC do
usuário estar ligado; é um serviço de longa duração na VPS, gerenciado por
Docker.

**Escolher o modelo de IA via um gateway próprio (9Router)** — em vez de
depender de uma única conta/API de um provedor, o agente fala com um
gateway HTTP compatível com a API da OpenAI que o próprio usuário mantém,
que por sua vez roteia para múltiplos modelos (Gemini, Claude, GPT-OSS via
"antigravity", ou outros provedores via OpenRouter).

**Controlar TVs e dispositivos de rede** — um script Node.js (`lg-control`)
liga/desliga e comanda TVs LG na rede local a partir de comandos do agente.

**Consultar e agir sobre notas do SAP** — um script (`fetch-note`) busca
notas técnicas do SAP, com sessão de navegador (login) já persistida, para
não precisar autenticar a cada consulta.

**Mostrar a agenda do dia** — scripts de calendário na VPS (Microsoft
Graph/WorkMail e Google Calendar) alimentam o card de reuniões do painel
físico, sem depender do Outlook estar aberto em lugar nenhum.

**Um painel físico dedicado** — um celular velho, sempre ligado na tomada,
rodando a PWA do painel (ver [panel/](panel/)) como controle físico rápido:
abrir apps, RDP, volume, scanner de rede, e um atalho de voz/texto direto
para o agente.

## Stack

- **Hermes** — framework de agente de IA (Python), com CLI própria, gateway
  de mensageria multiplataforma (Telegram, e-mail, WhatsApp, Slack...),
  gerenciamento de segredos e sessões — roda como serviço Docker na VPS.
- **9Router** — gateway HTTP próprio, compatível com a API da OpenAI, que
  o Hermes usa como "Custom endpoint" em vez de falar direto com um
  provedor de IA.
- **Ferramentas SAP** (`/sap`) — Node.js, com Playwright/Puppeteer para
  automação de navegador com sessão de login persistida.
- **Painel físico** (`panel/`) — Python (stdlib) + PWA, ver documentação
  própria.

Veja [ARCHITECTURE.md](ARCHITECTURE.md) para o diagrama completo e o fluxo
de dados entre cada peça.
