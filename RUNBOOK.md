# Runbook — exatamente o que foi feito

Registro passo a passo de todo o trabalho de diagnóstico, correção e
documentação realizado neste projeto: cada comando usado e o que ele
revelou. Serve como referência para reproduzir o setup do zero ou
entender por que cada decisão foi tomada.

## 1. Diagnóstico: por que o painel não subia sozinho

Sintoma: o painel deveria iniciar automaticamente e não estava.

```powershell
# Nenhum processo/serviço da Elgato — confirma que é um painel próprio, não o app oficial
Get-Process | Where-Object { $_.ProcessName -like "*stream*" -or $_.ProcessName -like "*elgato*" }
Get-CimInstance Win32_Service | Where-Object { $_.DisplayName -like "*Stream Deck*" }

# Achou o projeto real
Get-ChildItem -Path "D:\GIT" -Directory | Where-Object { $_.Name -like "*stream*" }
# -> D:\GIT\streamdeck

# Servidor não estava escutando na porta
Get-NetTCPConnection -LocalPort 8090 -ErrorAction SilentlyContinue

# Achou a Tarefa Agendada responsável por subir o servidor
Get-ScheduledTask | Where-Object { $_.TaskName -like "*deck*" }
# -> YuriStreamDeck, State: Ready (não Running)

Get-ScheduledTaskInfo -TaskName "YuriStreamDeck" | Select-Object LastRunTime, LastTaskResult
# -> LastTaskResult: 3221225786 (0xC000013A = STATUS_CONTROL_C_EXIT)

Export-ScheduledTask -TaskName "YuriStreamDeck"
# -> confirmou: Action = python.exe (não pythonw.exe), LogonTrigger, RestartOnFailure
#    Count=999 Interval=PT1M (deveria reiniciar sozinho e não estava reiniciando)
```

**Observação:** `python.exe` é um processo de console. Quando a sessão
sofre um "close event" (janela fechada, lock, hibernação, reconexão de
RDP), o Windows mata o processo com `STATUS_CONTROL_C_EXIT` — e isso
acontecia antes do mecanismo de restart conseguir agir de forma
confiável, deixando a tarefa parada até o próximo login.

## 2. Correção: autostart resiliente

```powershell
$action = New-ScheduledTaskAction `
  -Execute "C:\Users\<usuario>\AppData\Local\Programs\Python\Python314\pythonw.exe" `
  -Argument '"D:\GIT\streamdeck\server.py"' `
  -WorkingDirectory "D:\GIT\streamdeck"
Set-ScheduledTask -TaskName "YuriStreamDeck" -Action $action

$task = Get-ScheduledTask -TaskName "YuriStreamDeck"
$settings = $task.Settings
$settings.Hidden = $true
Set-ScheduledTask -TaskName "YuriStreamDeck" -Settings $settings

Start-ScheduledTask -TaskName "YuriStreamDeck"
Invoke-WebRequest -Uri "http://127.0.0.1:8090/health" -UseBasicParsing
# -> {"ok": true}
```

**Observação:** trocar `python.exe` por `pythonw.exe` (sem console) e
marcar a tarefa como `Hidden` elimina a exposição ao "close event". O
`RestartOnFailure` já configurado (999x / 1min) passa a funcionar de
verdade.

## 3. Correção: janelas de console piscando a cada ação

Sintoma reportado depois: toda ação clicada no painel abria uma janela de
terminal visível.

**Causa:** `subprocess.Popen(cmd, shell=True, ...)` sem console próprio
herdado (já que o servidor roda via `pythonw.exe`) faz o Windows alocar
uma janela nova de `cmd.exe` para cada ação.

**Correção:** adicionar `creationflags=subprocess.CREATE_NO_WINDOW` em
toda chamada de `subprocess.Popen`/`subprocess.run` do `server.py`
(12 pontos: `run()`, `send_to_ultron()`, `vps_status()` x3,
`get_calendar()`, `get_lan_cidr()`, `load_oui()`, `resolve_mdns()`,
`scan_network()` x2, `resolve()` interno).

```powershell
# Reiniciar o servidor depois de editar o server.py
Stop-ScheduledTask -TaskName "YuriStreamDeck"
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
Start-ScheduledTask -TaskName "YuriStreamDeck"
Invoke-WebRequest -Uri "http://127.0.0.1:8090/health" -UseBasicParsing
```

## 4. Criação do repositório de documentação (sanitizado)

```bash
# Verificar auth do gh e estado de git do projeto original
git status   # (dentro de D:\GIT\streamdeck) -> não era um repo git
gh auth status

# Pasta separada para a cópia sanitizada — NUNCA editar os arquivos reais
mkdir -p /d/GIT/yuri-deck
```

Cópias de `server.py`/`panel.html` foram escritas com IPs, hostnames de
EC2, e-mails e nomes de VPS reais trocados por placeholders
(`SEU_IP_AQUI`, `seu-servidor.exemplo.com`, `minha-vps` etc.) — nunca por
`sed`/edição do original, sempre reescrevendo a cópia do zero.

```bash
cd /d/GIT/yuri-deck
git init
git add -A
git commit -m "..."

gh repo create yuri-deck --private --source=. --remote=origin --push
# -> falhou: "Host key verification failed" (chave do GitHub não confiável)

ssh-keyscan -t rsa,ed25519 github.com >> ~/.ssh/known_hosts
git push -u origin HEAD
# -> falhou: "Permission denied (publickey)" (sem chave SSH configurada p/ GitHub)

