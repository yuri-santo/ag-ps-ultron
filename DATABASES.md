# Bancos de dados — estrutura (o conteúdo fica privado)

O Ultron guarda estado em vários SQLite. **Este documento mostra o *esquema*
(tabelas e para que servem) — nunca os dados.** Bancos pessoais (saúde,
finanças, agenda) contêm informação médica e financeira do dono e **não são
publicados**; o `sync-repo.sh` sobe apenas o `.schema` deles, com zero linhas.

## Pessoais (dados privados — só esquema)

### `saude_yuri.db` — saúde
`medicamentos`, `med_log` (adesão: pendente/lembrado/confirmado por dia),
`suplementos`, `refeicoes`, `treinos`, `logbook` (peso/medidas/análise),
`exames`, `metas_saude`, `regras` (protocolo clínico), `google_fit_daily`
(passos/calorias/sono), `diario_bordo`. Usado por **Jesus**, **Botura**,
**Arnold** e pelos crons de remédio.

### `financas_yuri.db` — finanças
`orcamento_mensal`, `contas_a_pagar`, `cartoes_credito`, `gastos_fatura`,
`creditos_fatura`, `compras_parceladas`, `assinaturas`, `recebimentos`,
`horas_extras*`, `aportes`, `metas`, `caixinhas*`, `carteira_real`/`sugerida`,
`radar_ativos`/`investimentos`, `setups_swinger`, `sinais_operacionais`,
`empresas`, `moradia`, `tickets*` (SAP), `ofertas_buscape`, `insights`,
`decision_runs`, `arvore_*` (árvore de decisão). Usado por **Bigode**,
**Buffett**, **Tron**.

### `agenda_yuri.db` — agenda
`compromissos`, `rotina_fixa`, `datas_importantes`, view `conflitos` (choques de
horário). Usado por **Dona** e **Maquiavel**.

## Memória e conhecimento
| Banco | Para que serve |
|---|---|
| `memory_store.db` | Memória semântica: `facts` (+ FTS5), `entities`, `fact_entities`, `memory_banks` (vetores). |
| `fact_store.db` | Fatos integrais preservados antes de encurtar a memória (Pink/Cérebro). |
| `projects.db` | Projetos/decisões confirmadas. |
| `kanban.db` (+ por-board) | Kanban do time (cards, votos, bloqueios do conselho). |

## Operacionais (automações)
| Banco | Para que serve |
|---|---|
| `promos_*.db`, `buscape*.db`, `deals.db`, `ofertas.db`, `telegram_promos.db` | Radares de promoção (dedup, histórico, "já visto"). |
| `tiktok/tiktok_product_radar.db` | Radar de produtos TikTok. |
| `youtube/money_engine.db`, `paporetocorte.db`, `youtube_cortes.db` | Motor de conteúdo YouTube. |
| `sap_sapeiros.db` | Base de conhecimento SAP (Thor). |
| `orchestration_bus.db` | Barramento de orquestração entre tarefas/agentes. |
| `meeting_copilot/meetings.db` | Reuniões gravadas/transcritas/atas. |
| `homeassistant/home-assistant_v2.db` | Estado do Home Assistant. |

## Sistema (Hermes — não versionado)
`state.db`, `sessions.db`, `shared-state.db`, `history.db`, `chat_history.db`,
`verification_evidence.db`, `cron/*.db` (jobs, execuções, entregas, notepad),
e os `state.db`/`cron_executions.db`/`verification_evidence.db` **por perfil**.

## Backup
`backups_local/` guarda cópias com prefixo `root_...`; o backup diário é
**restic** criptografado (ver [AUTOMACOES.md](AUTOMACOES.md)), com snapshot
consistente dos SQLite.

> Regra de ouro: **esquema e código sobem; dado pessoal não.** O `sync-repo.sh`
> dumpa o `.schema` (estrutura) e a **contagem** de linhas — nunca as linhas.
