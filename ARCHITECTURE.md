# Arquitetura completa — Ag-PS-Ultron

## Visão geral

```
                          ┌─────────────────────────┐
                          │   Celular (qualquer um)   │
                          │        Telegram           │
                          └────────────┬─────────────┘
                                       │ mensagem
                                       ▼
┌──────────────────────┐    HTTP/8090   ┌───────────────────────────────────────────┐
│  Celular velho fixo    │◀──────────────▶│              VPS (Linux, Docker)            │
│  panel/ (Yuri Deck)    │   (LAN, via     │                                             │
│  no notebook Windows   │   SSH p/ ações) │  ┌───────────────────────────────────────┐  │
└──────────────────────┘                 │  │  Hermes Agent (gateway de mensageria)  │  │
                                          │  │  - recebe Telegram/e-mail              │  │
                                          │  │  - roda como serviço Docker            │  │
                                          │  │  - fala com o modelo via 9Router        │  │
                                          │  └───────────────┬───────────────────────┘  │
                                          │                  │ chama                     │
                                          │                  ▼                           │
                                          │  ┌───────────────────────────────────────┐  │
                                          │  │  9Router (gateway de IA próprio)       │  │
                                          │  │  API compatível c/ OpenAI               │  │
                                          │  │  roteia p/ Gemini/Claude/GPT-OSS/       │  │
                                          │  │  OpenRouter conforme o modelo pedido    │  │
                                          │  └───────────────────────────────────────┘  │
                                          │                                             │
                                          │  ┌───────────────────────────────────────┐  │
                                          │  │  Ferramentas próprias (/sap, /tools)    │  │
                                          │  │  - lg-control.mjs  (TV/rede LAN)        │  │
                                          │  │  - fetch-note.mjs  (notas SAP, login    │  │
                                          │  │    de navegador persistido)             │  │
                                          │  │  - cal_daily2.py + MS Graph/Google       │  │
                                          │  │    (agenda do dia)                      │  │
                                          │  └───────────────────────────────────────┘  │
                                          └───────────────────────────────────────────┘
```

O sistema tem **dois pontos de entrada** para o mesmo agente:

1. **Telegram** — canal principal, funciona de qualquer celular, em
   qualquer lugar com internet. É o gateway de mensageria nativo do
   próprio Hermes (não é um bot separado escrito do zero).
2. **Painel físico** (`panel/`) — um celular velho dedicado, sempre ligado,
   rodando a PWA do Yuri Deck. Serve dois papéis: (a) atalhos físicos para
   ações locais do notebook (abrir apps, RDP, volume), e (b) uma caixa de
   texto/voz que manda comandos para o mesmo agente via SSH — ou seja, é
   *outra porta de entrada* para o Hermes, complementar ao Telegram.

Ambos os caminhos convergem no mesmo agente rodando na VPS — não há duas
implementações de agente, só duas interfaces de acesso a ele.

## Componentes

### Hermes Agent

Framework de agente de IA com CLI própria, instalado na VPS
(`/usr/local/lib/hermes-agent`, Python, ambiente virtual próprio). Não é um
script único — é uma ferramenta com várias responsabilidades:

- **`hermes chat`** — sessão interativa de chat com o agente.
- **`hermes model` / `hermes moa` / `hermes fallback`** — escolha de qual
  modelo de IA usar, incluindo "Mixture of Agents" (combinar respostas de
  múltiplos modelos) e provedores de fallback se o principal falhar.
- **`hermes gateway`** — gerencia o serviço de mensageria (Telegram,
  e-mail, WhatsApp, Slack, Discord, Signal, SMS, e vários outros — só
  Telegram e e-mail estão configurados/ativos hoje). Roda como serviço
  Docker de longa duração ("foreground"), com sessão(ões) ativa(s) e jobs
  agendados.
  observação: canal Telegram identificado pelo id de chat "home" —
  substitua pelo id real do seu chat ao configurar; nunca versione esse id
  num repositório público.
- **`hermes secrets`** — integração com cofres de senha externos
  (Bitwarden, 1Password) em vez de guardar segredos em texto puro no
  próprio agente.
- **`hermes egress`** — um firewall de injeção de credenciais ("iron-proxy")
  para chamadas de saída — a credencial é injetada no proxy, não fica
  exposta para o processo/modelo que faz a chamada.
- **`hermes send`** — dispara uma mensagem para uma plataforma configurada
  a partir de scripts/cron/CI (é o comando usado pelo `panel/server.py`
  para mandar texto do painel físico para o Telegram do usuário).
- **`hermes status`** — resumo de tudo: ambiente, modelo ativo, plataformas
  de mensageria configuradas, status do gateway, sessões e jobs. É esse
  comando que o `panel/server.py` chama (via SSH) para popular o card
  "Status VPS" do painel físico.

### 9Router

Gateway HTTP próprio, compatível com a API da OpenAI (`/v1/chat/completions`
etc.), que o Hermes usa como "Custom endpoint" em vez de falar direto com
um provedor de IA. Roteia por prefixo de modelo:

