# Ultron Lab

Plugin Hermes `ultron_lab` + skills + homelab, adaptados dos repositórios do Fabio Akita
(akitaonrails) em 27/09/2026. Não altera o código do `ultron_team`; só o reutiliza.

## O que entra

| Peça | Onde roda | Origem no Akita | O que faz |
| --- | --- | --- | --- |
| `ultron_golpe` | Ultron (perfil padrão) | frank_fbi, camadas 1 e 3 + política de escalonamento | Score 0-100 e veredito para mensagem/e-mail colado; padrões BR (Pix, boleto, Receita, número novo, tarefas pagas, domínio sósia, injeção contra IA) |
| `mail_fraud_check` | perfis `gmail` e `easysapers` | frank_fbi | Mesma análise sobre a mensagem da INBOX por UID, com cabeçalhos originais (SPF/DKIM/DMARC). `BODY.PEEK`, INBOX readonly |
| `ultron_homelab` | Ultron | home server do Akita (Uptime/Grafana) | Status HTTP dos serviços do inventário `/root/.hermes/ultron_lab/homelab.json` |
| skill `analise-golpe` | Ultron | frank_fbi | Fluxo de resposta e o que fazer se já caiu |
| skill `checar-noticia` | Ultron | frank_investigator + my-skills/fact-check | Fonte primária > volume, veto da primária, citação circular |
| skill `homelab-ops` | Ultron | post "Migrando meu Home Server" | Regras de operação, backup e migração PC → servidor |
| skill `midia-gpu` | Ultron | Real-ESRGAN, Video2K, FramePack, ComfyUI, easy-ffmpeg, easy-subtitle | Qual ferramenta usar e como |
| skill `memoria-projetos` | Ultron | ai-memory | Recuperar contexto de projeto e passar o bastão entre agentes |
| `homelab/` | WSL Debian (pc) ou servidor | home server + FrankMD, frank_type, ai-memory | 7 stacks Docker Compose, dois cenários, GPU por overlay |

## Instalar no Hermes local (WSL Debian, root)

```bash
cd /mnt/c/Users/yurim/ultron-team-20260913
PY=/caminho/do/python/do/hermes          # o mesmo que roda o gateway (precisa de PyYAML)
$PY -m unittest discover -s tests -q     # suíte inteira (ultron_team + ultron_lab)
$PY deploy_lab.py stage --dry-run        # mostra o que vai copiar
$PY deploy_lab.py stage                  # plugin, cópias nos perfis, skills, inventário
$PY deploy_lab.py activate --dry-run
$PY deploy_lab.py activate               # habilita no config.yaml principal e nos perfis gmail/easysapers
```

Depois reinicie o gateway pelo procedimento habitual (supervisor/autostart do WSL).
`stage` recusa sobrescrever diretório que não tenha o marcador `.ultron-lab-managed` e exige os perfis
do `ultron_team` já instalados. Os demais perfis (bigode, thor, hercules, money...) têm hash conferido
antes e depois; qualquer diferença aborta.

## Testar na conversa

- "É golpe? *Oi mãe, mudei de número, me faz um Pix de 800 agora*" → `ultron_golpe`, veredito Golpe.
- "Confere se o último e-mail da Easysapers sobre boleto é golpe" → Ultron → especialista easysapers →
  `mail_list` + `mail_fraud_check`.
- "Como está o homelab?" → `ultron_homelab` (antes de subir os stacks, tudo aparece fora; é esperado).

Atenção: `deploy.py stage` do `ultron_team` regrava o `config.yaml` dos perfis gmail/easysapers e tira o `ultron_lab` deles. Se reinstalar o `ultron_team`, rode `deploy_lab.py activate` de novo.

## Uso automático (27/09/2026)

- **Monitor sem LLM** (`ultron_lab/monitor.py`), rodado pelo `ultron-lab-monitor.timer` do systemd a cada 10 min:
  avisa no Telegram quando um serviço do inventário cai (2 checagens seguidas) ou volta, e quando chega
  e-mail novo no Gmail ou na Easysapers com score de golpe >= 51. Silencioso quando está tudo bem.
  Estado em `/root/.hermes/ultron_lab/monitor_estado.json`. Rodar na mão:
  `PYTHONPATH=/root/.hermes/plugins python3 -m ultron_lab.monitor todos --dry-run`.
- **ai-memory**: o Ultron consulta sozinho em assunto de projeto e registra decisões duráveis confirmadas.
- **Perfis de e-mail locais**: no Hermes local os especialistas se chamam `greg` (Gmail) e `cris` (Easysapers);
  o ultron_lab resolve o perfil pelo tipo de conta, então `mail_fraud_check gmail|easysapers <uid>` funciona no Ultron.
