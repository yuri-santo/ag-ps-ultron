# Passo a passo: construindo o seu Deck

## Pré-requisitos

- Windows 10/11 (o projeto usa `mstsc`, `SendKeys`, Task Scheduler — é
  Windows-específico).
- Python 3.10+ instalado (sem dependências externas — só stdlib).
- Opcional: WSL com uma distro Linux (o autor usa Kali) para o scanner de
  rede (`nmap`, `avahi-browse`).
- Opcional: acesso SSH a uma VPS/servidor remoto, se quiser as features de
  "agente remoto" e agenda via VPS.
- Opcional: Outlook desktop, se quiser a variante local de agenda
  (`read_outlook_cal.ps1`).

## 1. Estrutura de pastas

```
meu-deck/
  server.py        # servidor HTTP
  panel.html        # a PWA
  manifest.json     # manifest da PWA
```

Copie os três arquivos deste repositório para uma pasta no seu PC (ex:
`D:\GIT\meu-deck`).

## 2. Personalize as ações

Abra `server.py` e edite o dicionário `ACTIONS`:

- Troque os caminhos dos executáveis (`vscode`, `notepadpp`, etc.) pelos
  caminhos reais no seu PC.
- Troque os hosts de RDP (`rdp_host1`, `rdp_host2`, `rdp_host3`) pelos seus
  próprios IPs/hostnames.
- Se não for usar `agent_status`/`agent`/`calendar`/`network`, pode remover
  esses handlers de `do_POST` e as funções correspondentes — são
  independentes entre si.
- Se for usar o agente remoto, troque `minha-vps` pelo alias configurado no
  seu `~/.ssh/config` (`Host minha-vps` -> `HostName`, `User`,
  `IdentityFile`), e `/root/.local/bin/meu-agente-cli` pelo caminho real do
  seu CLI na VPS.

Abra `panel.html` e edite os botões (`data-action="..."`) para bater com as
chaves que você definiu em `ACTIONS`, e os textos/labels visíveis.

## 3. Teste local

```
python server.py
```

Abra `http://localhost:8090` no navegador do próprio PC. Confirme que os
botões disparam as ações esperadas e que `/health` responde `{"ok": true}`.

## 4. Acesse do celular (mesma rede Wi-Fi)

1. Descubra o IP local do PC: `ipconfig` (procure o IPv4 do adaptador
   Wi-Fi/Ethernet, algo como `192.168.1.x`).
2. No celular, na mesma rede, abra `http://192.168.1.x:8090`.
3. No navegador (Chrome/Safari), use "Adicionar à tela inicial" — o
   `manifest.json` faz o app abrir em tela cheia, sem barra de navegador.

Se não conectar, confira o Firewall do Windows: pode ser necessário liberar
a porta 8090 para redes privadas (nunca para redes públicas/internet).

## Preparando o celular físico (requisitos, modo quiosque e ideias)

O "celular velho" não é só uma tela — dá pra montar um dispositivo
dedicado de verdade. O que ele precisa ter, e o que vale a pena.

### Requisitos mínimos

- **Android/iOS com navegador atualizado** (Chrome/Safari) — é só uma
  PWA, não precisa de app nativo nem loja de aplicativo.
- **Wi-Fi fixo configurado** para a rede de casa, com "esquecer redes
  automaticamente" desligado (senão ele some da rede sozinho).
- **Carregador permanente** — o celular fica ligado na tomada o tempo
  todo; use um carregador de qualidade (evita degradar a bateria rápido
  com carga 100% constante — alguns Android têm "limite de carga" nas
  configurações de bateria, vale ativar se existir).
- **Tela sempre ligada**: em "Configurações > Tela > Tempo limite",
  coloque o máximo, e/ou use a opção de desenvolvedor "manter ligado
  durante carregamento" — o `panel.html` já pede `navigator.wakeLock`
  via JS, mas ter o SO configurado como reforço evita a tela apagar em
  navegadores que ignoram o wake lock em segundo plano.
- **Desabilitar otimização de bateria para o navegador** — Android mata
  processos em segundo plano agressivamente; sem isso, o painel pode
  "dormir" e parar de atualizar status/agenda.

### Modo quiosque (travar o celular só no painel)

Sem isso, qualquer toque acidental sai do painel e cai na home do
Android. Duas opções:

- **App Pinning nativo do Android** (Configurações > Segurança > Fixar
  app): abre o Chrome no painel, ativa o pin — o botão "voltar"/"home"
  fica bloqueado até destravar com PIN. Grátis, já vem no sistema, sem
  instalar nada.
- **Fully Kiosk Browser** (app dedicado, mais robusto): trava em tela
  cheia, recarrega sozinho se a página cair, pode auto-iniciar no boot
  do celular sem precisar desbloquear a tela, e tem um modo "screensaver"
  que nunca deixa a tela apagar de verdade. Vale o investimento se o
  celular for ficar de vez montado num suporte de parede/mesa.

### Ideias do que mais vale a pena ter nesse celular

