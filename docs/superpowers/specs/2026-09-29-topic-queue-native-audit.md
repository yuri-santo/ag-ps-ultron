# Auditoria da base nativa para a fila por assunto

Data: 2026-09-29. Escopo: leitura do Hermes instalado localmente em
`/opt/hermes-agent-20260924`, configuracao selecionada sem segredos e testes
isolados. Nao houve alteracao de runtime, restart, envio Telegram, acao pessoal
ou chamada de modelo nesta revisao. O diretorio instalado nao e um checkout
Git; nao atribuir estes achados a um commit upstream nao verificado.

## Achados prioritarios

### 1. `done` nativo nao equivale a revisao independente aprovada

`hermes_cli/kanban_db.py:2723`, `complete_task`, permite fechar tarefas em
`running`, `ready`, `blocked` ou `review`, com verificacoes de claim,
dependencias e evidencia textual. Nao exige o manifesto do Ultron. O texto
padrao para aprovacao manual pode ser usado sem nova evidencia.

Consequencia: coluna review e prompts nao garantem "nada sem validacao".
Verificar candidato/versao/evidencia e impedir bypass em todos os caminhos de
conclusao de resultados gerenciados. Etapa interna concluida nao e entrega.

### 2. Hooks de Kanban sao observadores, nao barreiras

`hermes_cli/plugins.py:163` e `hermes_cli/kanban_db.py:242` documentam callbacks
apos commit e ignoram seus retornos/falhas. Callback de conclusao nao pode
desfazer com seguranca a liberacao de dependentes ja ocorrida.

Reutilizar para acordar reconciliacao e coletar metricas; veto autoritativo
precisa ocorrer antes da transicao, restrito a cards gerenciados.

### 3. Notificador nao e outbox de entrega confirmada

`hermes_cli/kanban_db_notify.py:352`, `claim_unseen_events_for_sub`, avanca
cursor em transacao antes de enviar. O notifier pode recuar em falha conhecida,
mas queda entre claim e envio deixa janela de perda.

`gateway/kanban_watchers_notifier.py` tambem formata `review_requested`.
Modo wake evita ping passivo, nao substitui aprovacao nem recibo persistente.
Reusar adapter/roteamento; manter outbox especifico, receipts por parte e envio
incerto explicito. Nao prometer exatamente-uma-vez.

### 4. Worker pode classificar revisao pendente como sucesso

`agent/plugins/ultron_team/worker.py` do repositorio publico calcula falha por
`failed`, `partial` e texto vazio, mas nao considera `completed=false` ou
`model_review` pendente. A mesma omissao foi encontrada no worker privado.
`agent/turn_finalizer.py:628` do Hermes define `completed=false` quando a
revisao independente ainda nao terminou, sem necessariamente definir failed.

Corrigir esse contrato antes de usar respostas dos workers como prova de
sucesso. A presente alteracao de documentacao ainda nao corrige o bug.

### 5. Review nativo e orientado a software

`hermes_cli/kanban_db_dispatch.py:2073` injeta `sdlc-review` nos workers da
faixa review. Nao implementa competencia clinica, financeira ou SAP.
Usar ciclo de vida nativo sem tratar essa skill como aprovador universal.

### 6. Worker nativo pode ter ferramentas diferentes do bridge

`hermes_cli/kanban_db_dispatch.py:2620` resolve toolsets CLI do perfil;
`:2676` monta comando com esses toolsets. O bridge atual mantem allowlist menor.
Migrar spawn nao prova equivalencia. Testar definicoes efetivas de ferramentas,
nao apenas nomes de toolsets no YAML.

### 7. Limites tem semanticas diferentes

`hermes_cli/kanban_db_dispatch.py:1801` calcula teto padrao por memoria:
aproximadamente MemTotal/512 MiB, limitado entre 2 e 8. `null` usa esse calculo;
nao significa ilimitado no WSL Linux. `:2161` mostra que `max_spawn` e teto
concorrente por board. `gateway/kanban_watchers_dispatcher.py:35` informa que
essas configuracoes sao lidas no boot.

Leitura pontual do host resultou em capacidade derivada de 8, mas nao e um
benchmark de oito trabalhos pesados nem garantia de oito vagas livres.
Concorrencia por perfil e guarda de pressao de memoria continuam relevantes.

`tools/delegate_tool_config.py:89` permite `oneshot_max_children=0` para remover
teto total de filhos. `:129` documenta que delegacao async **rejeita**, em vez
de enfileirar, ao atingir capacidade. Nao substitui fila duravel Kanban.

### 8. Decomposicao nao e roteamento completo de conversa

`hermes_cli/kanban_specify.py:137` limita campos do prompt, incluindo corpo a
4000 caracteres. `hermes_cli/kanban_decompose.py:307` chama cliente auxiliar,
interpreta JSON flexivel e aplica/promove grafo. Nao garante cobertura de
mensagem longa, trechos de origem, isolamento de citacoes ou reply por assunto.

