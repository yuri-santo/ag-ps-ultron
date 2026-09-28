#!/usr/bin/env bash
# Uso: disparar.sh SCRIPT.sh — roda o script desta pasta fora do gateway (systemd-run) e volta na hora.
W=/mnt/c/Users/yurim/ultron-team-20260913/wsl
S="$1"; case "$S" in */*|"") echo "script invalido"; exit 2;; esac
[ -f "$W/$S" ] || { echo "script nao encontrado: $S"; exit 2; }
systemd-run --collect --unit="ultron-$(basename "$S" .sh)-$(date +%s)" /bin/bash "$W/$S" > "$W/logs/disparo-$(basename "$S" .sh).txt" 2>&1 \
  || { setsid nohup /bin/bash "$W/$S" < /dev/null > /dev/null 2>&1 & }
echo "Disparado em segundo plano: $S (log em $W/logs)"
