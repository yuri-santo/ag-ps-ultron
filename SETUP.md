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
