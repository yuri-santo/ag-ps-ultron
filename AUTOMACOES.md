# Automações — o que roda sozinho

O Ultron se opera sozinho por **cron jobs do Hermes** (agendador do próprio
agente, na aba **Cron** do dashboard) e por **systemd timers**. Cada job roda
como um turno do agente (com a revisão obrigatória) ou como script puro. Abaixo
está o catálogo por tema. Horários em **BRT**. Ids de chat/telegram e valores
pessoais foram omitidos.

## Rotina diária (entrega no Telegram / voz)
| Job | Quando | O que faz |
|---|---|---|
| `pink-curadoria-memoria` | 08:40 | A **Pink** consolida a memória do dia (antecede toda a esteira da manhã). |
| `resumo-diario-7h` | 09:00 | Resumo matinal (dados coletados por pré-script). |
| `radar-datas-especiais` | 09:00 / 20:45 | Avisa vésperas e datas importantes. |
| `Yuri Evolution Watchdog` | seg 09:00 | Atualiza o Logbook semanal (`updater.py`). |
| `agenda-secretaria` | 09:15 | A **Dona** lê a agenda do dia (WorkMail/Calendar) e avisa. |
| `financas-guardiao` | 09:30 | O **Bigode** revisa contas/orçamento do dia. |
| `time-sync-diario` | 19:00 | Sincroniza o **time** (finanças + saúde + agenda). |
| `jesus-checkin-noite` | 20:00 | Check-in de saúde, treino e bem-estar (**Jesus**). |

## Saúde — lembretes de remédio (cobram até confirmar)
Consultam `saude_yuri.db` (tabela `med_log`) e insistem se ainda estiver
pendente. Ex.: dose da manhã e sua cobrança 30 min depois, doses do café, da
tarde e da noite. **Regras clínicas do protocolo ficam privadas** (ver
[DATABASES.md](DATABASES.md)).

## Inglês (estudo)
`resumo`/`lembrete-ingles` (ter/qui/sáb), `treino-diario-ingles-tarde` (15:00,
Daily English Challenge), `english-task-monitor` (cobra tarefa não respondida a
cada 10 min), `check-aula` (sexta).

## Monitores (a cada 10 min ou em janelas)
| Job | O que observa |
|---|---|
| `monitor-emails-10m` | E-mail novo → triagem + alerta de golpe (via `ultron_lab`). |
| `monitor-promos-*` / `promos-triagem-conselho` | Buscapé, ofertas confiáveis, canais Telegram → conselho decide o que vale. |
| `monitor-promos-viagens` / `monitor_viagens_rss` | Promoções de viagem (RSS). |
| `monitor-instagram-oportunidades` | Feed/stories (perfil regional). |
| `monitor-imoveis-baixa-renda` | Imóveis por região (`imoveis/`). |
| `radar-smallcaps-3x` / `radar-swing-diario` | B3: small/mid caps e swing (Buffett + Bigode + Tanos). |
| `sync-google-fit` | Passos/calorias/sono → `saude_yuri.db`. |

## Conteúdo e canais (perfil Money)
| Job | O que faz |
|---|---|
| `money-publicador-shorts-08h/12h/19h` | Publica shorts no canal de conteúdo. |
| `youtube-cortes-autopilot` | Motor de cortes de vídeo (YouTube). |
| `tiktok-mercenario-5x` / `tiktok-seller-oportunidades` | Pipeline de afiliados TikTok: radar de produto, roteiro, render, publicação, comentário. |
| `monitor-promos-novos` | Novas ofertas oficiais para conteúdo. |

## Trabalho (SAP / uso profissional)
Jobs de sincronização de chamados SAP às 10h e 20h (perfis **Cris**/**Thor**).

## Infra, backup e conhecimento
| Job | Quando | O que faz |
|---|---|---|
| `ultron-backup` | sáb 10:30 | Backup **restic** criptografado para o disco D: (pós-aula de inglês). |
| `backup-vps-drive` | sáb 10:45 | `auto_archive_vps.py` — compacta 66 bancos SQLite e sobe no Google Drive. |
| `ultron-seguranca` | sáb 11:00 | Auditoria Lynis/Trivy/Gitleaks (máquina ligada e livre). |
| `ultron-lab-monitor` | 10 min | Sentinela contínuo: avisa se um serviço do homelab cai. |
| `NotebookLM Auth Keepalive` / `Cookie Sync` | 30 min / 1 h | Mantém a sessão do NotebookLM viva no Google (rotatividade contínua de cookie). |

## Lembretes pontuais (Once)
Consultas médicas, retiradas de medicamento, vésperas — criados sob demanda como
job único e se auto-desativam depois de disparar.

> A árvore completa de scripts de automação está em `/root/tools/` (ver
> [INTEGRACOES.md](INTEGRACOES.md) e [TOOLS.md](TOOLS.md)). O
> `agent/scripts/sync-repo.sh` varre essas fontes e sobe o código sanitizado.
