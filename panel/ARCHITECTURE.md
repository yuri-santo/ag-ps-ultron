# Arquitetura

## Visão geral

```
+----------------------+        HTTP (LAN, porta 8090)        +---------------------------+
|  Celular / navegador  | ------------------------------------> |  server.py (Windows)      |
|  panel.html (PWA)     | <------------------------------------ |  http.server + threads    |
+----------------------+         JSON / text/html               +-------------+-------------+
                                                                              |
                    +---------------------------+---------------------------+---------------------------+
                    |                           |                           |                           |
                    v                           v                           v                           v
          subprocess/start              WSL (Kali Linux)             SSH (minha-vps)              Outlook COM
       (apps, mstsc, SendKeys)      nmap + arp + avahi (mDNS)   agente-cli / docker ps / curl   (PowerShell + COM)
```

O sistema inteiro roda em **três camadas**:

1. **Cliente (panel.html)** — uma PWA de página única. Não tem lógica de
   negócio: cada botão só faz `fetch()` para o servidor e mostra o
   resultado. Isso mantém o cliente trivial de rodar em qualquer navegador
   moderno (Android, iOS, desktop) sem build step.
2. **Servidor (server.py)** — um `ThreadingHTTPServer` da biblioteca
   padrão do Python, sem framework, ouvindo em `0.0.0.0:8090`. Cada request
   HTTP é tratado numa thread separada, então uma ação lenta (ex: escanear a
   rede, ~15s) não trava outras requisições (ex: o health-check do
   indicador de conexão).
3. **Integrações externas** — o servidor é o único ponto que sabe falar com
   o resto do mundo: processos locais do Windows, WSL, SSH para a VPS, e o
   Outlook via COM.

## Por que essa arquitetura (e não outra)

- **PWA em vez de app nativo**: zero fricção de instalação (é só abrir a
  URL e "Adicionar à tela inicial"), atualiza sozinho a cada load, funciona
  em qualquer celular na mesma rede Wi-Fi.
- **Servidor Python com stdlib, sem framework**: o painel só faz proxy de
  ações para o Windows — não há necessidade de roteamento sofisticado,
  ORM, templates etc. Adicionar uma dependência (Flask/FastAPI) só pra
  isso seria peso sem benefício real.
- **O servidor decide o que é permitido**: o cliente nunca manda um comando
  arbitrário — ele manda uma *chave* (`action: "vscode"`) que é resolvida
  contra um dicionário fixo (`ACTIONS`) no servidor. Isso é a base do
  modelo de segurança (ver abaixo).

## Rotas HTTP (protocolo de comunicação)

Todo o protocolo é HTTP simples com corpo JSON. Não há autenticação,
sessão ou HTTPS — o modelo de confiança é "só quem está na minha rede local
chega nessa porta" (ver seção Segurança).

| Método | Rota            | Corpo (request)                          | Resposta                                    | O que faz |
|--------|-----------------|-------------------------------------------|----------------------------------------------|-----------|
| GET    | `/`             | -                                          | `panel.html`                                  | Serve a PWA |
| GET    | `/manifest.json`| -                                          | `manifest.json`                               | Manifest da PWA |
| GET    | `/health`       | -                                          | `{"ok": true}`                                | Heartbeat (indicador de status no painel) |
| POST   | `/action`       | `{"action": "vscode", "payload": null}`   | `{"ok": bool, "cmd"/"error": ...}`            | Executa uma ação da tabela `ACTIONS` |
| POST   | `/agent`        | `{"text": "..."}`                         | `{"ok": bool, "output": "..."}`               | Envia texto ao agente remoto via SSH |
| POST   | `/network`      | -                                          | `{"cidr", "hosts": [...], "count"}`           | Escaneia a LAN |
| POST   | `/agent-status` | -                                          | `{"agent", "ai_gateway", "dockers": [...]}`   | Status da VPS via SSH |
| POST   | `/calendar`     | `{"day": "YYYY-MM-DD", "window": 1}`      | JSON específico do script de calendário       | Agenda do dia |

