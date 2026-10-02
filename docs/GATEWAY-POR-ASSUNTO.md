# Gateway local por assunto

Atualizacao de 02/10/2026: [perfis persistentes](PERFIS-PERSISTENTES.md).
Ultron e o autor inicial, `/nome` seleciona um perfil ate nova escolha, `/perfil`
informa a selecao e `/perfis` lista os comandos. A triagem respeita o perfil
fixado na recepcao; o Cerebro deixou de ser o substituto da conversa geral.

Ativado em 01/10/2026 no DM autorizado: servico ativo, um escopo e 21 perfis.
Probe real com despachante nativo: dois cards concluidos, uma aprovacao, nenhum
envio Telegram. Entrega na conta real ainda nao exercitada por este teste.

## Escopo

Hermes, Ultron e 9Router rodam inteiramente no computador local Windows/WSL.
Este gateway nao depende da VPS Finaro. SOULs, contas, tokens, cookies, conversas
e bancos operacionais nao fazem parte deste repositorio publico.

A integracao usa o Kanban nativo do Hermes para claims, processos, limites por
perfil, capacidade de memoria e recuperacao. Nao instala outro bot, scheduler ou
Redis. A admissao e restrita ao DM autorizado do titular, vinculado ao bot,
usuario, conversa e thread. A chave local `topic-queue/config.json: enabled`
controla a entrada e a entrega sem editar personalidades.

## Caminho de uma mensagem

1. Autenticacao nativa antes do agrupamento de mensagens; ingresso duravel e
   idempotente por mensagem original.
2. Triagem semantica com contrato validado, trechos de origem, assunto, versao,
   especialista e dependencias. Numeros/datas/UIDs sozinhos nao autorizam SAP.
3. Despacho pelo Kanban para worker restrito do perfil real. Resultados de
   ferramentas e modelo efetivamente servido ficam ligados ao candidato.
4. Revisao do dominio e auditoria independente sobre as partes exatas da
   mensagem final. Reprovacao textual permite corrigir o texto sem repetir
   ferramentas. Falhas de revisao tem novas tentativas persistentes e limitadas.
5. Outbox aprovado com prefixo `Nome do agente: resposta`, sem emojis nem
   mensagens intermediarias de recebimento/revisor. Assuntos independentes
   saem por ordem de aprovacao; partes da mesma entrega nao se intercalam.
6. Recibo real do Telegram por parte. Resultado externo incerto nao e reenviado
   automaticamente. Falha local comprovada antes do envio pode ser retomada.

Versoes antigas, dependencias invalidadas e cancelamentos barram conclusao e
envio. `/stop` e `/new` invalidam o trabalho pendente do escopo, preservando o
comportamento nativo desses comandos. Continuações incluem contexto historico
das respostas aprovadas, sem trata-las como novas autorizacoes.

## Limites deliberados

- Nesta ativacao, somente texto simples entra na fila. Midia, mensagens
  encaminhadas/citacoes estruturadas, comandos, aprovacoes nativas e respostas
  a mensagens anteriores desconhecidas da fila seguem o caminho nativo.
- Nao ha elevacao das permissoes dos especialistas. Este fluxo nao autoriza
  automaticamente publicar, comprar, reservar ou alterar sistemas externos.
- A vitrine TikTok Shop permanece bloqueada pelo titular.
- Um timeout apos possivel acao externa estaciona o trabalho para investigacao;
  nao ha garantia de exactly-once em APIs externas sem idempotencia/recibo.
- Revisao independente exige modelo servido identificavel e diferente do
  produtor. Na verificacao real, Gemini produziu e NVIDIA Nemotron revisou.
  Rotas Qoder/OpenRouter testadas retornaram 503; uma rota Antigravity expirou;
  DeepSeek na NVIDIA retornou 410. Nao declarar todos os fallbacks funcionais.
- A fila nao entrega candidato sem aprovacao quando os revisores falham.
  Esgotadas as tentativas, o card fica bloqueado; nao e sucesso silencioso.

## Instalacao e operacao

O instalador e especifico para o runtime local auditado. `native_patch.py`
verifica hashes de cinco fontes nativas e recusa upstream desconhecido,
instalacao parcial ou alteracao concorrente. Reauditar antes de atualizar o
Hermes; nao copiar o patch cegamente para outra versao.

```sh
PY=/opt/hermes-agent-20260924/venv/bin/python
SRC=/mnt/c/Users/yurim/workspace/ag-ps-ultron-review-20260928/agent/topic_queue
$PY "$SRC/manage_gateway.py" status
$PY "$SRC/manage_gateway.py" disable
```

Para refresh do codigo, desabilitar a admissao, aguardar trabalhos ativos e
parar o servico. O watchdog local pode reinicia-lo: usar uma mascara temporaria
durante a manutencao e SEMPRE remove-la ao terminar.

```sh
systemctl mask --runtime --now hermes-gateway.service
systemctl reset-failed hermes-gateway.service
$PY "$SRC/manage_gateway.py" refresh
systemctl unmask --runtime hermes-gateway.service
systemctl start hermes-gateway.service
$PY "$SRC/manage_gateway.py" enable
```

Backup privado: `/root/ultron-local/maintenance/topic-gateway-20261001/`.
Inclui fontes originais, configuracao e politica anteriores; refresh registra
hashes instalados. Para reverter os hooks, executar `rollback-native` com o
servico parado no lugar de `refresh`, remover a mascara e reiniciar. O comando
recusa fontes alteradas desde a instalacao, preserva bancos/evidencias e nao
sobrescreve mudancas posteriores em config/politica. A admissao fica desligada.

## Verificacao

Testes usam contas sinteticas, homes e boards temporarios. `probe_pipeline.py`
exercita provedores reais sem enviar ao Telegram; `--native-dispatch` inclui o
despachante e subprocessos nativos. O home de diagnostico e privado.

```sh
NATIVE_SOURCE_ROOT=/root/ultron-local/maintenance/topic-gateway-20261001/backup/native \
PYTHONPATH=/opt/hermes-agent-20260924 "$PY" -m pytest "$SRC" -q
$PY "$SRC/probe_pipeline.py" --native-dispatch
```

Em 01/10/2026, regressao conjunta de audit/integrations/topic_queue/review/
meeting/video/phone: 434 testes e 163 subtestes aprovados, 7 pulados por ambiente
ou opt-in. Nenhuma publicacao, compra ou mensagem real foi criada pelos testes.
