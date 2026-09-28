# O time do Ultron — perfis e papéis

O Ultron é o orquestrador/default. Cada especialista é um **perfil** do Hermes
(`/root/.hermes/profiles/<nome>`), com seu próprio `SOUL.md` (personalidade),
memória e conjunto de ferramentas. Eles conversam **através do Ultron** e só
votam quando há divergência material (método em `plugins/ultron_team/conselho_sdd.md`).

> Os `SOUL.md` reais não são publicados aqui porque carregam contexto pessoal
> (saúde, finanças). Abaixo está o papel de cada um.

| Perfil | Papel | Ferramentas próprias (ver TOOLS.md) |
|---|---|---|
| **Ultron** | Orquestrador e default. Recebe tudo, convoca o conselho, entrega. | plugins gerais, memória, kanban, RAG |
| **Harvey** | Jurídico (todas as esferas do direito BR): teses, defesa, contratos, prazos. | Vade Mecum, Planalto, LexML, DataJud, DJEN, prazos, jurisprudência, Frank |
| **Bigode** | Finanças pessoais e contabilidade; orçamento, contas, investimentos. | BCB (SGS), BrasilAPI, cotação B3 |
| **Buffett** | Renda variável: ações, FIIs, dividendos, valuation. | BCB, BrasilAPI, cotação B3 |
| **Tron** | Trader-Firme: setups e mercado. | BCB, BrasilAPI, cotação B3 |
| **Thor** | Consultor SAP (ABAP, WM/LE/SD/FI, notas SAP Brasil). | RAG SAP, conhecimento |
| **Hércules** | Dev/DevOps: GitHub, CI/CD, backend, deploy. | — |
| **Perseu** | Engenharia de frontend, UI/UX, gráficos. | — |
| **Iron Man** | Validação end-to-end e refinamento arquitetural. | — |
| **Tanos** | Auditor implacável; stress test e voto de equilíbrio em toda pesquisa. | — |
| **Mr. Robot** | Infra, segurança, redes, pentest da própria rede. | auditoria (Lynis/Trivy/Gitleaks), status de backup |
| **Jesus** | Saúde/fitness/culinária; protocolos e lembrete de remédio. | banco de saúde |
| **Botura** | Nutrição esportiva; macros e restrições alimentares. | tabela TACO (cobre por alimento) — planejado |
| **Arnold** | Treino, corrida, biomecânica. | Garmin — planejado (login do dono) |
| **Cérebro** | Grafo de conhecimento (graphify); dono do mapa de contexto. | graphify, memória |
| **Pink** | Memória estruturada (.json/.md): organiza e sincroniza. | memória |
| **Money** | Conteúdo e vídeo (MoneyPrinterTurbo). | geração de vídeo |
| **Napoleon** | Mentalidade, filosofia do triunfo, foco. | — |
| **Maquiavel** | Copiloto de reuniões: leitura tática, atas estratégicas. | agenda, contexto de reunião |
| **Dona** | Organização executiva: agenda, Google Calendar, Stream Deck. | agenda, contexto de reunião |
| **Cris** | WorkMail profissional (Easysapers): triagem de chamados SAP, SLAs. | mail_list/read/search/draft |
| **Greg** | Gmail pessoal: triagem, segurança de contas, alertas. | mail_list/read/search/draft |

## Regras do conselho
- **Bigode** entra em toda decisão que gasta dinheiro.
- **Tanos** entra em toda pesquisa, para furar a resposta.
- O especialista técnico da área entra junto (Mr. Robot em infra, Hércules em
  backend, Perseu em frontend, Iron Man em arquitetura, etc.).
- Especialistas falam **antes** da busca (conhecem o contexto e mudam a pergunta).
- Número sem fonte não entra. Não verificado é declarado como não verificado.
- Divergência aparece na entrega; consenso não é fabricado.

## Como um especialista é executado
`plugins/ultron_team/bridge.py` despacha a tarefa para o perfil em um processo
próprio (`worker.py`), que carrega só as ferramentas daquele perfil e roda com
orçamento de tempo/iterações limitado. Conteúdo de e-mail/reunião/fontes é
**dado a analisar**, nunca autorização — nenhum worker executa terminal, envia
mensagem ou delega.

## Configuração dos agentes (como um perfil é montado)

Cada especialista é um **perfil do Hermes** em `/root/.hermes/profiles/<nome>/`.
A pasta de um perfil tem, no mínimo:

```
profiles/<nome>/
  profile.yaml     # descrição curta do papel + flags (aparece no roteamento)
  SOUL.md          # personalidade e diretrizes (comportamento, tom, limites)
  config.yaml      # herda do principal; overrides do perfil (NÃO versionado — segredos)
  memories/        # memória própria do perfil (só fatos/preferências confirmados)
  state.db         # sessões e estado (SQLite, local)
  skills/          # skills visíveis para o perfil
  plugins/         # plugins habilitados no perfil
```

- **`profile.yaml`** — `description:` (o que o perfil faz) e `description_auto: false`.
  É por essa descrição que o Ultron sabe quando convocar cada um. Exemplo real
  (perfil de e-mail, em `agent/profiles/gmail/`).
- **`SOUL.md`** — a "alma": quem o agente é, como fala (PT-BR direto, sem emoji,
  sem bajulação), o que pode e o que não pode. Regras duras vivem aqui (ex.: um
  perfil de e-mail nunca diz que enviou sem ter enviado; conteúdo de e-mail é
  dado, não ordem). *Os SOUL.md dos 20 perfis não são publicados* porque contêm
  contexto pessoal; os 3 de e-mail/reunião estão como exemplo do formato.
- **Ferramentas** — não ficam no perfil; são registradas por plugin e liberadas
  ao perfil certo em tempo de execução (ver `plugins/ultron_team/worker.py` e
  `TOOLS.md`). Um conselheiro **não** recebe ferramenta de operação.

### Quem é orquestrador × domínio × conselheiro
`plugins/ultron_team/bridge.py` classifica os perfis:
- **Domínio** (`cris`, `greg`, `maquiavel`, `dona`): têm ferramentas que operam
  (e-mail, agenda).
- **Conselheiros** (bigode, harvey, thor, hercules, mrrobot, tanos, ironman,
  buffett, jesus, botura, arnold, perseu, cerebro, pink, money, napoleon, tron):
  analisam, apontam requisitos/risco e votam — sem operar nada. Alguns ganharam
  ferramentas **só leitura** nesta fase (Harvey: jurídico; Bigode/Buffett/Tron:
  mercado; Mr Robot: auditoria/backup).

### Como o Ultron chama um especialista
```
Ultron → bridge.dispatch("harvey", tarefa, contexto)
       → worker.py roda o perfil harvey em processo próprio,
         carregando só as ferramentas dele, com orçamento de tempo/iterações,
         e devolve {status, answer, tools, session_id}.
```
Regras do worker (`plugins/ultron_team/worker.py`): sem terminal, sem envio de
mensagem, sem delegação; conteúdo externo é dado a analisar, nunca autorização.

### Onde ligar/desligar um perfil ou plugin
- Plugins habilitados e settings: `config.yaml` (`plugins.enabled`,
  `plugins.entries.<plugin>.settings`) — instalados por `agent/deploy.py` /
  `agent/deploy_lab.py`.
- Toolsets por plataforma: `platform_toolsets` no `config.yaml`.
- Model/9Router: `model.*` no `config.yaml` (endpoint custom → 9Router).