`Access-Control-Allow-Origin: *` está habilitado em todas as respostas —
necessário porque o painel pode ser aberto a partir de qualquer IP da LAN
apontando para o IP do PC, então a origem do fetch nem sempre bate com a do
servidor.

## Como cada integração conversa com o mundo externo

- **Apps locais / RDP / volume**: `subprocess.Popen(cmd, shell=True, ...)`
  disparando `start`, `mstsc` ou `powershell -Command "...SendKeys..."`.
  Rodam com `creationflags=subprocess.CREATE_NO_WINDOW` para não abrir
  janelas de console visíveis (importante quando o servidor roda via
  `pythonw.exe`, sem console próprio — sem essa flag, o Windows aloca um
  console novo e visível para cada processo filho de `shell=True`).
- **Scanner de rede**: chama `nmap -sn` dentro de uma distro WSL (Kali
  Linux) para descoberta de hosts, complementa com `arp -a` do próprio
  Windows para MAC address, resolve fabricante via a tabela OUI do nmap, e
  nomes `.local` via `avahi-browse` (também no WSL). Tudo em paralelo com
  `threading.Thread` por host para resolver hostname/mDNS/vendor sem
  serializar o scan inteiro.
- **Agente remoto / status da VPS / agenda**: tudo via
  `ssh -o BatchMode=yes -o ConnectTimeout=8 minha-vps "<comando remoto>"`.
  `BatchMode=yes` garante que, se a chave SSH não for aceita, falha rápido
  em vez de pendurar esperando senha. O "agente remoto" é um CLI próprio
  (não incluso neste repo) que roda na VPS e sabe encaminhar texto para um
  bot de mensageria, consultar o próprio status, etc.
- **Agenda (Outlook)**: existem duas abordagens no projeto original —
  `read_outlook_cal.ps1` lê o Outlook local via COM (`New-Object -ComObject
  Outlook.Application`), exige o Outlook desktop aberto na mesma máquina;
  a rota `/calendar` do `server.py`, em produção, na verdade consulta um
  script equivalente rodando *na VPS* via SSH — assim a agenda funciona de
  qualquer lugar, sem depender do Outlook estar aberto no PC do painel.

## Resiliência: por que o autostart importa (e o que já quebrou)

O servidor precisa ficar no ar o tempo todo, sem intervenção manual, porque
o painel é acessado do celular a qualquer hora. A solução é uma **Tarefa
Agendada do Windows**, não um serviço do Windows tradicional — porque as
ações (abrir apps visíveis, `SendKeys`, RDP) precisam rodar dentro de uma
sessão interativa de usuário, o que um Windows Service não tem por padrão.

Configuração da tarefa (`AgPSUltronDeck`):
- **Gatilho**: `LogonTrigger` — inicia quando o usuário faz login.
- **Principal**: `InteractiveToken` — roda como o usuário logado, com
  acesso à área de trabalho.
- **Restart automático**: até 999 tentativas, a cada 1 minuto, se o
  processo cair.
- **Ação**: `pythonw.exe "server.py"` — **não** `python.exe`.

O motivo do `pythonw.exe` (interpretador sem console) em vez de `python.exe`
é um problema real que já ocorreu: rodando com `python.exe`, o processo é um
app de console; quando a sessão sofre qualquer "close event" (janela de
console fechada, hibernação, reconexão de RDP), o Windows mata o processo
com `STATUS_CONTROL_C_EXIT` — e isso acontecia *antes* do mecanismo de
restart conseguir agir de forma confiável, deixando a tarefa parada até o
próximo login. Trocar para `pythonw.exe` (que não tem console para receber
esse evento) resolveu. Ver [SETUP.md](SETUP.md) para o passo a passo exato
de configuração dessa tarefa.

## Segurança

