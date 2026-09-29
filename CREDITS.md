# Créditos — projetos de terceiros usados no Ultron

O que está em [TOOLS.md](TOOLS.md) é código **próprio** deste repositório. Este
arquivo lista o que é **de terceiros**: para cada projeto, o link oficial e
**para que o Ultron usa**. A exceção distribuída é o subconjunto adaptado de
`marketingskills`, com o aviso MIT preservado em `agent/marketing/marketingskills/LICENSE`.

## Núcleo do agente

| Projeto | Link | Para que o Ultron usa |
|---|---|---|
| **Hermes Agent** (NousResearch) | https://github.com/NousResearch/Hermes | O agente em si: CLI, gateway de mensageria (Telegram/e-mail), segredos, sessões, skills. Tudo neste repo é plugin/extensão dele. |
| **9Router** | (gateway local, OpenAI-compatible) | Roteia o modelo para Gemini/Claude/GPT-OSS/OpenRouter com fallback. O Hermes aponta o "custom endpoint" para ele. |

## Reunião, voz e transcrição

| Projeto | Link | Para que o Ultron usa |
|---|---|---|
| **HermesDesktop** | https://github.com/fathah/hermes-desktop | App de voz no PC — fala com o agente por áudio. |
| **faster-whisper** (SYSTRAN) | https://github.com/SYSTRAN/faster-whisper | Transcrição PT-BR local, mantida "aquecida" para o HermesDesktop não estourar o tempo. |
| **sherpa-onnx** (k2-fsa) | https://github.com/k2-fsa/sherpa-onnx | Runtime CPU da transcrição/diarização (Parakeet + speaker embeddings). |
| **NVIDIA Parakeet TDT 0.6B v3** | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 | Modelo de transcrição alternativo (comparado ao whisper no benchmark). |
| **pyannote.audio** | https://github.com/pyannote/pyannote-audio | Diarização — separa "Participante 1..N" na ATA. |
| **python-docx** | https://github.com/python-openxml/python-docx | Gera a ATA em Word. |
| **ReportLab** | https://www.reportlab.com/opensource/ | Gera a ATA formal em PDF. |
| **Pillow / cairosvg** | https://python-pillow.org/ · https://cairosvg.org/ | Logo/ícone do Ultron na ATA e render do banner. |

## Jurídico (perfil Harvey)

| Projeto / fonte | Link | Para que o Ultron usa |
|---|---|---|
| **juscraper** (jtrecenti) | https://github.com/jtrecenti/juscraper | Coleta de jurisprudência de 2º grau nos TJs. |
| **Vade Mecum** (Senado Federal) | https://www2.senado.leg.br/bdsf/handle/id/496306 | PDF oficial indexado localmente (fonte de lei do Harvey). |
| **Portal da Legislação — Planalto** | https://www.planalto.gov.br/ | Texto vigente dos artigos. |
| **LexML** | https://www.lexml.gov.br/ | Índice oficial de legislação (SRU). |
| **DataJud / CNJ** | https://www.cnj.jus.br/sistemas/datajud/ | Consulta processual pública por número CNJ. |
| **DJEN / Comunica PJe** | https://comunica.pje.jus.br/ | Intimações oficiais. |
| **STF / STJ / TST** | https://portal.stf.jus.br/ · https://www.stj.jus.br/ · https://www.tst.jus.br/ | Jurisprudência oficial (links). |
| **Jusbrasil** | https://www.jusbrasil.com.br/ | Só link para conferência humana (os termos proíbem robôs — nunca raspa). |

## Finanças (Bigode / Buffett / Tron)

| Projeto / fonte | Link | Para que o Ultron usa |
|---|---|---|
| **yfinance** (ranaroussi) | https://github.com/ranaroussi/yfinance | Cotação e dividendos de ações/FIIs/ETFs da B3. |
| **Banco Central — SGS** | https://dadosabertos.bcb.gov.br/ | Selic, CDI, IPCA, IGP-M, dólar PTAX (oficial). |
| **BrasilAPI** | https://github.com/BrasilAPI/BrasilAPI | Feriados, CNPJ, taxas, bancos. |

## Marketing (Money)

| Projeto | Link | Para que o Ultron usa |
|---|---|---|
| **marketingskills** (Corey Haines) | https://github.com/coreyhaines31/marketingskills | Dez skills de método para posicionamento, pesquisa, copy, conteúdo, SEO, redes sociais, anúncios, analytics e testes A/B. Snapshot e licença MIT em `agent/marketing/`. |

## Segurança e backup (Mr. Robot)

| Projeto | Link | Para que o Ultron usa |
|---|---|---|
| **restic** | https://github.com/restic/restic | Backup diário criptografado em D:. |
| **Lynis** (CISOfy) | https://github.com/CISOfy/lynis | Auditoria de hardening semanal. |
| **Trivy** (Aqua Security) | https://github.com/aquasecurity/trivy | Varredura de vulnerabilidades. |
| **gitleaks** | https://github.com/gitleaks/gitleaks | Procura segredos vazados em arquivo. |

## Memória e conhecimento

| Projeto | Link | Para que o Ultron usa |
|---|---|---|
| **ai-memory** | https://github.com/akitaonrails/ai-memory | Memória semântica de projetos/decisões (docker, MCP). |
| **mcpvault** | https://github.com/bitbonsai/mcpvault | Expõe o vault do Obsidian por MCP, sem abrir o Obsidian. |

## Homelab e integrações (opcionais / planejados)

| Projeto | Link | Para que serve no cenário do Ultron |
|---|---|---|
| **Syncthing** | https://github.com/syncthing/syncthing | Sincronização de arquivos entre máquinas. |
| **Home Assistant** | https://github.com/home-assistant/core | Automação residencial (canal de comando do agente). |
| **LibreChat** | https://github.com/danny-avila/LibreChat | Front alternativo de chat (proxy no painel). |
| **MoneyPrinterTurbo** | https://github.com/harry0703/MoneyPrinterTurbo | Perfil Money: geração de vídeo/conteúdo. |
| **Playwright** (Microsoft) | https://github.com/microsoft/playwright | Automação de navegador quando uma fonte exige. |
| **Firecrawl** (Mendable) | https://github.com/mendableai/firecrawl | Coleta estruturada de páginas. |
| **Nango** | https://github.com/NangoHQ/nango | Conectores OAuth para integrações futuras. |

> **Planejados** (ainda não ativos): tabela **TACO** (nutrição, perfil Botura) e
> **Garmin** (treino, perfil Arnold — depende de login do dono).

---

Se algum projeto acima mudar de repositório ou você quiser trocar a fonte, o
`agent/scripts/sync-repo.sh` reconstrói e sobe o retrato atualizado com um comando.
