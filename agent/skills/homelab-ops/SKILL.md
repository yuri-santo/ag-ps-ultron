---
name: homelab-ops
description: Opera o homelab (status, subir stack, backup) com segurança
version: 1.0.0
metadata:
  hermes:
    category: ultron-lab
    tags: [homelab, docker, wsl, backup, infraestrutura]
    requires_toolsets: [ultron_lab]
---

# Operar o homelab

Layout e regras tirados da migração do home server do Akita (49 containers, openSUSE MicroOS) e
adaptados ao ambiente de Yuri: Docker dentro do WSL Debian, stacks em `/opt/agent-stacks/homelab`,
dados em `/opt/agent-stacks/homelab-data`. O cenário ativo está em `/opt/agent-stacks/homelab/.env`
(`CENARIO=pc` hoje; `servidor` quando existir a máquina dedicada).

## Perguntas de status ("como está o homelab?", "o ai-memory caiu?")

1. `ultron_homelab` (sem filtro, ou `grupo`/`nome`). Grupos: hermes, ia, arquivos, casa, integracoes, apps.
2. Responda: quantos no ar, quais fora, **críticos primeiro**, latência só se estiver anormal.
3. "ok" = respondeu HTTP esperado. Não é prova de que o serviço funciona por dentro; diga isso se Yuri
   perguntar algo funcional.

## Mudanças (subir, parar, atualizar, editar compose)

Só com pedido explícito de Yuri na conversa. Antes de qualquer mudança:

1. Diga o comando exato que vai rodar e o efeito (qual stack, se derruba algo em uso).
2. Backup quando houver dado em jogo: `scripts/backup-restic.sh backup` (ou pelo menos cópia do diretório
   do serviço em `homelab-data/<stack>/<servico>`).
3. Rode pelo script, nunca `docker compose` solto em outro diretório:
   `bash /opt/agent-stacks/homelab/scripts/homelab.sh up <stack>` (ou `ps`, `logs`, `pull`, `down`, `check`).
4. Confirme com `ultron_homelab` depois e relate o resultado real.

## Regras que valem sempre

- Um compose por stack, dados em `homelab-data/<stack>/<serviço>`; nada de volume espalhado pela home.
- Portas publicadas só em `BIND` (127.0.0.1 no PC). Nunca abrir porta no roteador: acesso externo por
  Cloudflare Tunnel com Cloudflare Access, ou Tailscale.
- Portas reservadas do Yuri que o homelab não usa: 8090, 8123, 3080, 1234, 20128, 5001, 9119, 9500.
- Serviço que monta o socket do Docker equivale a root: nunca exponha sem autenticação.
- Alertas de serviço fora vêm do timer `ultron-lab-monitor.timer` (sem LLM). Para ver o último estado:
  `/root/.hermes/ultron_lab/monitor_estado.json`; para rodar na hora: `python3 -m ultron_lab.monitor homelab --dry-run`
  com `PYTHONPATH=/root/.hermes/plugins`.
- Nada de `docker system prune -a`, `rm -rf` em `homelab-data` ou `down -v` sem Yuri confirmar
  o comando exato. Volumes apagados não voltam.
- Modelos (Ollama, ComfyUI, FramePack) não entram no backup: rebaixáveis. Configs e bancos entram.
- SELinux (servidor com MicroOS/Fedora): prefira `security_opt: [label:disable]` a `:Z` em volumes NFS.
- Agentes de código rodando no servidor: use `ai-jail` (sandbox do Akita; no Windows só via WSL2).

## Migração PC → servidor

1. `scripts/backup-restic.sh backup` no PC.
2. No servidor: clonar o repo em `/opt/agent-stacks/homelab`, `cp cenarios/servidor.env.example .env`,
   preencher segredos, `scripts/clonar-vendors.sh`.
3. `restic restore latest --target /` e `scripts/homelab.sh up all`.
4. Trocar o inventário do Ultron para `homelab.servidor.json` (IP/Tailscale do servidor) e checar com
   `ultron_homelab`.
