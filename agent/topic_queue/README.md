# Admissao duravel por assunto

**Conectada e ativada no gateway local em 01/10/2026**, somente para texto simples
no DM autorizado do titular. `runtime.py` liga os componentes ao Kanban nativo,
workers restritos, revisores reais e outbox Telegram. Os testes automatizados
continuam isolados, sem enviar mensagens reais. Consulte escopo, limites,
evidencias e reversao no [guia operacional](../../docs/GATEWAY-POR-ASSUNTO.md).
Segue o [desenho aprovado](../../docs/superpowers/specs/2026-09-29-topic-queue-design.md).

## Implementado

- Ingresso SQLite idempotente por plataforma, conta, dono, chat, thread e mensagem.
- Commit sincrono antes de confirmar admissao; reinicio conserva pendencias.
- Proposta de triagem com schema fechado, perfis permitidos e cobertura do texto.
- Trechos de pedido delimitados pelo adapter confiavel, nunca pelo modelo.
- Versoes por assunto, dependencias sem ciclos e invalidacao dos descendentes.
- Intencoes de cards com correlacao estavel, sem criar outro scheduler.
- Reconciliacao com Kanban nativo em transacao externa, com cards bloqueados e
  sem agente, sessao, notificacao ou execucao; recuperacao apos commit parcial.
- Proposta semantica pelo cliente auxiliar nativo, com JSON estrito, snapshot
  dos assuntos da mesma origem e preservacao da mensagem pendente em falhas.
- Referencias de replies isoladas por origem; nao equivalem a recibos de envio.
- Preparacao imutavel do candidato/autor real/partes finais antes da revisao.
- Aprovacao por competencias e revisor independente, vinculada a versao,
  card, execucao, modelo servido e hashes obtidos por leitores do host.
- Outbox por parte, lock de conversa entre processos, intent duravel, recibos
  atomicos e reconciliacao sem repetir um envio de resultado incerto.

`TopicStore(path, allowed_profiles=...)` exige diretorio privado dedicado em
Linux/WSL: pasta 0700, banco 0600. Nao apontar para a raiz do perfil, para uma
pasta compartilhada ou para este repositorio. Texto integral permanece privado.
O chamador deve tratar `QueueError` como operacao nao confirmada. A allowlist
de perfis e os trechos autorizados devem vir do runtime confiavel.

## Validacao

```sh
python -m pytest agent/topic_queue -q
```

Em 01/10/2026: 103 testes aprovados em Python 3.11/WSL, incluindo 40 ingressos
seguidos de encerramento abrupto do processo, duplicatas concorrentes, schema
invalido, referencias entre chats, cobertura incompleta e versao obsoleta.
Os testes de Kanban usam a instalacao Hermes local e `HERMES_HOME`/boards
temporarios; sao pulados quando `hermes_cli.kanban_db` nao esta instalado.
As respostas do modelo sao simuladas: a suite comprova os limites do contrato,
nao a acuracia semantica de um provedor real.
`unittest discover` nao executa estes testes: eles usam pytest.

## Integracao Nativa Preparada

`NativeCards` recebe explicitamente uma factory de conexao independente,
`create_task` e `write_txn` do Hermes. Reserva primeiro o caminho do board na
base privada e depois concilia a correlacao sob locks privado e nativo, nessa
ordem. Nao troca o board, recria cards arquivados ou aceita cards adulterados.
Pais precisam estar conciliados e sem subscriptions; versoes antigas nunca
sao liberadas. `card_intents()` retorna o ID conciliado, mas `released=False`.

`plan_ingress` recebe roster e contexto do host confiavel, nao da mensagem.
Nao corta texto para caber no modelo; orcamento explicito excedido deixa a
mensagem pendente. Replies sem referencia conhecida tambem ficam pendentes.
O adapter nativo usa a rota auxiliar `kanban_decomposer`, as configuracoes e
afinidade do Hermes, sem ferramentas e sem o decompositor que altera o grafo.
Executar fora do event loop do gateway. O host continua responsavel pelo retry.
Antes do commit, todo o snapshot e revalidado atomicamente (versao, validade
e contrato), inclusive quando um predecessor invalida o assunto sem mudar seu
numero de versao. Um contexto ja invalido e estavel pode ser replanejado;
dependencias necessarias precisam estar representadas no novo plano.

## Integracao operacional

`gateway_adapter.py` admite apos autorizacao, antes do agrupamento nativo.
`native_guard.py` exige aprovacao antes de completar e impede reescrita de cards
gerenciados. `worker_host.py` usa claims/processos do Kanban; `specialist.py`
preserva o worker restrito e captura o modelo servido. `reviewer.py` valida o
texto congelado por dominio e auditoria. `native_patch.py` fixa cinco fontes
auditadas, inclusive supressao do notificador duplicado. `manage_gateway.py`
oferece refresh, ativacao/desativacao e rollback por checksum.

Validacao do pacote: 264 testes aprovados, 1 pulado. Probe real pelo despachante
nativo terminou com triagem e especialista `done`, dois pareceres e uma
aprovacao. Nao foi enviado teste ao Telegram; a entrega real ao titular ainda
depende da proxima interacao. Os testes de transporte usam doubles do Telegram.

## Aprovacao e envio preparados

`delivery.py` recebe leitores confiaveis `execution`, `review`, `policy`,
`control` e `outcome`. As APIs aceitam IDs, nunca aprovacoes declaradas pelo
modelo. Politica/roster, dependencias, controle e versao sao revalidados antes
de cada parte. Texto preformatado e congelado antes da revisao, sem formatar
novamente durante envio. Esta versao transporta somente texto.

`dispatch_next(scope, send)` segura flock Linux/WSL por conversa e transacao
privada durante cada envio. O host DEVE impor timeout ao transporte e coordenar
mudancas de controle com a mesma transacao. `reconcile` so aceita recibos do
leitor confiavel. Timeouts/crashes nao geram reenvio automatico. Uma parte
unica/final incerta nao bloqueia outra entrega independente; um grupo multipart
incompleto e ainda valido nao e intercalado. Cancelamento/invalidacao impede
partes restantes, sem apagar tentativas cujo efeito externo e desconhecido.

70 testes da entrega passaram em 01/10/2026, incluindo multiprocessos, falha de
persistencia de recibo, cancelamento, reabertura e recuperacao. Os leitores e
transportes desses testes sao simulados. Nao constitui teste do Telegram real.
`patch_worker_proof.py` preserva metadados/hashes dos resultados restritos;
nao transforma status `not_required` em aprovacao de comite.
