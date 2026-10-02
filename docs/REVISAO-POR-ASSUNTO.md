# Revisao por assunto e confianca da entrega

## Estado atual: somente jobs

Em 02/10/2026 o titular retirou a fila por assunto das conversas. Configuracao
ativa: `enabled=false`, `review_scope=cron_only`, `subject_review_v2=true`.
Mensagens diretas usam o fluxo nativo Hermes, sem triagem e sem revisao de
entrega. `/ultron`, `/thor`, `/pink` e demais comandos continuam selecionando
perfis persistentemente; `/perfil` informa o atual. Nenhuma permissao de
ferramenta foi ampliada. Registros antigos da fila ficam preservados, inativos.

Somente jobs nativos cron passam pela revisao descrita abaixo. Erro tecnico
do revisor permite entregar com confianca limitada. Nao foi criada outra fila
de execucao para jobs. Instalador: `agent/topic_queue/install_cron_only_review.py`.

Politica solicitada pelo titular em 02/10/2026: falha tecnica de um revisor
nao deve apagar a resposta pronta nem repetir as ferramentas executadas.

- O perfil escolhido continua sendo o autor. Revisores sao selecionados pelo
  pedido do assunto, nao automaticamente pelo autor e nem por numeros/datas.
- Tanos deixa de ser obrigatorio em toda conversa; entra quando ha auditoria.
- A selecao atual e local e conservadora, por termos explicitos do pedido.
  Nao e um classificador semantico treinado. Casos ambiguos ficam com o autor.
- Workers da fila adiam a revisao para a entrega final, evitando duas barreiras.
- HTTP 4xx/5xx, timeout e falha de conexao geram voto `unavailable`, nunca
  `approved`. A resposta e liberada com **Confianca limitada: revisao incompleta**
  e os nomes dos perfis indisponiveis. Nao ha porcentagem inventada.
- `completed` na entrega nativa significa entrega liberada; `approval_completed`
  permanece falso e `status=unvalidated`. Cada voto indisponivel fica incompleto.
- Reprovacao concreta (`revise`/`blocked`), prova invalida ou identidade divergente
  nao se transforma em aprovacao tecnica. Continua exigindo correcao.
- A regra e de entrega, nao de autorizacao de ferramentas. Nao libera compras,
  publicacoes, alteracao de medicacao, mudancas destrutivas ou repeticao de acoes.
- A chamada de revisao tem timeout de rede de 20 segundos. O tempo total ainda
  depende da geracao, ferramentas, fila e politica nativa do cliente auxiliar.
- Saudacoes completas incluindo o nome Ultron aceitam validacao local; saudacao
  misturada com pedido tecnico continua sendo tarefa.
- Texto e arquivos mantem recibos. Audio nao substitui a entrega documental.

Instalador local: `agent/topic_queue/install_subject_review.py`. Exige gateway
parado, verifica os hashes existentes, preserva backup privado e ativa
`subject_review_v2` no config privado da fila. Hermes e 9Router sao locais.
Nenhuma chave, perfil pessoal ou cookie faz parte deste repositorio.

As aprovacoes antigas mantem sua politica congelada. Nao se reenvia conteudo
com recibo confirmado ou envio incerto para aplicar a nova politica.
