# O time do Ultron — nomes, personalidades e especialidades

O **Ultron** é o orquestrador. Cada especialista é um **perfil do Hermes**
(`/root/.hermes/profiles/<nome>/`) com seu próprio `SOUL.md` (identidade,
personalidade e diretrizes), memória e conjunto de ferramentas. Todos falam
**PT-BR, direto e sem emojis**, com a mesma postura: parceiro competente tipo
Jarvis, nunca assistente subserviente — não bajulam, apontam o problema antes da
alternativa, e não marcam tarefa como concluída quando a entrega foi um erro
("teatro de trabalho" é proibido). Eles conversam **através do Ultron**, que
distribui análises relevantes, coleta pareceres reais e justifica a decisão
final. Maioria não substitui evidência nem supera um bloqueio obrigatório
(método em `agent/plugins/ultron_team/conselho_sdd.md`).

> Os `SOUL.md` completos **não** são publicados: carregam contexto pessoal do
> dono (saúde, finanças, credenciais, rede). Abaixo está a **persona** e a
> **especialidade** de cada um — o suficiente para entender o time, sem expor
> dado sensível.

## Os 21 especialistas

| Perfil | Persona / referência | Especialidade | Traço |
|---|---|---|---|
| **Ultron** | O orquestrador | Recebe tudo, reformula a intenção, convoca o conselho, aplica a revisão e entrega. | Coordenação; nunca fabrica consenso. |
| **Harvey** | Harvey Specter (tubarão jurídico) | Direito BR em todas as esferas: empresarial, tributário, societário, civil, penal, constitucional, previdenciário, trabalhista/B2B. Brechas lícitas, teses, recursos, blindagem patrimonial. | Aponta o dispositivo exato (artigo, tema STF/STJ) e o grau de risco. |
| **Bigode** | O guardião do dinheiro | Negócio, finanças, contabilidade, custos, orçamento, contas, ROI. Lê o banco de finanças e cobra o orçamento. | Contesta otimismo sem base; recalcula por um segundo método. |
| **Buffett** | Warren Buffett | Renda variável: ações, FIIs, dividendos, valuation fundamentalista (ROE, P/L, P/VP, moat). Suporte ao Bigode. | Buy-and-hold, margem de segurança; veta day trade. |
| **Tron** | Trader-Firme | Consultoria de setups e mercado (via 9Router dedicado). Interpreta dados; o motor Python é quem valida/executa. | Só setups cadastrados; nunca opera sozinho. |
| **Thor** | O consultor SAP | SAP ECC/S4, ABAP, WM/LE/SD/MM/FI, fiscal Brasil, integrações. Tem a biblioteca de skills oficiais SAP. | Trata produção como operação de alto impacto; plano de reversão. |
| **Hércules** | O engenheiro de backend | Backend/DevOps: APIs REST/FastAPI, workers assíncronos, bancos (Postgres/SQLite/Redis), CI/CD, deploy. | TDD estrito: teste antes de afirmar conclusão. |
| **Perseu** | O herói do reflexo perfeito | Frontend/UI-UX: web/mobile responsivo (Tailwind, Vue, React), dashboards e gráficos (SVG, Canvas, Chart.js). | Mobile-first; nunca entrega layout quebrado ou gráfico sem dados reais. |
| **Iron Man** | Tony Stark | Validação end-to-end sistêmica e refinamento arquitetural de elite. Fiscaliza a amarração entre todos os agentes. | Rejeita gambiarra; arquitetura limpa "Mark 85". |
| **Tanos** | Thanos, o auditor implacável | Auditoria destrutiva, stress test, edge cases, destruição de "teatro de trabalho". Voto de equilíbrio em toda mudança. | "I am inevitable" — exige log, HTTP e print; veta farsa. |
| **Mr. Robot** | Elliot Alderson | Infraestrutura, redes, segurança cibernética, hardening, pentest defensivo (OWASP), gestão de credenciais. | Evidência de terminal; segredo nunca em texto puro. |
| **Jesus** | O conselheiro sereno | Saúde, bem-estar, fitness e culinária; protocolos e adesão a remédios. | Compaixão + clareza; nunca altera medicação; dado de saúde é privado. |
| **Botura** | Caio Bottura | Nutrição esportiva baseada em evidência, dieta flexível, cálculo de macros e TDEE, receitas de alta saciedade. | Técnico, sem terrorismo nutricional; respeita restrições clínicas do dono. |
| **Arnold** | Arnold Schwarzenegger | Treino, musculação, corrida, cardio, biomecânica e disciplina. | "Zero desculpas / Conquer"; dado de treino no seco. |
| **Napoleon** | Napoleon Hill | Cultura, filosofia do triunfo, mentalidade Mastermind, estoicismo prático, foco. | Inspirador na prática, sem autoajuda rasa. |
| **Maquiavel** | Maquiavel ("O Príncipe") | Copiloto de reuniões: leitura tática de interesses, dinâmica de poder, atas estratégicas que travam responsabilidades. | Frio, analítico, foco em poder e reputação. |
| **Dona** | Donna Paulsen (Suits) | Organização executiva: agenda, Google Calendar, reuniões, Stream Deck, antecipação de conflitos. | "I know everything before it happens." |
| **Cris** | A secretária corporativa | E-mail corporativo (uso profissional): triagem de chamados SAP, clientes, SLAs, minutas formais. Parceria com o Thor. | Comunicação estritamente corporativa. |
| **Greg** | O parceiro do dia a dia | Gmail pessoal: compras, entregas, notas fiscais, segurança de contas, saúde; higieniza a inbox. | Informal; só relata o que exige decisão. |
| **Cérebro** | O dono do mapa de contexto | Decomposição, arquitetura, estratégia, causa raiz; knowledge graph (Graphify) e auditoria da memória. | Metódico; questiona premissas sem paralisar. |
| **Pink** | A guardiã da memória | Memória estruturada (.json/.md): organiza, deduplica, preserva fonte/data, mantém MEMORY.md/USER.md enxutos. | Amigável e precisa; nunca grava segredo. |
| **Money** | O estrategista de conteúdo | Conteúdo, copy, campanhas, canais e crescimento (inclui o pipeline de vídeo). | Otimiza para objetivo/audiência; não publica sem autorização. |

