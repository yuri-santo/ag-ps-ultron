<p align="center">
  <img src="assets/banner.svg" alt="Ag-PS-Ultron" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-em%20produção-22c55e" alt="status">
  <img src="https://img.shields.io/badge/plataforma-Windows%20%2B%20Linux%20VPS-3da9fc" alt="plataforma">
  <img src="https://img.shields.io/badge/agente-Hermes-7c5cff" alt="hermes">
  <img src="https://img.shields.io/badge/router-9Router-3da9fc" alt="9router">
  <img src="https://img.shields.io/badge/mensageria-Telegram-26A5E4" alt="telegram">
  <img src="https://img.shields.io/badge/painel-PWA-1c1f28" alt="pwa">
  <img src="https://img.shields.io/badge/uso-pessoal-8d96a8" alt="uso pessoal">
</p>

<p align="center">
  Agente de IA pessoal que roda <b>24/7 numa VPS</b>, acessível de qualquer
  celular via <b>Telegram</b> ou de um <b>painel físico dedicado</b> (um
  celular velho rodando a PWA "Ultron Deck"), com ferramentas próprias de
  pesquisa em sistemas restritos, controle de TV/rede e agenda.
</p>

---

Este repositório documenta a arquitetura completa do sistema, de ponta a
ponta: como cada peça foi construída, como instalar/configurar cada
agente do zero, e como tudo se conecta. Assim como no componente
`panel/`, hostnames, IPs, IDs de chat e tokens reais foram substituídos
por placeholders — o objetivo é documentar *como o sistema é construído*,
não expor a infraestrutura real.

## Diagrama completo

```
 ┌────────────────────────┐          ┌──────────────────────────────────┐
 │  Celular (qualquer um)  │          │  Biblioteca de PDFs → NotebookLM   │
 │  app Telegram           │          │  RAG paralelo — fluxo manual,      │
 └────────────┬────────────┘          │  não é chamado pelo agente         │
              │ mensagem              └──────────────────────────────────┘
              ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                            VPS Linux (Docker)                            │
 │                                                                          │
 │  ┌───────────────────────────┐  modelo de IA  ┌────────────────────────┐ │
 │  │  Hermes Agent              │───────────────▶│  9Router                │ │
 │  │  gateway Telegram / e-mail │                │  compat. OpenAI         │ │
 │  │  CLI: status/send/secrets  │                │  roteia: Gemini/Claude/ │ │
 │  └──────┬───────────────┬────┘                │  GPT-OSS/OpenRouter     │ │
 │         │               │                      └────────────────────────┘ │
 │         ▼               ▼                                                │
 │  ┌────────────────┐  ┌─────────────────────────────┐                    │
 │  │  /restrito      │  │  Kali pentest (kali-tools)    │                    │
 │  │  /tools         │  │  nmap/hydra/gobuster/nikto/   │                    │
 │  │  email-manager  │  │  sqlmap — testa a própria rede │                    │
 │  └────────────────┘  └───────────────┬───────────────┘                    │
 │                                       │ SSH reverso + WireGuard            │
 └───────────────────────────────────────┼────────────────────────────────────┘
                                          │
                 ┌─────────────────────────┴─────────────────────────┐
                 ▼                                                   ▼
 ┌────────────────────────────┐    HTTP LAN    ┌─────────────────────────────┐
 │  Notebook Windows            │◄──────────────▶│  Celular velho fixo           │
 │  panel/server.py :8090       │                │  PWA "Ultron Deck"            │
 │  WSL Kali (nmap/avahi/Raptor)│                │  + userland Linux (WireGuard) │
 └────────────────────────────┘                │  acessível por SSH direto      │
                                                 └─────────────────────────────┘
```

O painel físico e o Telegram são duas portas de entrada para o **mesmo**
agente (Hermes, na VPS) — não há dois agentes. O importante deste
diagrama é a seta voltando da VPS para casa: o túnel SSH reverso
(notebook) e o WireGuard (celular) não servem só para casa *falar* com a
VPS — a VPS também consegue *agir* de volta em casa (rodar comando no
notebook, abrir uma sessão dentro do userland do celular, escanear/testar
a própria rede pelo container Kali). Detalhe completo de cada seta em
[ARCHITECTURE.md](ARCHITECTURE.md) e [NETWORK.md](NETWORK.md).

## Mapa da documentação