- `ag/*` — modelos via um provedor tipo "antigravity" (Gemini, Claude,
  GPT-OSS).
- `openrouter/*` — modelos via OpenRouter.

Vantagem prática: trocar de modelo (ex: de Gemini para Claude) é só trocar
a string do modelo configurado no Hermes — não precisa reconfigurar chaves
de API em cada ferramenta que usa IA.

### Ferramentas SAP e de rede (`/sap`)

Um pequeno projeto Node.js na VPS com duas ferramentas concretas:

- **`lg-control.mjs`** — controla TVs LG na rede local (liga/desliga,
  comandos) — é a peça de "network (WoL/scan/TVs)" mencionada como
  capacidade do agente.
- **`fetch-note.mjs`** — busca notas técnicas do SAP. Guarda o estado da
  sessão do navegador (cookies/login) num arquivo separado após a primeira
  autenticação manual, para não precisar logar de novo a cada consulta —
  **este já é, na prática, o padrão de "automação de navegador com área de
  login persistida"** que se cogitou como expansão do painel: abrir uma
  sessão autenticada uma vez, reusar o estado salvo nas execuções
  seguintes. O arquivo de estado de sessão nunca deve ir para controle de
  versão (contém cookies de login reais).

### Agenda (`/tools`)

Scripts Python na VPS que consultam calendários via Microsoft Graph
(WorkMail/Exchange) e Google Calendar, normalizando o resultado em JSON.
É esse JSON que `panel/server.py` repassa para o card de reuniões do
painel físico (rota `/calendar`) — o painel não fala com o Outlook nem com
o Google diretamente, só consome o resultado já processado da VPS.

### Painel físico (`panel/`)

Documentado em detalhe em [panel/ARCHITECTURE.md](panel/ARCHITECTURE.md).
Resumo: um celular velho fixo, rodando a PWA, conversando com um servidor
Python no notebook Windows, que por sua vez aciona ações locais (apps,
RDP, volume) e — para tudo que envolve o agente, a agenda e o status da
VPS — abre uma conexão SSH até a VPS e chama os comandos acima.

## Segurança

Herda o modelo de confiança do `panel/` (rede local, sem autenticação —
ver [panel/ARCHITECTURE.md](panel/ARCHITECTURE.md)), mais os seguintes
pontos específicos do agente:

- **Segredos ficam na VPS, não no notebook**: chaves de modelo, tokens de
  mensageria e credenciais de sites ficam configurados dentro do Hermes
  (idealmente via `hermes secrets`, apontando para Bitwarden/1Password) —
  o notebook só precisa da chave SSH para acionar comandos, nunca guarda
  as credenciais em si.
- **`hermes egress`** existe exatamente para isso: nenhuma ferramenta que
  o agente chama deveria precisar saber a credencial real — o proxy de
  saída injeta ela na hora da chamada.
- **Estados de sessão de navegador (`sap-storage-state.json` e
  equivalentes) são segredos** tão sensíveis quanto uma senha — permitem
  logar como o usuário sem precisar da senha. Nunca devem ir para
  controle de versão, backup público, ou ser copiados para fora da VPS
  sem necessidade.
- **O id do chat do Telegram e qualquer token de bot** não devem aparecer
  em texto puro em nenhum repositório, nem privado — trate como você
  trataria uma senha.
- **Superfície de comandos do agente**: como o Hermes tem `chat` e
  `tool-calling`, o agente pode, em tese, executar ações amplas (é um
  agente com ferramentas, não um bot de respostas fixas) — vale revisar
  periodicamente quais ferramentas/skills estão habilitadas para ele
  (`--toolsets`, `--skills`) e não habilitar mais do que o necessário para
  o uso real.

## Possíveis expansões

- **Formalizar a automação de navegador como capacidade genérica do
  agente**: hoje `fetch-note.mjs` é uma automação específica para SAP;
  generalizar esse padrão (sessão persistida + Playwright) para outros
  sites com login daria ao agente a capacidade de "fazer ações repetitivas
  em qualquer site" pedida como expansão — reaproveitando a mesma ideia de
  estado de sessão salvo, e reportando resultados (relatórios, planilhas)
  de volta via o mesmo canal (`hermes send`) já usado para Telegram.
- **Geração de planilhas/relatórios a partir das automações de
  navegador**: o mesmo agente que já gera relatório de reunião (no
  `panel/`) poderia gerar `.xlsx` a partir dos dados extraídos de uma
  automação de navegador, e enviar por Telegram ou salvar num storage
  compartilhado.
- **Dashboard unificado de status**: hoje `hermes status` e o status dos
  containers Docker são consultados via SSH sob demanda pelo painel;
  poderia virar um endpoint HTTP próprio do Hermes (via `hermes gateway`
  ou um webhook simples) para não depender de SSH a cada consulta.
- **Failover de modelo mais visível no painel**: o Hermes já tem
  `fallback` configurável; expor no card "Status VPS" qual modelo está
  ativo *no momento* (principal vs. fallback) ajudaria a perceber
  degradação de serviço mais cedo.
