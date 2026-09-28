#!/usr/bin/env bash
# Dispara o instalador fora do processo do gateway, para sobreviver ao reinício do Hermes.
S=/mnt/c/Users/yurim/ultron-team-20260913/wsl/instalar-ultron-lab.sh
L=/mnt/c/Users/yurim/ultron-team-20260913/wsl/logs
mkdir -p "$L"
rm -f "$L/ultimo-resultado.txt"
if [ "$(ps -p 1 -o comm=)" = systemd ] && command -v systemd-run >/dev/null; then
  systemd-run --collect --unit="ultron-lab-install-$(date +%s)" /bin/bash "$S" > "$L/disparo.txt" 2>&1
  echo "modo=systemd-run" >> "$L/disparo.txt"
else
  setsid nohup /bin/bash "$S" > "$L/disparo.txt" 2>&1 < /dev/null &
  echo "modo=setsid" >> "$L/disparo.txt"
fi
echo "Instalacao do ultron_lab disparada em segundo plano. Log em $L"