Este projeto assume um **modelo de confiança de rede local**: qualquer
dispositivo que alcançar a porta 8090 do PC pode disparar qualquer ação da
tabela `ACTIONS`, ler a agenda, escanear a rede e mandar comandos para o
agente remoto. Não há autenticação, autorização por usuário, nem HTTPS.
Isso é uma escolha deliberada de simplicidade para uso pessoal numa rede
doméstica confiável — **não é adequado para expor na internet** como está.

Pontos de atenção se você for construir o seu:

- **Nunca abra a porta 8090 no roteador/firewall para a internet.** Se
  precisar acessar de fora de casa, use uma VPN (WireGuard/Tailscale) até a
  sua rede local, nunca port-forward direto.
- **O dicionário `ACTIONS` é a única superfície de comando aceita** — o
  cliente nunca manda um comando de shell livre, só uma chave que já existe
  no servidor. Ao adicionar novas ações, evite interpolar `payload` do
  cliente direto em uma string de shell (`shell=True`); se precisar aceitar
  parâmetros do cliente, valide/sanitize antes (como já é feito em
  `set_volume`, que faz `clamp` e `int()` no valor recebido). Comandos que
  já usam `shell=True` com argumentos fixos (sem input do cliente) são
  seguros por não interpolarem dado externo, mas qualquer ação nova que
  aceite `payload` deve seguir o mesmo cuidado.
- **A chave SSH para a VPS deve ter passphrase vazia só se o agente SSH
  estiver protegido pelo login do Windows** — como o comando roda
  automaticamente e sem interação (`BatchMode=yes`), não há como digitar
  senha; a segurança dessa conexão depende inteiramente de quem tem acesso
  físico/remoto à sessão do Windows já ser confiável.
- **E-mails, hostnames e IPs reais nunca devem ir para um repositório
  público** — é exatamente o que foi sanitizado neste repo (troque os
  placeholders pelos seus valores reais só localmente, fora do controle de
  versão, ou num `.env`/`config.json` no `.gitignore`).

## Possíveis expansões

- **Autenticação mínima**: um token fixo (header `Authorization`) validado
  no `do_POST`, gerado uma vez e colado manualmente no painel — evita que
  qualquer dispositivo na rede (ex: um convidado no Wi-Fi) dispare ações,
  sem precisar de um sistema de login completo.
- **HTTPS local**: certificado autoassinado, para não trafegar em texto
  puro nem no Wi-Fi de casa.
- **Confirmação para ações destrutivas**: hoje qualquer ação dispara na
  hora; ações "perigosas" (ex: desligar o PC, fechar um app) poderiam pedir
  um segundo toque de confirmação no cliente.
- **Automação de navegador com login** (pedido explícito de expansão):
  adicionar uma rota `/browser-task` que aciona um motor de automação
  (Playwright é o candidato natural — já roda headless, tem gravação de
  sessão/cookies reutilizável) para logar em sites e repetir tarefas
  (baixar relatório, preencher formulário, extrair dados para planilha).
  Isso é tratado como uma feature separada, não incluída neste repo, porque
  envolve uma decisão importante de segurança: **onde e como as
  credenciais dos sites ficam guardadas** (cofre de senhas do SO via
  `keyring`, variável de ambiente, ou um `.env` local nunca commitado).
- **Geração de relatórios/planilhas**: o "modo reunião" já gera relatório
  via o agente remoto; o mesmo padrão (transcrever/coletar dado -> mandar
  prompt estruturado ao agente -> devolver texto) pode virar geração de
  planilha (`.xlsx` via `openpyxl` no lado do agente, ou no próprio
  `server.py`) a partir de dados extraídos de automações de navegador.
- **Múltiplos usuários/painéis**: hoje é um painel pessoal single-user; um
  arquivo `config.json` por usuário (em vez do dicionário `ACTIONS`
  hardcoded no código) permitiria reutilizar o mesmo `server.py` para
  outra pessoa sem editar o Python.
- **Notificações push**: hoje o painel só *mostra* estado quando aberto;
  um Service Worker com Push API poderia alertar (ex: reunião em 5 min,
  container caiu na VPS) mesmo com o app fechado.
