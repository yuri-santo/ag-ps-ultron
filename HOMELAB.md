# Homelab — os serviços que sustentam o Ultron

Tudo roda em **Docker** dentro do WSL do notebook (apelido *Saitama*). O
`ultron_homelab` (plugin `ultron_lab`) consulta o inventário
(`agent/homelab/inventario/`) para dizer o que está no ar. Composição atual
(`docker ps`), agrupada por função:

## Núcleo do agente
| Container | Imagem | Papel |
|---|---|---|
| `ultron-9router` | 9Router | Gateway de modelos → Gemini/Claude/GPT-OSS/OpenRouter (fallback). |
| `hermes-frank-web` / `hermes-frank-worker` | `hermes-frank-investigator` | **Frank**: verificação de fatos das alegações do conselho. |

## Memória e conhecimento
| Container | Imagem | Papel |
|---|---|---|
| `ai-memory` | `akitaonrails/ai-memory` | Memória semântica (MCP). |
| `hermes-rag-api` / `hermes-rag-db` / `hermes-rag-embeddings` | `hermes-rag-*` | RAG: API + banco + embeddings. |
| `flowsint-neo4j-prod` | `neo4j:5` | Grafo da plataforma de investigação. |
| `flowsint-app/api/celery/postgres/redis` | `reconurge/flowsint-*` | OSINT/investigação (app, API, workers, Postgres, Redis). |

## Integrações e fronts
| Container | Imagem | Papel |
|---|---|---|
| `ultron-librechat` + `ultron-librechat-mongodb` | LibreChat + `mongo:8` | Front de chat alternativo. |
| `ultron-nango-server` + `ultron-nango-db` + `ultron-nango-redis` | `nangohq/nango-server`, `postgres:16`, `redis:7` | Conectores OAuth. |
| `homeassistant` | `home-assistant:stable` | Automação residencial / canal de comando. |
| `syncthing` | `syncthing/syncthing` | Sincronização de arquivos entre máquinas. |

## Organização no repositório (`agent/homelab/`)
```
homelab/
  stacks/        arquivos · ia (nvidia/rocm) · midia · monitor (prometheus)
  cenarios/      pc.env.example · servidor.env.example  (PC atual × servidor futuro)
  inventario/    homelab.pc.json · homelab.servidor.json
  scripts/       homelab.sh · backup-restic.sh · upscale.sh · clonar-vendors.sh · Homelab.ps1
```

- **Cenário PC** — o que roda hoje no notebook.
- **Cenário servidor** — plano para migrar para uma máquina dedicada (GPU
  NVIDIA/ROCm para IA e mídia, stack de monitoramento com Prometheus).
- `ultron-lab-monitor` (cron, 10 min) avisa no Telegram se algum serviço cai.

> Segredos dos compose (tokens, senhas) ficam em `.env` **não versionados** —
> o repositório traz só os `*.env.example` com placeholders.
