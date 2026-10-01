# Repositorios, video e automacao local

> Estado de instalacao atualizado em [01/10/2026](INTEGRACOES-2026-10-01.md).
> Abaixo permanece o registro da analise de 30/09, nao a disponibilidade atual.

Analise em 30/09/2026 via GitHub CLI autenticada, clones de leitura e arquivos
de implementacao. Popularidade nao foi usada como prova de seguranca ou ganho.
Nenhum instalador de terceiros foi executado. Hermes/Ultron continuam locais;
nenhuma VPS participa. Este documento nao publica dados privados das contas.

## Decisoes

| Repositorio | Decisao para o Ultron | Ganho e limite |
|---|---|---|
| [video-use](https://github.com/browser-use/video-use) | Adaptar primeiro | Timeline textual, tempos de palavras, fades de audio e inspecao nas transicoes. Aproveita FFmpeg/Hyperframes existentes. Nao e um gerador de cenas nem um publicador TikTok. Transcricao upstream chama ElevenLabs; nao ativar envio de midia/custo por padrao. |
| [no-ai-slop](https://github.com/petergyang/no-ai-slop) | Incorporar criterios editoriais | Money e Ultron podem revisar roteiros/entregas mantendo voz propria, cortando frases genericas e exageros. Nao detecta autoria por IA com confiabilidade, nao valida fatos e nao precisa alterar SOULs. |
| [SkillSpector](https://github.com/NVIDIA/SkillSpector) | Adotar em etapa isolada de auditoria de skills | Analise estatica, riscos de prompt injection, exfiltracao e dependencias; revisao antes de instalar/atualizar skills, nao a cada saudacao. Requer Python >=3.12 no commit analisado; ambiente Hermes usa 3.11. Instalar em ambiente separado, com versao fixada e scanner sem acesso a segredos. Nao instalado nesta etapa. |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | Inspiracao arquitetural, sem substituir Hermes | Plugins com ciclo de vida, eventos tipados, registros persistentes e ferramentas por escopo. Projeto em developer preview; o proprio SAFETY.md diz que nao e auditado nem pronto para producao. Um segundo harness adicionaria estado/roteamento concorrente. |
| [Maestro](https://github.com/mobile-dev-inc/Maestro) | Reservar para testes mobile/web | Fluxos YAML, asserts, espera automatica e MCP podem ajudar Perseu/Iron Man a validar apps. Requer Java 17+ e dispositivo/emulador/navegador configurado. Nao resolve criacao de video; nao instalar emulador pesado sem caso concreto. |
| [Omarchy](https://github.com/omacom/omarchy) | Nao instalar no ambiente atual | Distribuicao Linux e experiencia desktop, nao biblioteca para Hermes. Aproveitar ideias de operacao documentada, atalhos, snapshots e diagnostico, sem trocar Windows/WSL ou importar dotfiles. |
| [PhoneHarness](https://github.com/PhoneHarness/PhoneHarness) | Inspiracao para verificacao e roteamento | Prefere CLI/MCP quando existe caminho exato, usa GUI quando necessario, avalia efeitos verificaveis e guarda traces. Stack orientada a Android/Termux/emulador, nao TikTok editor. API retornou licenseInfo=null e clone nao apresentou LICENSE na raiz: esclarecer licenca antes de incorporar codigo. |

As decisoes sao inferencias para este ambiente, nao benchmarks entre produtos.

## Referencias de codigo

- DeepSeek: `docs/architecture.md`, `SAFETY.md`; eventos de sessao duraveis vs eventos de agente em execucao.
- video-use: `helpers/render.py`, `helpers/timeline_view.py`, `helpers/transcribe.py`; cortes com fades de 30 ms, visao composta sob demanda, chamada Scribe externa.
- no-ai-slop: `skills/no-ai-slop/SKILL.md` e `eval.md`; preservar voz e nao introduzir novas alegacoes.
- SkillSpector: `pyproject.toml`, `src/skillspector/cli.py`, `nodes/analyzers/osv_client.py`. `--no-llm` desliga analise LLM, mas nao significa ausencia de rede: ha consultas de vulnerabilidades. Para isolamento estrito, restringir rede e aceitar cobertura reduzida explicitamente.
- Maestro: README, CLI/MCP e requisitos de dispositivos. Nao confundir Maestro Studio desktop com o codigo aberto do framework.
- Omarchy: README/manual, especialmente operacao e snapshots.
- PhoneHarness: README/benchmark; avaliar estado final e efeitos colaterais, nao apenas cliques.

## Revisoes analisadas

| Repositorio | Commit |
|---|---|
| deepseek-ai/deepseek-harness | `639ed015397290b3745d163aafe02ffee4aa3f84` |
| browser-use/video-use | `b877063835e6ea6e457124da7e28a0ae26691dc3` |
| petergyang/no-ai-slop | `000650b156983f5159695b441477f4e63b25dc85` |
| NVIDIA/SkillSpector | `2226747e4ca97198bb82faf5085b8a75f2e1dc02` |
| mobile-dev-inc/Maestro | `51538ec1d3bb0c5eb84f29fee1687d0ccd2817c7` |
| omacom/omarchy | `8b4eae66da2938ba9559f103b18dbf85cdf28a70` |
| PhoneHarness/PhoneHarness | `1cdc0d963641d517f5deb687adb37332cf844e70` |

MIT: DeepSeek Harness, video-use, no-ai-slop, Omarchy. Apache-2.0:
SkillSpector e Maestro. Dependencias podem ter termos diferentes. Esta etapa
implementou adaptacoes proprias, sem copiar os projetos completos para o agente.

## Problemas observados no fluxo atual

O job TikTok apontava para `auto_tiktok_publicador_loop.py`, embora o fluxo
documentado use `affiliate_autonomy.py`. O script legado afirma que gera
quando a fila acaba, mas apenas procura dois caminhos fixos e retorna False
se nada estiver disponivel. Tambem aceitava candidate_ids ou texto de sucesso
como publicacao, sem demonstrar a releitura do post exato. Nao usar esse caminho
como fallback de disponibilidade.

O MP4 mais recente examinado tem 29,664 s, H.264, 1080x1920 e audio AAC.
Decodifica, mas apresenta cinco planos estaticos, muitos textos e alegacoes
comerciais. A contact sheet nao prova audio correto nem confirma as alegacoes.
O preflight detectou congelamento nas cinco cenas. O original foi preservado;
nao foi revisado, republicado ou classificado como anuncio aprovado.

O job de oportunidades informou falta de oportunidades autenticadas no Seller.
Isso e pendencia de autenticacao/coleta, nao defeito de render nem motivo para
inventar dados ou substituir cookies. Precisa de verificacao da sessao pelo
titular, sem compartilhar senhas em conversa.

## Implementacao desta etapa

Fontes reproduziveis em `agent/video/`:

- `media_preflight.py`: prova tecnica local com hash, audio, proporcao exibida,
  duracao, decodificacao completa e alertas de preto/silencio/congelamento.
- `affiliate_quality.py`: envelopes de audio de 30 ms e vinculo entre MP4,
  preflight e recibo. Um resultado tecnico nao concede aprovacao visual.
- `patch_affiliate.py`: alteracoes restritas por ancoras no renderer, guard,
  evidencia do broker e instrucoes da cadeia Kanban; recusa fonte desconhecida.
- `cron_migration.py`: somente payload/contexto do job existente; nao muda
  horarios, permissao, conta, ferramentas, estado ou destino. Recusa job ativo.
- `VIDEO-QUALITY.md`: gatilhos por contexto, revisao editorial e audiovisual,
  evidencia exigida e limites das ferramentas. Nao chama todas em todo turno.

Preflight entra antes do recibo final de render. O guard rejeita evidencia
ausente/alterada; o broker recebe o arquivo e seus avisos. Render antigo precisa
de nova revisao, nao de recibo editado para parecer aprovado. Publicacao e
comentario continuam sob os guards e autorizacoes existentes.

Nao instalamos novo agente, SO, modelo de video, emulador ou rotina duplicada.
O ganho implementado e verificabilidade/qualidade do caminho existente, nao
promessa de viralidade, renda ou geracao de cenas sem provedor disponivel.

## Verificacao local

- 28 testes de video passaram, incluindo FFmpeg real e montagem nativa de
  material sintetico, sem provedor TTS e sem publicacao.
- 22 testes existentes da campanha afiliada passaram com o guard instalado.
- 49 testes de revisao do agente passaram como regressao.
- MP4 original preservado; analise tecnica e contact sheet privadas em
  `outputs/video-audit-20260930` no workspace do titular, fora deste repositorio.
- Restic `80266082` preserva codigo, configuracao cron e skill antes da etapa;
  `4bc8cd65` preserva as instrucoes locais AGENTS.md. Nenhum banco de campanhas,
  cookie, SOUL ou aprovacao foi editado.

O renderer, guard, evidencia do broker e instrucoes de producao foram instalados.
A migracao aguardou o termino da execucao das 18h e atualizou o job existente
via API nativa Hermes, sem reiniciar o gateway. ID, horarios (00h, 12h, 15h,
18h e 21h), ferramentas, skills, permissao, destino e historico foram preservados.
O novo prompt chama `affiliate_autonomy.py tick` e deixa de repetir contexto
de execucoes antigas com instrucoes do publicador legado. Leitura posterior
confirmou payload novo, nenhuma execution claim ativa e proxima execucao as
21h de 30/09. Isso nao comprova que a nova cadeia inteira tenha publicado:
nenhuma postagem real foi disparada durante os testes desta alteracao.