`hermes_cli/plugins.py` documenta `pre_gateway_dispatch` antes de auth.
Admissao deve cobrir caminhos livre/ocupado apos controles nativos, sem executar
modelo nem gravar dados de nao autorizados.

### 9. Fila ocupada tem teto e nao substitui admissao duravel

`gateway/run.py:4034` define `_BUSY_QUEUE_MAX_PENDING = 32`.
`gateway/run_busy.py:401` descarta mensagens excedentes; o FIFO e mantido em
memoria. Persistir ingresso gerenciado antes desse caminho e testar 33+
mensagens e queda abrupta, nao somente restart com encerramento normal.

### 10. Delegacao independente nao elimina status intermediario

`tools/delegate_tool_dispatch.py:321` instrui o modelo a encerrar turno com
status de uma linha e retornar resultados como novos turnos. Silenciar busy
ack nao resolve esse caminho. Turnos de mero despacho e completion wakes
gerenciados precisam passar pela politica de saida sem pings intermediarios;
somente resultado aprovado sai pelo outbox.

## Recursos aproveitaveis

- `hermes_cli/config_defaults.py:1854`: namespace Kanban e configuracoes reais.
- `gateway/kanban_watchers.py`: dispatcher embutido, singleton e notifier.
- `hermes_cli/kanban_db_dispatch.py`: memoria, perfis, recuperacao e spawn.
- `hermes_cli/kanban_db_graph.py`: decomposicao persistente e dependencias.
- `hermes_cli/kanban_db.py:3952`: `schedule_task`; estaciona sem horario proprio.
- `hermes_cli/kanban_db.py:3644`: `unblock_task`; revalida dependencias.
- `hermes_cli/kanban_db.py:3724`: invalidacao de descendentes apos reabrir pai.
- `tools/delegate_tool_config.py`: conclusoes independentes de delegacao.
- `hermes_cli/config_defaults.py:1959`: descoberta nativa de ferramentas.
- `gateway/run.py:1960` e `:2081`: chaves `display.*` de modo ocupado e confirmacoes.

APIs Python sao superficie da versao instalada, nao promessa de estabilidade.
Instalador deve verificar assinaturas/ancoras e recusar divergencia, em vez
de substituir modulos inteiros por copias antigas.

## Verificacao executada

Conftest foi inspecionado: isola HERMES_HOME antes da importacao, remove
credenciais dos testes, protege bancos reais e desativa instalacao automatica
de dependencias. Comando no WSL Debian:

```sh
/opt/hermes-agent-20260924/venv/bin/python -m pytest -q \
  /opt/hermes-agent-20260924/tests/hermes_cli/test_kanban_memory_guard.py \
  /opt/hermes-agent-20260924/tests/hermes_cli/test_kanban_host_cap.py \
  /opt/hermes-agent-20260924/tests/hermes_cli/test_kanban_per_profile_cap.py \
  /opt/hermes-agent-20260924/tests/hermes_cli/test_kanban_decompose_db.py \
  /opt/hermes-agent-20260924/tests/hermes_cli/test_kanban_review_lifecycle_complete.py \
  /opt/hermes-agent-20260924/tests/gateway/test_kanban_notifier_wake_only_ordering.py
```

Resultado: **54 passed in 36.14s**. Confirma esse subconjunto em testes isolados.
Nao prova fila por assunto end-to-end, capacidade real de provedores, entrega
Telegram ou futuras barreiras de aprovacao.

## Resultado

Desenho anterior duplicava capacidades e fixava concorrencia/correcoes
prematuramente. A [especificacao revisada](2026-09-29-topic-queue-design.md)
conserva Kanban como motor unico, explicita contratos adicionais e separa
capacidade ajustavel de permissoes/validacao. Implementacao e ativacao seguem
como trabalho tecnico, sem nova rodada de aprovacao do mesmo pedido.

## Adapter Testado Em 01/10/2026

`agent/topic_queue` agora concilia intencoes duraveis com cards Kanban nativos
em estado blocked, sem assignee, sessao ou subscriptions. A reserva do board
precede o primeiro commit nativo; retry recupera correlacao apos crash antes
do vinculo privado. O write_txn externo fecha a corrida do lookup nativo de
idempotencia. Criacao nao implica aprovacao nem habilita o dispatcher.

Triagem usa o cliente auxiliar nativo `kanban_decomposer` sem ferramentas,
sem recortar texto e sem invocar o decompositor que promove o grafo. A proposta
precisa preservar os spans autorizados e o snapshot completo da origem; versao,
validade e contrato sao rechecados no mesmo commit da proposta. Nao ha modelo
real nos testes: a acuracia da classificacao continua sem benchmark.

103 testes passaram no adapter, incluindo Kanban temporario e falhas de
concorrencia/reinicio; o subconjunto nativo acima voltou a passar com 54 testes.
Nenhum card foi criado no board real. Ainda faltam as barreiras de aprovacao,
ingresso autenticado anterior ao FIFO e outbox; a fila nova nao esta ativa.