Como esse mesmo celular já roda um **userland Linux completo por dentro**
(via WireGuard, ver [NETWORK.md](../NETWORK.md#3-o-celular-do-painel-também-é-um-nó-linux-completo)),
ele não precisa ser só uma tela passiva — dá pra aproveitar o hardware:

- **Suporte de parede/mesa** — vira um "painel de controle" físico de
  verdade, tipo um termostato inteligente.
- **App de câmera IP** (ex: apontando pro cômodo onde fica) — reaproveita
  a câmera do celular como mais um ponto de monitoramento doméstico,
  complementar ao scanner de rede.
- **Automação por NFC** — colar uma tag NFC perto do suporte para
  disparar uma rotina (ex: "modo cinema": TV liga, luzes apagam) tocando
  o celular nela, sem precisar nem abrir o painel.
- **Node auxiliar de automação** — já que o userland Linux dele está na
  mesma malha WireGuard da VPS, pequenos scripts/cron *locais* (ex: ler
  um sensor conectado via USB-OTG, rodar um teste de latência da própria
  rede de casa "de dentro") podem rodar direto nele, sem depender da VPS
  estar de pé.
- **Segundo canal de notificação** — como ele já está sempre ligado e na
  tela, uma notificação push simples (ou até só o toast do próprio
  painel) pode servir de alerta visual imediato (reunião em breve,
  dispositivo novo na rede) sem depender do celular principal do usuário
  estar por perto.

### No que ele efetivamente ajuda, resumindo

Mais do que "um monte de botões", esse celular fixo é: **um ponto de
controle físico instantâneo** (mais rápido que abrir um app no celular
principal), **um segundo canal de notificação sempre visível**, e **um nó
de rede próprio** (por causa do userland Linux) que o agente pode usar
para automações que precisam rodar fisicamente dentro de casa — não só
uma tela bonita para os botões.

## 5. Autostart resiliente (o passo que mais importa)

Rodar `python server.py` manualmente não sobrevive a um reboot nem a um
logout. A solução testada é uma Tarefa Agendada do Windows configurada para
reiniciar sozinha se cair — com um detalhe importante: **use `pythonw.exe`,
não `python.exe`**, para não deixar (nem arriscar fechar) uma janela de
console.

Via PowerShell (ajuste os caminhos):

```powershell
$action = New-ScheduledTaskAction `
  -Execute "C:\Caminho\Para\Python\pythonw.exe" `
  -Argument '"D:\GIT\meu-deck\server.py"' `
  -WorkingDirectory "D:\GIT\meu-deck"

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -MultipleInstances IgnoreNew -Hidden -ExecutionTimeLimit 0

Register-ScheduledTask -TaskName "MeuDeck" `
  -Action $action -Trigger $trigger -Settings $settings
```

Pontos que fazem diferença real:
- **`pythonw.exe`** em vez de `python.exe` — evita que o processo receba
  `STATUS_CONTROL_C_EXIT` quando a janela de console (que nem deveria
  existir) sofrer um "close event" (lock de tela, hibernação, reconexão de
  sessão).
- **`-Hidden`** — a tarefa não deixa vestígio de janela.
- **`RestartCount`/`RestartInterval`** — se o processo cair por qualquer
  outro motivo, ele volta sozinho em até 1 minuto, até 999 vezes.
- Dentro do próprio `server.py`, toda chamada de `subprocess.Popen`/
  `subprocess.run` que dispara um processo do Windows (RDP, volume, SSH,
  nmap...) usa `creationflags=subprocess.CREATE_NO_WINDOW`. Sem essa flag,
  cada ação clicada no painel abriria uma janela de console visível no PC
  — porque `shell=True` cria um `cmd.exe` novo, e sem console próprio
  herdado (já que o servidor roda via `pythonw.exe`), o Windows aloca uma
  janela nova para cada um.

Para testar o autostart sem reiniciar o PC:

```powershell
Start-ScheduledTask -TaskName "MeuDeck"
Invoke-WebRequest http://127.0.0.1:8090/health -UseBasicParsing
```

## 6. (Opcional) Scanner de rede via WSL

1. Instale uma distro no WSL com `nmap` e `avahi-utils`:
   ```
   wsl --install -d kali-linux
   wsl -d kali-linux -- sudo apt install -y nmap avahi-utils
   ```
2. Ajuste, em `server.py`, o nome da distro (`"kali-linux"`) se usar outra.
3. O scan roda `nmap -sn` na sub-rede `192.168.1.0/24` por padrão — ajuste
   se a sua rede usar outra faixa.

## 7. (Opcional) Agente remoto via SSH

1. Gere/configure uma chave SSH sem senha (ou com o agente SSH do Windows
   desbloqueado junto com o login) para a sua VPS.
2. Adicione um alias no `~/.ssh/config`:
   ```
   Host minha-vps
     HostName seu-servidor.exemplo.com
     User root
     IdentityFile ~/.ssh/sua_chave
   ```
3. Teste manualmente: `ssh minha-vps echo ok` deve funcionar sem pedir
   senha nem confirmação.
4. Do lado da VPS, você precisa de um CLI/script próprio que receba texto
   (para `/agent`) e devolva status em texto (para `/agent-status`) — isso
   é específico de cada setup e não está incluído aqui.

## Troubleshooting

**O painel não abre no celular**: confirme que o PC e o celular estão na
mesma rede Wi-Fi (não em VLANs/guest network separadas), e que o Firewall
do Windows libera a porta 8090 para "Rede Privada".

**Uma ação clicada não faz nada**: rode `python server.py` manualmente (sem
`pythonw`) e observe o console — erros de caminho de executável aparecem
ali.

**Janelas de console piscando ao clicar em ações**: falta
`creationflags=subprocess.CREATE_NO_WINDOW` em alguma chamada de
`subprocess` — confira `run()` e toda função que chama `subprocess.run`.

**A tarefa agendada não reinicia depois que o processo cai**: verifique
com `Get-ScheduledTaskInfo -TaskName "MeuDeck"` o campo `LastTaskResult`.
Um valor `3221225786` (`0xC000013A`, `STATUS_CONTROL_C_EXIT`) indica que o
processo foi morto por um "close event" de console — troque para
`pythonw.exe` como descrito no passo 5.