# Solução: trocar para HTTPS usando o token já autenticado do gh
git remote set-url origin https://github.com/yuri-santo/yuri-deck.git
gh auth setup-git
git push -u origin HEAD
# -> sucesso
```

**Observação:** antes de cada push, rodar um grep de sanidade —
confirma que nada sensível escapou da sanitização:

```bash
grep -riE "10\.20\.20\.10|187\.77\.35\.139|minha-vps|meudominio|meuusuario" /d/GIT/yuri-deck
# -> No files found
```

## 5. Levantamento da arquitetura real do agente (VPS)

Tudo via SSH, somente leitura, usando o mesmo alias já configurado que o
`server.py` usa em produção:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 minha-vps "/root/.local/bin/hermes status"
# -> revelou: modelo ag/gemini-3.7-flash-high via "Custom endpoint" (9Router),
#    Telegram configurado, Gateway Service rodando via docker

ssh minha-vps "ls -la /root/.local/bin/ ; ls -la /root/tools/"
# -> hermes (symlink p/ /usr/local/lib/hermes-agent), agy, tron, uv/uvx
#    /root/tools: scripts de calendário (cal_daily2.py) + MS Graph/Google auth

ssh minha-vps "docker ps --format '{{.Names}}|{{.Status}}'"
# -> confirma quais containers rodam na VPS (importante: a VPS também hospeda
#    projetos NÃO relacionados ao agente pessoal - excluídos da documentação)

ssh minha-vps "hermes --help"
# -> lista completa de subcomandos do Hermes (chat, model, moa, gateway,
#    secrets, egress, send, status, ...)

ssh minha-vps "crontab -l"
ssh minha-vps "find / -maxdepth 6 -iname '*telegram*' -o -iname '*lg-control*'"
# -> achou /root/sap/lg-control.mjs (controle de TV LG) e confirmou que o
#    Telegram é nativo do Hermes (hermes_cli/telegram_managed_bot.py)

ssh minha-vps "ls -la /root/sap/"
# -> lg-control.mjs, fetch-note.mjs, sap-storage-state.json (sessão de
#    navegador persistida - tratado como segredo, nunca lido/copiado)
```

## 6. Investigação do WSL Kali (rede + segurança)

```bash
wsl -d kali-linux -- bash -c "which nmap arp-scan arpwatch suricata snort fail2ban-client"
# -> só nmap instalado; nenhum IDS de rede passivo configurado

wsl -d kali-linux -- bash -c "find / -maxdepth 4 -iname '*raptor*'"
# -> achou um framework próprio de segurança em /opt/raptor e ~/raptor

wsl -d kali-linux -- bash -c "cd /opt/raptor && python3 raptor.py --help"
# -> confirma os modos: scan (Semgrep), sca, binary, fuzz (AFL++), web,
#    codeql, agentic, analyze, describe, doctor, frida
```

**Observação:** Raptor é uma ferramenta de teste de segurança de
código/binário/app web — não um IDS de rede. A detecção de dispositivo
novo na LAN continua sendo um design proposto (ver ARCHITECTURE.md),
ainda não implementado.

## 7. Reestruturação e rename do repositório

```bash
cd /d/GIT/yuri-deck
mkdir -p panel
git mv server.py panel/server.py
git mv panel.html panel/panel.html
git mv manifest.json panel/manifest.json
git mv SETUP.md panel/SETUP.md
git mv ARCHITECTURE.md panel/ARCHITECTURE.md
# (novo README.md e ARCHITECTURE.md escritos na raiz, cobrindo o sistema todo)
```

**Cuidado real que aconteceu aqui:** um `mv /d/GIT/yuri-deck /d/GIT/ag-ps-ultron`
foi tentado para renomear a pasta, mas `D:\GIT\Ag-ps-Ultron` **já existia**
como a pasta de trabalho real do usuário (com dados reais, não
versionada). Como o Windows é case-insensitive, o `mv` colocou o
repositório git *dentro* da pasta real em vez de renomear — o que quase
resultou em dar `git add` num diretório com arquivos reais (IPs, e-mails).
Detectado antes do `git add` com um `ls` de verificação; corrigido
movendo o repositório para um caminho separado:

```bash
mv "/d/GIT/Ag-ps-Ultron/yuri-deck" "/d/GIT/ag-ps-ultron-repo"
# -> pasta de trabalho real do usuário (D:\GIT\Ag-ps-Ultron) ficou intocada
```

```bash
cd /d/GIT/ag-ps-ultron-repo
git add -A
git commit -m "..."

gh repo rename ag-ps-ultron --repo yuri-santo/yuri-deck --yes
git remote set-url origin https://github.com/yuri-santo/ag-ps-ultron.git
git push -u origin HEAD

gh repo view yuri-santo/ag-ps-ultron --json name,visibility,url
# -> {"name":"ag-ps-ultron","visibility":"PRIVATE", ...}
```

## Lições / padrões que valem para o próximo componente

- **Sempre `ls`/`diff` antes de mover pastas** quando existe qualquer
  chance de colisão de nomes (ainda mais em Windows, case-insensitive).
- **Nunca editar a cópia real** ao sanitizar — sempre escrever a cópia
  sanitizada num arquivo/pasta separado, e rodar um grep de sanidade
  antes de cada `git push`.
- **`pythonw.exe` + `Hidden` + `RestartOnFailure`** é o padrão a repetir
  para qualquer novo processo de longa duração no Windows controlado por
  Tarefa Agendada.
- **`creationflags=subprocess.CREATE_NO_WINDOW`** em toda chamada de
  subprocess que dispara um processo do Windows a partir de um script sem
  console.
