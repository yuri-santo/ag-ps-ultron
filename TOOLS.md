# Ferramentas, skills e automações

Tudo é registrado pelos plugins do Hermes (`agent/plugins/`) e disponibilizado
ao Ultron ou a um perfil específico. Ferramentas de operação nunca ficam com um
conselheiro; e-mail/conteúdo externo é dado, nunca instrução.

## Ferramentas por plugin

### `harvey_juridico` (perfil Harvey) — jurídico, só leitura
| Ferramenta | O que faz |
|---|---|
| `vademecum_consultar` | Texto de lei do Vade Mecum do Senado (3ª ed., jan/2026) por artigo ou busca; cita a página. Índice local SQLite FTS5 (`agent/juridico/build_index.py`). |
| `planalto_artigo` | Texto **vigente** de um artigo no Planalto (sem redação riscada), com notas "Redação dada pela Lei…". Confirma mudança após jan/2026. |
| `lexml_buscar` | Índice oficial de legislação (LexML SRU). |
| `datajud_processo` | Processo pelo número CNJ na API pública do DataJud/CNJ: classe, assuntos, movimentos. |
| `djen_comunicacoes` | Intimações oficiais do DJEN (Comunica PJe) por processo ou OAB+UF. |
| `prazo_processual` | Vencimento de prazo (CPC 219/220/224), feriados nacionais, carnaval/Corpus Christi forenses, recesso 20/12–20/01. |
| `jurisprudencia_links` | Links oficiais STF/STJ/TST/CNJ + link do Jusbrasil só para conferência humana. |
| `tj_jurisprudencia` | Jurisprudência de 2º grau nos TJs (via juscraper). |
| `frank_verificar` / `frank_relatorio` | Manda alegação decisiva ao Frank e lê o parecer. |

### `ultron_agentes` (Bigode/Buffett/Tron e Mr Robot) — dados reais, só leitura
| Ferramenta | O que faz |
|---|---|
| `bcb_serie` | Série oficial do Banco Central (SGS): Selic, CDI, IPCA (acum. 12m), IGP-M, dólar PTAX. |
| `brasilapi` | Feriados, CNPJ, taxas, bancos (BrasilAPI). |
| `cotacao_b3` | Cotação e dividendos de ação/FII/ETF da B3 (yfinance). |
| `seguranca_relatorio` | Resumo da última auditoria (Lynis/Trivy/Gitleaks). |
| `backup_status` | Status do backup restic. |

### `ultron_lab` (Ultron e perfis de e-mail) — anti-golpe e homelab
| Ferramenta | O que faz |
|---|---|
| `ultron_golpe` | Analisa se uma mensagem/e-mail é golpe/phishing (determinístico, offline). Score 0–100, veredito, achados por camada. |
| `mail_fraud_check` | Mesma análise sobre a mensagem da INBOX por UID (cabeçalhos SPF/DKIM/DMARC). |
| `ultron_homelab` | Diz quais serviços do homelab respondem agora (só leitura). |

### `ultron_team` (perfis de domínio)
| Ferramenta | Perfil | O que faz |
|---|---|---|
| `mail_list/read/search/draft` | Cris, Greg | Caixa de e-mail do perfil, sem marcar como lida; rascunho local. |
| `meeting_agenda`, `meeting_context` | Maquiavel, Dona | Agenda WorkMail e recorte da última reunião. |

## Skills (`agent/skills/`)
`analise-golpe`, `checar-noticia`, `homelab-ops`, `memoria-projetos`, `midia-gpu`
— mais as skills do próprio Hermes (`conselho-sdd`, `frank-investigator`, etc.).

## Reunião → ATA (`agent/meeting/`, `agent/stt/`)
- `render_report.py` — ATA formal em **PDF** (modelo Chamada / Participantes /
  Deliberações / Encaminhamentos / Encerramento, com o logotipo do Ultron).
- `render_docx.py` — a mesma ATA em **Word** editável.
- `parakeet_cli.py` — transcrição CPU com NVIDIA Parakeet (sherpa-onnx).
- `diarizar.py` — separa as vozes ("Participante 1..N") com pyannote+3D-Speaker.
- `benchmark.py` — compara Parakeet × faster-whisper em PT-BR.

## Automações (systemd timers no WSL)
| Timer | Quando | O que faz |
|---|---|---|
| `ultron-lab-monitor` | a cada 10 min | Avisa no Telegram se um serviço do homelab cai ou se chega e-mail novo com cara de golpe. |
| `ultron-seguranca` | domingo 04:30 | Auditoria Lynis/Trivy/Gitleaks. |
| `ultron-backup` | diário 03:40 | Backup restic criptografado em D:. |

## Fontes externas e limites
- **Oficiais** (sem login): BCB/SGS, BrasilAPI, DataJud, DJEN, Planalto, LexML,
  STF/STJ/TST (portais), TJs (juscraper).
- **Yahoo Finance** (yfinance): não oficial, pode ter atraso.
- **Jusbrasil**: os termos de uso proíbem robôs; o Harvey só gera o link para
  conferência humana, nunca raspa.
- Tudo que é "só leitura" não altera nada; ações com efeito externo exigem
  pedido explícito do dono.
