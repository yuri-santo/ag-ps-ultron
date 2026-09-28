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
