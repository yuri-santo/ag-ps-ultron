# Admissao duravel por assunto

**Fundacao offline; nao instalada no gateway.** Este modulo nao altera o
Telegram, nao chama modelos, nao executa ferramentas e nao envia mensagens.
Segue o [desenho aprovado](../../docs/superpowers/specs/2026-09-29-topic-queue-design.md).

## Implementado

- Ingresso SQLite idempotente por plataforma, conta, dono, chat, thread e mensagem.
- Commit sincrono antes de confirmar admissao; reinicio conserva pendencias.
- Proposta de triagem com schema fechado, perfis permitidos e cobertura do texto.
- Trechos de pedido delimitados pelo adapter confiavel, nunca pelo modelo.
- Versoes por assunto, dependencias sem ciclos e invalidacao dos descendentes.
- Intencoes de cards com correlacao estavel, sem criar outro scheduler.
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

Em 01/10/2026: 33 testes aprovados em Python 3.11/WSL, incluindo 40 ingressos
seguidos de encerramento abrupto do processo, duplicatas concorrentes, schema
invalido, referencias entre chats, cobertura incompleta e versao obsoleta.
`unittest discover` nao executa estes testes: eles usam pytest.

## Ainda Nao Implementado

Adapter pos-autorizacao e anterior ao FIFO ocupado; triagem pelo cliente auxiliar;
reconciliacao das intencoes com cards Kanban; veto pre-transicao; manifestos de
aprovacao; outbox por parte; recibos reais e tratamento de envio incerto; pausa,
cancelamento e recuperacao end-to-end. `card_intents()` retorna deliberadamente
`released=False` e `native_card_id=None`.

Nao habilitar processamento com base apenas nesta suite. O aceite final precisa
provar A lento/B rapido, dependencia por versao aprovada, falha de provedor,
queda antes/depois do envio e ausencia de entrega duplicada ou sem validacao.