| Arquivo | O que tem lá |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitetura completa: Hermes, 9Router, e-mail, busca web, toolsets/skills (com tabela das skills pessoais por tarefa), NotebookLM/RAG, filosofia do agente, segurança e pontos de extrema atenção. |
| [NETWORK.md](NETWORK.md) | Rede de ponta a ponta: LAN de casa, WireGuard, o userland Linux dentro do celular, o túnel SSH reverso até o notebook, e o container de pentest ativo na VPS. |
| [INSTALL.md](INSTALL.md) | Manual passo a passo para instalar e configurar o Hermes e o 9Router do zero, com o passo a passo completo de conexão ao Telegram. |
| [panel/](panel/) | O painel físico (PWA + servidor Python no Windows) — [ARCHITECTURE.md](panel/ARCHITECTURE.md) e [SETUP.md](panel/SETUP.md) próprios, incluindo requisitos do celular físico, modo quiosque e ideias de uso. |
| [RUNBOOK.md](RUNBOOK.md) | Passo a passo real de tudo que foi diagnosticado, corrigido e construído neste projeto, comando por comando. |

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

**Proteger e atacar dispositivos da própria rede via WSL Kali** —
descoberta completa de dispositivos na LAN sob demanda (nmap + ARP +
mDNS), somada a um framework de pentest completo (**Raptor**, o
ferramental de pentest do próprio Kali) para testar de verdade a
segurança dos dispositivos e aplicações da rede — não só descobrir o
que existe, mas avaliar o quão exposto está. Detecção de invasão
*contínua* (alertar sozinho quando um dispositivo novo aparece) ainda é
um design proposto, não implementado — ver [ARCHITECTURE.md](ARCHITECTURE.md).

**Base de conhecimento pessoal (NotebookLM + biblioteca em PDF)** — uma
biblioteca de livros em PDF alimenta o NotebookLM (Google), usado como
camada de pesquisa/RAG paralela ao agente — hoje é um fluxo manual do
usuário, não uma chamada automática do Hermes, mas é parte real da
"inteligência" que apoia as decisões do sistema.

**Pesquisar em sistemas com acesso restrito** — um script (`fetch-note`)
busca documentação técnica em um portal com login, com sessão de
navegador já persistida, para não precisar autenticar a cada consulta.

**Mostrar a agenda do dia** — scripts de calendário na VPS (Microsoft
Graph/WorkMail e Google Calendar) alimentam o card de reuniões do painel
físico, sem depender do Outlook estar aberto em lugar nenhum.

**Um painel físico dedicado** — um celular velho, sempre ligado na tomada,
rodando a PWA do painel (ver [panel/](panel/)) como controle físico rápido:
abrir apps, RDP, volume, scanner de rede, e um atalho de voz/texto direto
para o agente. Esse mesmo celular também roda um **userland Linux
completo por dentro** (acessível por SSH via WireGuard) — não é só uma
tela, é mais um nó de rede.

**Agir de volta em casa, a partir da VPS** — via túnel SSH reverso, o
agente consegue rodar comando ou ler arquivo direto no notebook Windows
(sem VPN, sem porta aberta no roteador); via WireGuard, consegue abrir
sessão dentro do userland Linux do celular físico. A VPS não só recebe
pedidos de casa — ela também alcança casa.

**Gerenciar e-mail de múltiplas contas** — ler, buscar, enviar e
organizar e-mail (IMAP/SMTP) de várias contas próprias, separado do canal
de mensageria do Telegram/e-mail que fala com o agente.

## Stack

- **Hermes** — framework de agente de IA (Python), com CLI própria, gateway
  de mensageria multiplataforma (Telegram, e-mail, WhatsApp, Slack...),
  gerenciamento de segredos, sessões e um sistema próprio de skills
  (`SKILL.md`) — roda como serviço Docker na VPS.
- **9Router** — gateway HTTP próprio, compatível com a API da OpenAI, que
  o Hermes usa como "Custom endpoint" em vez de falar direto com um
  provedor de IA.
- **Kali (pentest ativo)** — um container Kali dedicado, rodando na
  própria VPS, com `nmap/hydra/gobuster/dirb/nikto/sqlmap` para testar de
  verdade a segurança dos dispositivos da rede de casa, alcançados pelos
  túneis abaixo.
- **WireGuard + túnel SSH reverso** — a malha de rede que conecta VPS,
  notebook e celular físico sem expor nenhum deles diretamente à
  internet. Ver [NETWORK.md](NETWORK.md).
- **Pesquisa em ambientes restritos** (`/restrito`) — Node.js, com
  Playwright/Puppeteer para automação de navegador com sessão de login
  persistida.
- **Painel físico** (`panel/`) — Python (stdlib) + PWA, ver documentação
  própria.

Veja [ARCHITECTURE.md](ARCHITECTURE.md) para o fluxo de dados completo
entre cada peça.
