#!/usr/bin/env bash
# Stream Deck: tudo que abriria outra página/site/app abre no Saitama, nunca no celular (27/09/2026).
#   - POST /open (desktop_open.py): links http/https e protocolos de reunião abrem no Windows;
#   - abrir-local.js: links externos, window.open e links dentro dos painéis embutidos viram /open;
#   - "Entrar" em reunião: Teams/Zoom pelo app, Meet/Webex/GoTo/Whereby/Jitsi/Chime no navegador do desktop;
#   - botões "Abrir … no Saitama" voltam a abrir no desktop (o hub.js os desviava para telas no celular);
#   - atalhos ↗ de e-mails/reuniões abrem o Outlook (caixa/calendário) no Saitama.
# Backup, testes com o Python do Windows, restauração automática e reinício do painel (só se não houver gravação).
set -euo pipefail
REPO=/mnt/c/Users/yurim/ultron-team-20260913
SRC=$REPO/wsl/streamdeck-patch
SNAP=$REPO/wsl/streamdeck-snapshot
DECK=/mnt/d/GIT/streamdeck
LOGDIR=$REPO/wsl/logs
TS=$(date +%Y%m%dT%H%M%S)
mkdir -p "$LOGDIR"
LOG=$LOGDIR/aplicar-streamdeck-$TS.log
exec > >(tee -a "$LOG") 2>&1
BK=/mnt/d/GIT/_backups/streamdeck-$TS
CHANGED="meeting_controls.py server.py deck.html hub.js test_meeting_controls.py test_deck.py"
NEW="desktop_open.py abrir-local.js test_desktop_open.py"
winps() { /usr/local/bin/python3 /root/ultron-local/windows_exec.py --timeout "${2:-120}" --powershell "\$ErrorActionPreference='Continue';$1"; }
echo "== aplicar-streamdeck $TS"

all_applied() { local f; for f in $CHANGED $NEW; do cmp -s "$DECK/$f" "$SRC/$f" || return 1; done; }
state=novo
if all_applied; then
  state=aplicado; echo "Arquivos já aplicados; sigo para testes e reinício."
else
  for f in $CHANGED; do
    if ! cmp -s "$DECK/$f" "$SNAP/$f" && ! cmp -s "$DECK/$f" "$SRC/$f"; then
      echo "ABORTADO: $DECK/$f mudou desde a análise (não sobrescrevo trabalho novo)."; exit 3
    fi
  done
fi

restore() {
  echo "!! restaurando $BK"
  for f in $CHANGED; do [ -f "$BK/$f" ] && cp -p "$BK/$f" "$DECK/$f"; done
  for f in $NEW; do
    if [ -f "$BK/$f" ]; then cp -p "$BK/$f" "$DECK/$f"
    elif [ -f "$BK/.novo-$f" ] && [ -f "$DECK/$f" ]; then mv "$DECK/$f" "$BK/removido-$f"; fi
  done
}

mkdir -p "$BK"
for f in $CHANGED $NEW; do
  if [ -f "$DECK/$f" ]; then cp -p "$DECK/$f" "$BK/$f"; else : > "$BK/.novo-$f"; fi
done
echo "backup: $BK"
if [ "$state" = novo ]; then
  for f in $CHANGED $NEW; do cp "$SRC/$f" "$DECK/$f"; done
  echo "arquivos copiados para $DECK"
fi

# Testes com o mesmo Python do painel (Windows); se não houver interop, testa com o Python do WSL + shims.
tests="test_desktop_open test_meeting_controls test_deck test_hub test_hub_media test_deck_auth test_local_runtime test_librechat_proxy test_finance_proxy"
ok=0
wout=$(winps "Set-Location 'D:\GIT\streamdeck'; \$py = Join-Path \$env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'; & \$py 'C:\Users\yurim\ultron-team-20260913\wsl\streamdeck-patch\_run_tests.py' $tests; 'exit=' + \$LASTEXITCODE" 300 || true)
echo "$wout" | tail -8
echo "$wout" | grep -q "exit=0" && echo "$wout" | grep -q "RESULTADO_TESTES OK" && ok=1
if [ $ok = 0 ]; then
  echo "(testando com Python do WSL + shims do Windows)"
  T=$(mktemp -d); cp -r "$DECK"/. "$T"/ 2>/dev/null || true
  cat > "$T/_run_linux.py" <<'PY'
import os, subprocess, sys, ctypes, types, unittest
os.startfile = lambda *a, **k: None
subprocess.CREATE_NO_WINDOW = 0
if not hasattr(ctypes, 'windll'): ctypes.windll = types.SimpleNamespace(user32=types.SimpleNamespace(keybd_event=lambda *a: None))
sys.path.insert(0, os.getcwd())
r = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]))
sys.exit(0 if r.wasSuccessful() else 1)
PY
  ( cd "$T" && DECK_AUTH_FILE="$T/sess.json" DECK_NETWORK_FILE="$T/net.json" python3 _run_linux.py $tests 2>&1 | tail -6 ) && \
    ( cd "$T" && DECK_AUTH_FILE="$T/sess.json" DECK_NETWORK_FILE="$T/net.json" python3 _run_linux.py $tests >/dev/null 2>&1 ) && ok=1
  rm -rf "$T"
fi
if [ $ok = 0 ]; then restore; echo "ABORTADO: testes falharam; painel restaurado."; exit 4; fi
echo "testes: ok"

# Reinício do painel: não interrompe gravação de reunião em andamento.
rec=$(curl -s --max-time 8 http://127.0.0.1:8090/meeting/status || true)
if echo "$rec" | grep -q '"recording": *true\|"status": *"active"\|"status": *"paused"'; then
  echo "Reunião/gravação em andamento: NÃO reiniciei. Os arquivos novos entram no próximo reinício do painel."
  exit 0
fi
winps "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { \$_.CommandLine -like '*GIT\\streamdeck\\server.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force; 'parado pid ' + \$_.ProcessId }
Start-Sleep 2
\$t = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { (\$_.Actions | ForEach-Object { \"\$(\$_.Execute) \$(\$_.Arguments)\" }) -match 'streamdeck' } | Select-Object -First 1
if (\$t) { Start-ScheduledTask -InputObject \$t; 'iniciado pela tarefa ' + \$t.TaskName } else { & 'D:\GIT\streamdeck\watchdog.ps1'; 'iniciado pelo watchdog.ps1' }" 60 || true
for i in $(seq 1 45); do curl -s --max-time 3 http://127.0.0.1:8090/health | grep -q ok && break; sleep 2; done
echo "health: $(curl -s --max-time 5 http://127.0.0.1:8090/health || echo indisponivel)"
curl -s --max-time 5 http://127.0.0.1:8090/abrir-local.js | grep -q abrirNoSaitama && echo "abrir-local.js servido: ok" || echo "abrir-local.js: NÃO servido"
curl -s --max-time 5 http://127.0.0.1:8090/ | grep -q '/abrir-local.js' && echo "deck.html carrega abrir-local.js: ok" || echo "deck.html sem abrir-local.js"
# /open rejeita alvo perigoso (sem abrir nada no desktop):
echo "open file:// -> $(curl -s --max-time 5 -H 'Content-Type: application/json' -d '{"url":"file:///C:/Windows/System32/cmd.exe"}' http://127.0.0.1:8090/open)"
echo "== concluído. Log: $LOG"
