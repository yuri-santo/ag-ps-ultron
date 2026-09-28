#!/usr/bin/env bash
# Corrige a janela "Windows Script Host - Permissão negada (800A0046), linha 14" do
# C:\Users\yurim\.hermes-autostart.vbs (âncora do WSL no logon), 28/09/2026.
# Diagnostica quem chama o VBS, faz backup, instala a versão nova (caminho completo do wsl.exe,
# novas tentativas sem janela de erro, sem âncora duplicada, log) e testa com cscript.
set -uo pipefail
REPO=/mnt/c/Users/yurim/ultron-team-20260913
NEWVBS=$REPO/wsl/autostart/hermes-autostart.vbs
LIVEVBS=/mnt/c/Users/yurim/.hermes-autostart.vbs
TS=$(date +%Y%m%dT%H%M%S)
LOGDIR=$REPO/wsl/logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/corrigir-autostart-$TS.log
exec > >(tee -a "$LOG") 2>&1
BK=$REPO/wsl/backups/autostart-$TS
winps() { /usr/local/bin/python3 /root/ultron-local/windows_exec.py --timeout "${2:-120}" --powershell "\$ErrorActionPreference='Continue';$1"; }
echo "== corrigir-autostart $TS"

echo "-- diagnóstico"
winps '
"boot: " + (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
"wsl.exe: " + ((Get-Command wsl.exe -All -ErrorAction SilentlyContinue | ForEach-Object Source) -join "; ")
Get-AppxPackage *WindowsSubsystemForLinux* -ErrorAction SilentlyContinue | ForEach-Object { "pacote WSL: " + $_.Version + " " + $_.InstallLocation }
"-- tarefas que chamam o VBS/wsl:"
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -match "hermes-autostart|wsl\.exe" } | ForEach-Object {
  $i = Get-ScheduledTaskInfo -InputObject $_ -ErrorAction SilentlyContinue
  "{0}{1} estado={2} ultima={3} resultado=0x{4:X} acoes={5}" -f $_.TaskPath,$_.TaskName,$_.State,$i.LastRunTime,$i.LastTaskResult,(($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " | ") }
"-- inicializar (pasta Startup e Run):"
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup","$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp" -ErrorAction SilentlyContinue | ForEach-Object { "startup: " + $_.FullName }
foreach ($k in "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run","HKLM:\Software\Microsoft\Windows\CurrentVersion\Run") { $p = Get-ItemProperty $k -ErrorAction SilentlyContinue; if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object { "run: " + $_.Name + " = " + $_.Value } } }
Select-String -Path "C:\HermesDesktop\scripts\*.ps1" -Pattern "hermes-autostart" -ErrorAction SilentlyContinue | ForEach-Object { "referencia: " + $_.Path + ":" + $_.LineNumber + " " + $_.Line.Trim() }
"-- âncoras wsl.exe agora:"
Get-CimInstance Win32_Process | Where-Object Name -eq "wsl.exe" | ForEach-Object { "pid " + $_.ProcessId + " desde " + $_.CreationDate + " :: " + $_.CommandLine }
"-- bloqueios do Defender (ASR) nas últimas 24h:"
Get-WinEvent -FilterHashtable @{LogName="Microsoft-Windows-Windows Defender/Operational"; Id=1121,1122; StartTime=(Get-Date).AddDays(-1)} -MaxEvents 5 -ErrorAction SilentlyContinue | ForEach-Object { $_.TimeCreated.ToString("s") + " " + (($_.Message -split "`n" | Select-Object -First 6) -join " ") }
' 180 || echo "(diagnóstico parcial)"

echo "-- backup e instalação"
mkdir -p "$BK"
[ -f "$LIVEVBS" ] && cp -p "$LIVEVBS" "$BK/.hermes-autostart.vbs" && echo "backup: $BK/.hermes-autostart.vbs"
if cmp -s "$LIVEVBS" "$NEWVBS"; then echo "VBS novo já instalado."; else cp "$NEWVBS" "$LIVEVBS" && echo "VBS novo instalado em C:\\Users\\yurim\\.hermes-autostart.vbs"; fi

echo "-- teste /check (sem efeito)"
out=$(winps '& "$env:SystemRoot\System32\cscript.exe" //nologo "$env:USERPROFILE\.hermes-autostart.vbs" /check; "exit=" + $LASTEXITCODE' 60)
echo "$out"
if ! echo "$out" | grep -q "check: wsl=" || ! echo "$out" | grep -q "exit=0"; then
  echo "!! VBS novo falhou no teste; restaurando o antigo"
  cp -p "$BK/.hermes-autostart.vbs" "$LIVEVBS"
  echo "RESULTADO_AUTOSTART=falhou_restaurado" ; exit 1
fi

echo "-- execução real (com âncora ativa só registra; sem âncora, cria uma)"
winps '& "$env:SystemRoot\System32\cscript.exe" //nologo "$env:USERPROFILE\.hermes-autostart.vbs"; "exit=" + $LASTEXITCODE' 240
echo "-- disparo pela própria tarefa agendada"
winps '$t = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { ($_.Actions | ForEach-Object { $_.Arguments }) -match "hermes-autostart" } | Select-Object -First 1
if ($t) { Start-ScheduledTask -InputObject $t; Start-Sleep 12; $i = Get-ScheduledTaskInfo -InputObject $t; "tarefa " + $t.TaskName + " resultado=0x{0:X}" -f $i.LastTaskResult } else { "nenhuma tarefa referencia o VBS" }
"-- log do VBS:"
Get-Content "$env:LOCALAPPDATA\hermes-autostart.log" -Tail 6 -ErrorAction SilentlyContinue' 90
echo "RESULTADO_AUTOSTART=ok"
