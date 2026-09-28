# Integrações — tudo com que o Ultron conversa

Todo o código de interface vive em `/root/tools/` e nos plugins. **Credenciais,
cookies e tokens ficam de fora** (arquivos `*token*`, `*cookie*`, `client_secret*`,
`.env`); aqui estão o **canal**, **para que serve** e **o código** que fala com
cada sistema.

## Mensageria e voz (como você fala com o agente)
| Canal | Interface | Uso |
|---|---|---|
| **Telegram** | gateway do Hermes | Canal principal: você fala e ele responde (texto e voz/TTS). |
| **HermesDesktop** | app de voz no PC | Fala por áudio; transcrição local (faster-whisper aquecido). |
| **Stream Deck** | `panel/` (PWA na LAN) | Botões que abrem tudo **no PC** (ver [DASHBOARD.md](DASHBOARD.md)). |
| **E-mail** | gateway | Recebe/triagem por e-mail. |

## Produtividade e trabalho
| Sistema | Código | Uso |
|---|---|---|
| **Microsoft 365 / WorkMail** | `ms_graph.py`, `ms_auth.py`, `workmail_cal.py`, `cal_*.py`, `sync_agenda_unificada.py` | Agenda corporativa + e-mail Easysapers (perfis **Dona**, **Cris**). |
| **Google Calendar** | `cal_daily2.py`, `agenda_add.py` | Agenda pessoal unificada com a corporativa. |
| **Gmail pessoal** | gateway de e-mail | Compras, entregas, segurança de contas (perfil **Greg**). |
| **Easysapers / SAP** | `fetch_easysapers.py`, `scrape_easysapers.py`, `sync_easysapers_tickets.py`, `scrape_sapeiros.py`, `enrich_sap_knowledge.py` | Chamados SAP, base de conhecimento (perfis **Cris**, **Thor**). |

## Saúde
| Sistema | Código | Uso |
|---|---|---|
| **Google Fit** | `google_fit/` (OAuth, `sync_health_to_db.py`, `fetch_health_data.py`) | Passos, calorias, sono, FC → `saude_yuri.db`. |
| **Google Drive** | `google_fit/*drive*`, `drive_backup.py` | Armazenamento/base de conhecimento de saúde e backup. |
| **Relatórios clínicos** | `generate_health_summary_pdf.py`, `generate_pdf_prontuario.py`, `insert_vacinas*.py`, `mk_health_agenda_db.py` | PDF de prontuário/vacinas (dados privados). |

## Conhecimento e memória
| Sistema | Código | Uso |
|---|---|---|
| **NotebookLM** | `nb_login.py`, `nb_login_auto.py`, `clean_notebooks.py`, `curate_leiloes_notebook.py`, skills `notebooklm*`, `notebooklm_keepalive.sh`, `local_fs.py` (ponte de arquivos Windows↔WSL) | Curadoria de fontes e pesquisa; a sessão é mantida viva por cron (keepalive + sync de cookies do Windows). |
| **ai-memory** | container (MCP) + `memoria_curadoria_v1.py` | Memória semântica de projetos/decisões (perfil **Pink**). |
| **Graphify / knowledge graph** | `setup_memory_graph.py`, `distribute_knowledge_to_agents.py` | Mapa de contexto (perfil **Cérebro**). |
| **Obsidian** | `mcpvault` (MCP) | Vault de notas por MCP, sem abrir o Obsidian. |
| **hermes-rag** | containers `hermes-rag-*` | RAG com banco + embeddings. |
| **flowsint** | containers `flowsint-*` (neo4j, api, app, celery, postgres, redis) | Plataforma de investigação/OSINT. |
| **Frank (investigador)** | containers `hermes-frank-*` | Verificação de fatos das alegações decisivas do conselho. |

## Conteúdo, mídia e canais (perfil Money)
| Sistema | Código | Uso |
|---|---|---|
| **TikTok** | `tiktok/` (radar de produto, `affiliate_*`, `content_studio`, `tiktok_case_publisher.py`, render/comentário) | Pipeline de afiliados de ponta a ponta. |
| **YouTube** | `youtube/` (`autonomous_money_engine.py`, `auto_corte_publicador_loop.py`, downloads, OAuth) | Canal de cortes @paporetocorte. |
| **Instagram** | `instagram/` (`follow_queue.py`, `monitor_feed_stories.py`) | Monitoramento e crescimento regional. |
| **Geração de vídeo/imagem** | plugins `video_gen` (Google Veo), `image_gen` (Google Gemini), `kling/` | Cria vídeo/imagem para conteúdo. |
| **Voz/TTS** | `video_voice.py`, TTS do gateway | Narração e áudio das mensagens. |

## Promoções e radares
`monitor_buscape*.py`, `monitor_promos_*.py`, `monitor_viagens_rss.py`,
`monitor_energia_especifico.py`, `monitor_telegram_promo_channels.py`,
`monitor_influenciadores_telegram.py`, `imoveis/monitor_imoveis_regional.py` —
alimentam os bancos `promos_*.db` e passam pelo conselho antes de virar alerta.

## Finanças e mercado
`radar_smallcaps.py`, `swingtrader_checklist.md`, `trader_quant_setups.md`,
`export_controle_pagamentos.py`, `fin-dashboard/` (Perseu) — além das fontes
oficiais (BCB, BrasilAPI, B3/yfinance) descritas em [CREDITS.md](CREDITS.md).

## Casa e conectores
| Sistema | Como | Uso |
|---|---|---|
| **Home Assistant** | container `homeassistant` | Automação residencial / canal de comando. |
| **Nango** | containers `ultron-nango-*` | Conectores OAuth para integrações. |
| **LibreChat** | containers `ultron-librechat*` | Front de chat alternativo. |
| **Syncthing** | container `syncthing` | Sincronização de arquivos entre máquinas. |

## Modelos (9Router)
`ultron-9router` roteia todo modelo para **Gemini / Claude / GPT-OSS / OpenRouter**
com fallback. O Hermes aponta o "custom endpoint" para ele; perfis podem ter
modelo próprio (`model.*` no `config.yaml`).

> Repositórios oficiais das libs/serviços de terceiros: [CREDITS.md](CREDITS.md).
