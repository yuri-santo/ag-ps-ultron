# Yuri Deck

Painel de controle pessoal em formato PWA (instalável no celular como app),
que fala com um servidor HTTP local no PC para disparar ações do dia a dia:
abrir programas, conectar em servidores remotos (RDP), controlar volume,
escanear a rede local, consultar a agenda e conversar com um agente de IA
remoto rodando em uma VPS.

Este repositório documenta a arquitetura completa e o passo a passo para
construir o seu próprio painel do zero. O código aqui é uma **cópia
sanitizada** do projeto real do autor — hostnames, IPs e e-mails reais foram
trocados por placeholders (`SEU_IP_AQUI`, `seu-servidor.exemplo.com` etc.).

## Índice

- [ARCHITECTURE.md](ARCHITECTURE.md) — arquitetura completa, protocolo de
  comunicação, modelo de segurança e ideias de expansão.
- [SETUP.md](SETUP.md) — passo a passo para construir e colocar no ar,
  incluindo o autostart resiliente no Windows (Task Scheduler).

## O que ele é capaz de fazer

**Lançar programas locais** — VS Code, Notepad++, OBS, Notion, WhatsApp,
Telegram, Xbox App, prompt de comando, com um toque.

**Atalhos de RDP** — abre `mstsc` direto para hosts/IPs pré-configurados, ou
um arquivo `.rdp` salvo, sem precisar digitar endereço.

**Controle de volume** — sobe, desce, muda, ou define um nível específico
(via `SendKeys` do Windows, com fallback para `nircmd` se instalado).

**Scanner de rede local** — descobre dispositivos na LAN combinando `nmap`
(via WSL/Kali), ARP do Windows e resolução de nomes mDNS (avahi), mostrando
IP, MAC, fabricante e hostname de cada um.

**Status de infraestrutura remota** — consulta via SSH o estado de uma VPS:
um agente de IA próprio (gateway, sessões, última atividade), um gateway de
IA local à VPS, e a lista de containers Docker rodando (com healthcheck
visual: ativo/caído).

**Ping rápido** — testa conectividade com um host remoto com um toque.

**Agenda do dia** — mostra reuniões de um ou mais calendários (Outlook/
Exchange) num card no topo do painel, com navegação por dia, agrupamento por
pessoa, e alerta quando uma reunião está prestes a começar.

**Comando de voz para o agente remoto** — um campo de texto com
reconhecimento de fala (Web Speech API) que envia comandos em linguagem
natural para o agente de IA na VPS via SSH.

**Modo reunião** — grava e transcreve continuamente (client-side, no
navegador) durante uma reunião e, ao finalizar, pede ao agente remoto para
gerar um relatório profissional (participantes, decisões, pendências,
próximos passos).

**PWA instalável** — `manifest.json` permite "Adicionar à tela inicial" no
celular, rodando em tela cheia como um app nativo, com wake-lock para manter
a tela ligada.

## Stack

- **Backend:** Python 3.10+, só biblioteca padrão (`http.server`,
  `subprocess`, `threading`) — zero dependências externas.
- **Frontend:** HTML/CSS/JS puro, sem framework, uma única página.
- **Integrações opcionais:** WSL (Kali Linux) para `nmap`/`avahi`, SSH para
  uma VPS remota, COM do Outlook via PowerShell.
- **Autostart:** Tarefa Agendada do Windows (`pythonw.exe`, sem console,
  com restart automático em caso de falha).

Veja [ARCHITECTURE.md](ARCHITECTURE.md) para o diagrama completo e
[SETUP.md](SETUP.md) para construir o seu.
