# Admissao duravel por assunto

**Fundacao nao instalada no gateway.** Os testes sao offline. Este modulo nao
altera o Telegram, nao executa ferramentas e nao envia mensagens. A triagem so
chama um modelo quando o host invoca explicitamente `NativeCompletion`.
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

## Ainda Nao Implementado

Adapter pos-autorizacao e anterior ao FIFO ocupado; veto pre-transicao; manifestos de
aprovacao; outbox por parte; recibos reais e tratamento de envio incerto; pausa,
cancelamento e recuperacao end-to-end. Nao ha worker de admissao/triagem/card
ligado ao gateway; estas APIs sao componentes, nao uma fila operacional nova.

Nao habilitar processamento com base apenas nesta suite. O aceite final precisa
provar A lento/B rapido, dependencia por versao aprovada, falha de provedor,
queda antes/depois do envio e ausencia de entrega duplicada ou sem validacao.