- **Removidos do homelab**: Uptime Kuma, Portainer, Vaultwarden, FrankMD e Frank Type. Dados movidos para
  `/opt/agent-stacks/homelab-data/_removidos-20260927T224227/` (não apagados).

## Recuperação

Cada execução grava `/root/.hermes/backups/ultron-lab-<timestamp>/manifest.json` com a lista do que mudou
e as cópias originais. Para desfazer a ativação: restaurar `config.yaml` e
`profiles/{gmail,easysapers}/config.yaml` desse backup e reiniciar o gateway. Para remover de vez: apagar
`plugins/ultron_lab`, `profiles/{gmail,easysapers}/plugins/ultron_lab` e `skills/ultron-lab`.

## Limites conhecidos

- A análise de golpe é determinística e offline: sem WHOIS, blacklists, VirusTotal ou URLhaus (camadas
  2, 4 e 5 do Frank FBI) e sem consenso de 3 LLMs (camada 6). O modelo do Ultron dá a leitura dele à parte.
- `ultron_homelab` mede resposta HTTP, não saúde funcional.
- Nenhum teste aqui prova entrega real no Telegram nem o comportamento do Hermes instalado; valide na
  conversa depois do `activate`.


## Ajustes de 28/09/2026

- **Revisão** (`/root/ultron-local/model_review.py`, `review-policy.json`, `agent/ultron_review_gate.py`): o aviso
  `reviewer_unavailable_or_invalid` vinha de o único revisor elegível (ag/claude-opus-4-6-thinking) devolver JSON
  cortado com `review_output_tokens=800`, sem nova tentativa. Agora são 2048 tokens, o broker repete o mesmo revisor
  quando ele é o único (pedindo JSON compacto) e o motivo aparece em português. Revisão continua obrigatória.
  Script: `wsl/ajustar-revisao.sh`; backup em `/root/ultron-local/backups/revisao-*`.
- **Stream Deck** (`D:\GIT\streamdeck`): tudo que abriria página, site ou app abre no Saitama. Novo `POST /open`
  (`desktop_open.py`), `abrir-local.js` intercepta links, `window.open` e links dos painéis embutidos; "Entrar" em
  reunião abre Teams/Zoom pelo app e Meet/Webex/GoTo/Whereby/Jitsi/Chime no navegador do desktop; os botões
  "Abrir … no Saitama" e os atalhos ↗ de e-mails/reuniões abrem no computador. Script: `wsl/aplicar-streamdeck.sh`;
  backup em `D:\GIT\_backups\streamdeck-*`.
- **Autostart do WSL** (`C:\Users\yurim\.hermes-autostart.vbs`, tarefa HermesUltronAutostart): sem a janela
  "Permissão negada"; caminho completo do `wsl.exe`, novas tentativas por ~3 min, sem âncora duplicada e log em
  `%LOCALAPPDATA%\hermes-autostart.log`. Script: `wsl/corrigir-autostart.sh`; backup em `wsl/backups/autostart-*`.


## Parte 2 de 28/09/2026

- **Transcrição do Hermes desktop** ("Falha na transcrição… TimeoutError"): o desktop espera 20 s e o Whisper local era descarregado após 180 s ocioso; recarregar levava ~28 s. Agora `stt.local.unload_after_idle_seconds: 0` e o `ultron_lab/stt_warmup.py` carrega o modelo em segundo plano quando o gateway sobe.
- **Ata formal** (`meeting_ata/render_report.py`, instalado em `meeting_copilot/render_report.py`): modelo "Ata formal de reunião" (Chamada, Participantes, Aprovação das Atas Anteriores, Relatórios Apresentados, Assuntos Pendentes, Deliberações com tabela de encaminhamentos, Encerramento com assinaturas), logotipo hexagonal do Ultron e paleta lilás do Stream Deck. Análise executiva e transcrição integral viram anexos.
- **Harvey** (`harvey_juridico/`, só no perfil jurídico, via `ultron_team/worker.py`): vademecum_consultar, planalto_artigo, lexml_buscar, datajud_processo, djen_comunicacoes, prazo_processual, jurisprudencia_links, tj_jurisprudencia, frank_verificar/frank_relatorio, mais `web`. Vade Mecum em `/root/.hermes/profiles/harvey/juridico/`.
- Varredura do GitHub: `docs/ferramentas-github-2026-09-28.md`.
