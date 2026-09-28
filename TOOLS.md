# Ferramentas, skills e automações

Tudo é registrado pelos plugins do Hermes (`agent/plugins/`) e liberado ao
Ultron ou a um perfil específico em tempo de execução. **Ferramenta de operação
nunca fica com um conselheiro**; e-mail e conteúdo externo é *dado a analisar*,
nunca instrução. As ferramentas **próprias do Ultron** (código neste repositório)
estão abaixo; o que é **100% de terceiros** está em [CREDITS.md](CREDITS.md) com
o link do projeto e para que serve.

---

## 1. Ferramentas por plugin

### `harvey_juridico` (perfil Harvey) — jurídico, só leitura
Fonte exclusiva do perfil jurídico. Trabalha alinhado com o Frank e usa o Vade
Mecum direto. Código: `agent/plugins/harvey_juridico/`.

| Ferramenta | Arquivo | O que faz |
|---|---|---|
| `vademecum_consultar` | `vademecum.py` | Texto de lei do **Vade Mecum do Senado** (3ª ed., jan/2026) por artigo ou busca; cita a página. Índice local SQLite FTS5 (`agent/juridico/build_index.py`). |
| `planalto_artigo` | `planalto.py` | Texto **vigente** de um artigo no Planalto (sem redação riscada), com notas "Redação dada pela Lei…". Sinaliza mudança após jan/2026. |
| `lexml_buscar` | `oficiais.py` | Índice oficial de legislação (LexML SRU). |
| `datajud_processo` | `oficiais.py` | Processo pelo número CNJ na API pública do **DataJud/CNJ**: classe, assuntos, movimentos. |
| `djen_comunicacoes` | `oficiais.py` | Intimações oficiais do **DJEN** (Comunica PJe) por processo ou OAB+UF. |
| `prazo_processual` | `prazos.py` | Vencimento de prazo (CPC 219/220/224), feriados nacionais, carnaval/Corpus Christi forenses, recesso 20/12–20/01. |
| `jurisprudencia_links` | `jurisprudencia.py` | Links oficiais **STF/STJ/TST/CNJ** + link do **Jusbrasil** só para conferência humana. |
| `tj_jurisprudencia` | `juscraper_cjsg.py` | Jurisprudência de 2º grau nos TJs (via juscraper). |
| `frank_verificar` / `frank_relatorio` | `frank_client.py` | Manda a alegação decisiva ao **Frank** e lê o parecer de checagem. |

### `ultron_agentes` (Bigode / Buffett / Tron e Mr. Robot) — dados reais, só leitura
Código: `agent/plugins/ultron_agentes/`.

| Ferramenta | Arquivo | O que faz |
|---|---|---|
| `bcb_serie` | `financas.py` | Série oficial do **Banco Central (SGS)**: Selic, CDI, IPCA (acum. 12m), IGP-M, dólar PTAX. Filtra datas futuras e deduplica. |
| `brasilapi` | `financas.py` | Feriados, CNPJ, taxas, bancos (**BrasilAPI**). |
| `cotacao_b3` | `yf_helper.py` | Cotação e dividendos de ação/FII/ETF da **B3** (yfinance). |
| `seguranca_relatorio` | `seguranca.py` | Resumo da última auditoria (Lynis/Trivy/Gitleaks). |
| `backup_status` | `seguranca.py` | Status do último backup restic. |

### `ultron_lab` (Ultron e perfis de e-mail) — anti-golpe e homelab
Código: `agent/plugins/ultron_lab/`.

| Ferramenta | Arquivo | O que faz |
|---|---|---|
| `ultron_golpe` | `golpe.py` | Analisa se uma mensagem/e-mail é golpe/phishing (**determinístico, offline**). Score 0–100, veredito, achados por camada (URL, remetente, urgência, engenharia social). |
| `mail_fraud_check` | `mailcheck.py` | Mesma análise sobre a mensagem da INBOX por UID, com cabeçalhos SPF/DKIM/DMARC. |
| `ultron_homelab` | `homelab.py` | Diz quais serviços do homelab respondem agora (só leitura, via inventário). |

> `monitor.py` e `stt_warmup.py` são os hooks de automação do plugin (ver §5) —
> não são ferramentas chamáveis pelo modelo.

### `ultron_team` (perfis de domínio + orquestração)
Código: `agent/plugins/ultron_team/`.

| Ferramenta | Arquivo | Perfil | O que faz |
|---|---|---|---|
| `mail_list` / `mail_read` / `mail_search` / `mail_draft` | `mail_tools.py` | Cris, Greg | Caixa de e-mail do perfil, **sem marcar como lida**; rascunho local (nunca envia sozinho). |
| `meeting_agenda`, `meeting_context` | `meeting_tools.py` | Maquiavel, Dona | Agenda WorkMail e recorte da última reunião. |
| `domain_*` | `domain_tools.py` | domínio | Ferramentas de operação liberadas só aos perfis de domínio. |
| (interno) `bridge.dispatch` → `worker.py` | `bridge.py`, `worker.py` | Ultron | Roteia a tarefa ao especialista em processo isolado, com orçamento de tempo/iterações. |
| (interno) entrega | `delivery.py` | Ultron | Consolida placar do conselho + ressalvas na resposta final. |