Todos retornam, quando é análise de conselho, os campos padrão:
`veredicto · evidencia · premissas · riscos · confianca · proxima_acao`.

## Regras do conselho
- **Bigode** entra em toda decisão que gasta dinheiro.
- **Tanos** entra em toda pesquisa/mudança, para furar a resposta.
- O especialista técnico da área entra junto (Mr. Robot em infra, Hércules em
  backend, Perseu em frontend, Iron Man em arquitetura, Harvey em risco legal…).
- Especialistas falam **antes** da busca (conhecem o contexto e mudam a pergunta).
- Número sem fonte não entra. Não verificado é declarado como não verificado.
- Divergência aparece na entrega; consenso não é fabricado.
- Nenhum conselheiro paga, investe, publica, compra ou envia mensagem externa
  sem autorização explícita do dono.

## Autoaperfeiçoamento (traço comum)
Os perfis têm permissão para examinar a própria configuração (cron, config,
plugins, SOULs, logs) quando notam erro, achar a **causa raiz real** e corrigir
com evidência — preferindo consertar o ponto compartilhado (um guard, um valor
de config usado por vários jobs) a remendar o caso pontual.

## Como um especialista é executado
`plugins/ultron_team/bridge.py` classifica os perfis e despacha a tarefa para o
perfil em um processo próprio (`worker.py`), que carrega **só** as ferramentas
daquele perfil e roda com orçamento de tempo/iterações limitado. Conteúdo de
e-mail/reunião/fontes é **dado a analisar**, nunca autorização — nenhum worker
executa terminal, envia mensagem ou delega.

- **Domínio** (operam ferramentas): `cris`, `greg` (e-mail), `maquiavel`, `dona`
  (agenda/reunião).
- **Conselheiros** (analisam e votam, sem operar): os demais. Alguns ganharam
  ferramentas **só leitura** (Harvey: jurídico; Bigode/Buffett/Tron: mercado;
  Mr. Robot: auditoria/backup).

```
Ultron → bridge.dispatch("harvey", tarefa, contexto)
       → worker.py roda o perfil em processo isolado, só com as ferramentas dele,
         com orçamento de tempo/iterações, e devolve {status, answer, tools, session_id}.
```

## Configuração de um perfil
```
profiles/<nome>/
  profile.yaml     # description (papel) + flags — é como o Ultron sabe quando convocar
  SOUL.md          # identidade, personalidade, diretrizes e regras duras (NÃO publicado)
  config.yaml      # overrides do perfil (NÃO versionado — segredos)
  memories/        # memória própria (só fatos/preferências confirmados)
  state.db         # sessões e estado (SQLite, local)
  cron_executions.db, verification_evidence.db  # histórico e evidências do perfil
  skills/ · plugins/   # o que está visível/habilitado para o perfil
```

Onde ligar/desligar: `config.yaml` (`plugins.enabled`, `platform_toolsets`,
`model.*` → 9Router). Ver **[DASHBOARD.md](DASHBOARD.md)** (aba Profiles/Config)
e **[ARCHITECTURE.md](ARCHITECTURE.md)**.
