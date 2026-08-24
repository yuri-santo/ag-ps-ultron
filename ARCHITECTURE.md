# Arquitetura completa — Ag-PS-Ultron

## Visão geral

O diagrama completo do sistema está no [README.md](README.md#diagrama-completo)
(raiz do repositório). Resumo em camadas:

- **Casa**: Telegram (qualquer celular) + painel físico (celular velho
  fixo, `panel/`) rodando no notebook Windows, que aciona o WSL Kali
  (rede/segurança local) e abre SSH para a VPS.
- **VPS (Docker)**: Hermes Agent (gateway de mensageria + CLI) fala com o
  9Router (gateway de modelo) e aciona as ferramentas `/restrito` e `/tools`.
- Telegram e o painel físico são **duas portas de entrada para o mesmo
  agente** — não há dois agentes rodando.

O sistema tem **dois pontos de entrada** para o mesmo agente:

1. **Telegram** — canal principal, funciona de qualquer celular, em
   qualquer lugar com internet. É o gateway de mensageria nativo do
   próprio Hermes (não é um bot separado escrito do zero).
2. **Painel físico** (`panel/`) — um celular velho dedicado, sempre ligado,
   rodando a PWA do Ultron Deck. Serve dois papéis: (a) atalhos físicos para
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

### E-mail como canal de mensageria

Assim como o Telegram, o e-mail é um dos canais de mensageria nativos do
`hermes gateway` (`hermes status` mostra `Email ✓ configured`). Configurar
segue o mesmo fluxo do Telegram — pelo assistente interativo:

```bash
hermes setup
# escolher "Email" na lista de plataformas -> informar servidor SMTP/IMAP
# e credenciais (ou apontar para um segredo já guardado via `hermes secrets`)
```

Uma vez configurado, o e-mail funciona como mais uma porta de entrada/
saída equivalente ao Telegram: você pode mandar um e-mail para o agente
e ele processa como uma mensagem de chat, ou o agente pode notificar por
e-mail (`hermes send --to email ...`) do mesmo jeito que notifica por
Telegram.

### Busca na web

Levantamento real do ambiente (via `hermes status`) mostra que nenhuma
integração dedicada de busca/navegação web está configurada hoje:
Tavily, Firecrawl, Browser Use e Browserbase aparecem todas como
"não configuradas". Ou seja, **o agente não tem busca na web ligada por
padrão neste setup** — qualquer resposta que pareça vir de uma busca é,
na prática, conhecimento do próprio modelo, não uma consulta ao vivo.

Para habilitar busca real, o caminho é: gerar uma chave num desses
serviços (Tavily e Firecrawl têm planos gratuitos de teste), guardá-la
com `hermes secrets` (não em variável de ambiente solta), e então:

```bash
hermes auth add tavily          # ou firecrawl / browser-use / browserbase
hermes chat -t web -q "pesquise algo na internet"
# -t web (ou o nome do toolset correspondente) habilita a ferramenta
# de busca só para aquela sessão
```

### Toolsets e Skills — os "plugins" do agente

O Hermes não tem um sistema de "plugins" no sentido tradicional (não é
instalar um pacote separado por integração) — ele usa dois conceitos
próprios, configuráveis por sessão via flags de linha de comando:

- **Toolsets** (`-t`/`--toolsets`) — grupos de *ferramentas* que o modelo
  pode chamar (ex: acesso a arquivos, execução de comandos, navegador,
  busca web). Habilitar só o necessário por sessão é também uma prática
  de segurança — quanto menos ferramentas ativas, menor a superfície do
  que o agente pode fazer sem querer.
- **Skills** (`-s`/`--skills`) — módulos de conhecimento/procedimento
  pré-carregados (parecido com "receitas" ou playbooks) que o agente
  injeta no contexto para saber *como* fazer uma tarefa específica bem
  (ex: uma skill de "como gerar relatório de reunião", outra de "como
  consultar documento de um sistema com acesso restrito"). O ambiente deste projeto acumulou uma
  biblioteca própria de dezenas de skills ao longo do tempo — não listada
  aqui por ser específica do uso pessoal do autor, mas o mecanismo (uma
  pasta de skills carregável por nome) é reaproveitável para qualquer
  domínio.

```bash
hermes -t files,exec,web -s relatorio-reuniao -q "gere o relatório de hoje"
```

- **`hermes plugins`** — diretório próprio para extensões mais profundas
  do agente (além de toolsets/skills), separado do restante da
  configuração.
- **`hermes dashboard`** — sobe uma UI web (porta 9119) para inspecionar
  sessões, config e status visualmente, em vez de tudo via terminal/SSH.

### Pesquisa em ambientes restritos e de rede (`/restrito`)

Um pequeno projeto Node.js na VPS com duas ferramentas concretas:

- **`lg-control.mjs`** — controla TVs LG na rede local (liga/desliga,
  comandos) — é a peça de "network (WoL/scan/TVs)" mencionada como
  capacidade do agente.
- **`fetch-note.mjs`** — busca documentação técnica de um sistema com acesso restrito. Guarda o estado da
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

### Controle de rede local e detecção de invasão (WSL Kali)

Roda dentro de uma distro Linux no WSL (o autor usa Kali), chamada a
partir do `panel/server.py`. Hoje cobre **controle/descoberta de rede sob
demanda** — a base necessária para detecção de invasão, mas ainda não a
detecção contínua em si:

- **`nmap -sn`** — varredura ativa de host discovery na sub-rede local.
- **`arp -a`** (do próprio Windows) — tabela ARP, complementa o nmap com
  MAC address de cada host.
- **tabela OUI do nmap** — resolve fabricante a partir do MAC.
- **`avahi-browse`** — nomes mDNS (`.local`) de dispositivos que anunciam
  serviços (AirPlay, Chromecast, HomeKit, SMB, etc.).

Isso já dá controle de rede completo *sob demanda*: apertar "Rede" no
painel mostra todo dispositivo ativo na LAN, com IP, MAC, fabricante e
nome. Para virar detecção de invasão de verdade falta rodar essa
varredura *continuamente* e **alertar sozinho** quando aparece um
dispositivo novo — isso ainda não existe, é só sob demanda.

**Limitação técnica a considerar antes de implementar um IDS passivo**
(Suricata/Snort/arpwatch clássico, que ficam "ouvindo" todo o tráfego da
LAN): o WSL2, por padrão, usa rede **NAT virtualizada** — a distro Linux
não enxerga o broadcast/ARP de outros hosts como se estivesse
fisicamente no mesmo segmento, só o próprio tráfego de ida/volta pelo NAT
do host Windows. Por isso `nmap -sn` (varredura **ativa**) funciona, mas
uma ferramenta de captura **passiva** não veria o tráfego alheio de forma
confiável nessa configuração padrão. Duas saídas: (a) o modo de rede
"mirrored" do WSL2 (versões mais novas do Windows), que aproxima a distro
da pilha de rede real do host — validar se a captura passiva funciona
nele; ou (b) aceitar a abordagem ativa e detectar por **diferença entre
varreduras periódicas**, que já funciona com a arquitetura atual.

**Design proposto (ainda não implementado) para detecção de invasão
real:**

1. Um script roda a mesma lógica de `scan_network()` periodicamente (ex:
   a cada 10 min), via Tarefa Agendada própria (mesmo padrão da
   `AgPSUltronDeck`: `pythonw.exe`, sem console, restart automático).
2. Persiste a lista de dispositivos conhecidos (IP + MAC) num arquivo
   local (`known_devices.json`).
3. A cada rodada, compara com a lista conhecida: MAC nunca visto →
   alerta de "dispositivo desconhecido na rede"; MAC conhecido com
   fabricante diferente do esperado → alerta (spoofing grosseiro).
4. O alerta usa o canal já existente — `hermes send --to telegram` via
   SSH — sem precisar construir notificação nova.
5. Dispositivo novo legítimo exige aprovação manual (adicionar à lista
   conhecida) pelo painel físico ou por comando ao agente no Telegram.

Isso entrega o valor real de "detecção de invasão" numa rede doméstica
(dispositivo estranho conectado = alerta), sem o custo de manutenção de
assinaturas de IDS de nível corporativo.

**Raptor — o ferramental de pentest que já existe no mesmo Kali**: o
autor já mantém, na mesma distro WSL, um framework de testes de
segurança chamado **Raptor** (`/opt/raptor`), com CLI unificada
(`raptor.py <modo>`) — é literalmente a ferramenta de pentest do Kali
usada para **proteger e atacar** de verdade os próprios dispositivos e
aplicações da rede, não só listar o que existe (isso quem faz é o
nmap/arp/avahi da seção acima). O modo `web`, por exemplo, serve tanto
para auditar o próprio painel/apps quanto para testar a segurança real
de qualquer dispositivo da LAN que exponha uma interface web (roteador,
TV, IoT). Não fica "ouvindo" passivamente a LAN — é ativo, sob demanda,
com os modos:

| Modo      | O que faz |
|-----------|-----------|
| `scan`    | Análise estática de código (Semgrep) |
| `sca`     | Software Composition Analysis — dependências, advisories, SBOM |
| `binary`  | Investigação black-box de binários |
| `fuzz`    | Fuzzing de binários (AFL++) |
| `web`     | Teste de segurança de aplicação web |
| `codeql`  | Análise só com CodeQL |
| `agentic` | Workflow autônomo completo (Semgrep + CodeQL + análise por LLM) |
| `analyze` | Análise de vulnerabilidade via LLM a partir de um SARIF já gerado |
| `describe`/`doctor` | Inspeção pré-execução / status do setup local |
| `frida`   | Instrumentação dinâmica (alpha) |

O papel real do Raptor nesta arquitetura é **complementar, não
substituir**, a detecção de invasão de rede: enquanto o nmap+arp+avahi
descobrem *dispositivos* na LAN, o Raptor pode rodar `web`/`scan`/`sca`
periodicamente contra as próprias superfícies expostas do sistema — o
`panel/server.py` (porta 8090, sem autenticação), o 9Router, ou qualquer
app publicado — para pegar vulnerabilidades de aplicação antes que virem
um vetor de invasão de fato. Isso fecha as duas pontas: **quem está na
minha rede** (nmap/arp) e **o que, nas minhas próprias aplicações, pode
ser explorado** (Raptor).

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
- **Estados de sessão de navegador (`estado-sessao.json` e
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

## Filosofia do agente

O Ag-PS-Ultron não é construído para um único caso de uso fixo — é uma
**base sólida e de propósito geral** (Hermes + 9Router + canais de
mensageria + ferramentas próprias), que se expande de duas formas
deliberadamente separadas:

1. **Pedindo ao agente, em conversa, para usar o que ele já tem** — o
   Hermes já sabe gerar relatório, checar status, controlar TV, navegar
   com login persistido etc.; boa parte do "crescimento" é simplesmente
   descobrir e pedir novas combinações do que já existe (um toolset
   diferente, uma skill diferente, um prompt mais específico).
2. **Desenvolvendo por fora e plugando** — quando falta uma capacidade de
   verdade nova (uma integração, uma automação, um script), ela é
   construída como código externo (uma skill nova, uma ferramenta em
   `/restrito` ou `/tools`, um toolset novo) e só depois oferecida ao
   agente para chamar.

O que este projeto **não** faz de propósito: deixar o agente reescrever
ou expandir a própria arquitetura sozinho, de forma autônoma, só a
partir de uma conversa. Mesmo o Hermes se descrevendo como "self-
improving" (cria/ajusta skills a partir do uso), a decisão de adicionar
uma capacidade nova de peso continua sendo humana e externa — o agente
aprende a usar melhor o que tem, não decide sozinho expandir seu próprio
raio de ação.

### Base de conhecimento pessoal — NotebookLM + biblioteca em PDF

Complementando o próprio modelo de IA, existe uma camada de pesquisa
paralela: uma biblioteca pessoal de livros em PDF, carregada no
[NotebookLM](https://notebooklm.google.com) (Google), usada como um RAG
(Retrieval-Augmented Generation) sobre esse material específico — o
NotebookLM responde perguntas ancoradas exatamente nos PDFs carregados,
em vez de conhecimento geral do modelo. Hoje isso é um fluxo **manual**
do usuário (consulta feita direto no NotebookLM, em paralelo ao agente),
não uma chamada automática que o Hermes faz sozinho — mas é uma fonte de
"conhecimento verdadeiro" real que informa decisões, no mesmo espírito
de "prover a base" descrito acima: dá para automatizar essa ponte no
futuro (ex: um toolset que consulta a API do NotebookLM), sem que isso
mude a filosofia — continuaria sendo um recurso que o agente *usa*
quando pedido, não algo que ele cria/expande sozinho.

## Possíveis expansões

Ambas as expansões abaixo são capacidades do **agente (Ultron/Hermes, na
VPS)**, não do painel físico — o painel só dispara o pedido (por
texto/voz ou por um novo botão); quem executaria a automação, guardaria
a sessão de login e geraria o resultado é sempre o Hermes.

- **Automação de navegador com login, como capacidade genérica do
  agente**: hoje `fetch-note.mjs` é uma automação específica para aquele sistema,
  rodando junto do agente na VPS; generalizar esse mesmo padrão (sessão
  de navegador persistida + Playwright) para outros sites com login
  daria ao Hermes a capacidade de logar em qualquer site e repetir
  tarefas (baixar relatório, preencher formulário, extrair dado) sob
  comando — reaproveitando a mesma ideia de estado de sessão salvo já
  usada pelo `fetch-note.mjs`, e devolvendo o resultado pelo mesmo canal
  (`hermes send`) já usado para o Telegram/painel. A decisão de segurança
  que falta resolver antes de generalizar: **onde e como as credenciais
  de cada site ficam guardadas** — via `hermes secrets` (Bitwarden/
  1Password, já suportado pelo próprio Hermes) é a opção mais alinhada
  com o resto da arquitetura, em vez de variável de ambiente ou `.env`.
- **Geração de relatórios/planilhas pelo agente**: o Hermes já gera
  relatório de reunião a partir do texto que o painel encaminha (a
  transcrição é feita no navegador do painel, mas quem escreve o
  relatório é o agente); o mesmo padrão — coletar dado (de uma automação
  de navegador, por exemplo) → mandar prompt estruturado ao Hermes →
  devolver texto — pode virar geração de planilha (`.xlsx` via
  `openpyxl`, rodando ao lado do Hermes na VPS) a partir de dados
  extraídos de uma automação de navegador, entregue por Telegram ou
  salva num storage compartilhado.
- **Dashboard unificado de status**: hoje `hermes status` e o status dos
  containers Docker são consultados via SSH sob demanda pelo painel;
  poderia virar um endpoint HTTP próprio do Hermes (via `hermes gateway`
  ou um webhook simples) para não depender de SSH a cada consulta.
- **Failover de modelo mais visível no painel**: o Hermes já tem
  `fallback` configurável; expor no card "Status VPS" qual modelo está
  ativo *no momento* (principal vs. fallback) ajudaria a perceber
  degradação de serviço mais cedo.