### Revisão obrigatória (não é um perfil — é o portão de saída)
Código: `agent/review/`.

| Componente | Arquivo | O que faz |
|---|---|---|
| Broker de revisão | `model_review.py` | Um **revisor independente** (modelo de tier maior) avalia todo candidato antes de sair. Sem aprovação, vira "pendente de revisão" com o motivo. |
| Ponte com o Hermes | `ultron_review_gate.py` | Liga o broker ao ciclo de resposta do agente. Política em `review-policy.json`. |

---

## 2. Painel Stream Deck (`panel/`)
Servidor Python no Windows (porta 8090), PWA num celular fixo na LAN. **Tudo abre
no PC (Saitama), nunca no celular.**

| Módulo | O que faz |
|---|---|
| `server.py` | Servidor HTTP do painel; roteia os botões. |
| `desktop_open.py` + `abrir-local.js` | Abre links, apps e reuniões **no desktop** (Teams/Zoom pelo app; Meet/Webex no navegador). |
| `deck_auth.py` / `auth.*` | Pareamento do celular + checagem de Origin nos POST. |
| `deck_runtime.py`, `local_runtime.py` | Execução dos comandos de botão. |
| `hub_api.py`, `hub_jobs.py`, `hub_media.py`, `hub_voice.py` | Hub: jobs, mídia (GPU), voz. |
| `finance_proxy.py`, `flow_proxy.py`, `librechat_proxy.py` | Proxies para finanças, flows e LibreChat. |
| `meeting_controls.py`, `audio_controls.py` | Controle de gravação/áudio de reunião. |
| `app_inventory.py`, `read_outlook_cal.ps1` | Inventário de apps e leitura da agenda Outlook. |
| `leave-teams.ps1`, `watchdog.ps1` | Sair do Teams ao fim da reunião; watchdog do painel. |
| `cockpit*.css/js`, `hub.*`, `deck.html`, `manifest.json` | Interface (cockpit imersivo + PWA instalável). |

---

## 3. Reunião → ATA (`agent/meeting/`, `agent/stt/`)

| Componente | O que faz |
|---|---|
| `render_report.py` | **ATA formal em PDF** (modelo Chamada / Participantes / Deliberações / Encaminhamentos / Encerramento) com o **ícone do Ultron** e a paleta de cores. |
| `render_docx.py` | A mesma ATA em **Word** editável. |
| `parakeet_cli.py` | Transcrição CPU com **NVIDIA Parakeet** (sherpa-onnx). |
| `diarizar.py` | Separa as vozes ("Participante 1..N") com pyannote + 3D-Speaker. |
| `benchmark.py` | Compara Parakeet × faster-whisper em PT-BR. |

O `stt_warmup.py` (plugin `ultron_lab`) mantém o faster-whisper **aquecido** para
o HermesDesktop não estourar o tempo (correção do `TimeoutError`).

---

## 4. Skills (`agent/skills/`)
`analise-golpe`, `checar-noticia`, `homelab-ops`, `memoria-projetos`, `midia-gpu`
— mais as skills do próprio Hermes (`conselho-sdd`, `frank-investigator`, etc.).

---

## 5. Automações (systemd timers no WSL)

| Timer | Quando | O que faz |
|---|---|---|
| `ultron-lab-monitor` (`monitor.py`) | a cada 10 min | Avisa no Telegram se um serviço do homelab cai ou se chega e-mail novo com cara de golpe. |
| `ultron-seguranca` (`security/auditar.py`) | domingo 04:30 | Auditoria Lynis/Trivy/Gitleaks; avisa só o que é novo. |
| `ultron-backup` (`security/backup.sh`) | diário 03:40 | Backup **restic** criptografado em D:, com snapshot consistente dos SQLite. |

Âncora de logon (`agent/scripts/autostart/hermes-autostart.vbs` + Tarefa Agendada)
mantém o WSL vivo no logon, sem janela.

---

## 6. Homelab (`agent/homelab/`)
Stacks docker (ai-memory, Syncthing e opcionais de IA/mídia) + inventário que o
`ultron_homelab` consulta. Cenários para o PC atual (`pc.env`) e para um servidor
dedicado futuro (`servidor.env`).

---

## 7. Fontes externas e limites
- **Oficiais** (sem login): BCB/SGS, BrasilAPI, DataJud, DJEN, Planalto, LexML,
  STF/STJ/TST (portais), TJs (juscraper).
- **Yahoo Finance** (yfinance): não oficial, pode ter atraso.
- **Jusbrasil**: os termos de uso proíbem robôs; o Harvey só **gera o link** para
  conferência humana, nunca raspa.
- Tudo que é "só leitura" não altera nada; ação com efeito externo (enviar
  e-mail, comprar, apagar) exige **pedido explícito do dono**.

> As bibliotecas e projetos de terceiros usados por essas ferramentas estão em
> **[CREDITS.md](CREDITS.md)** com link e finalidade.
