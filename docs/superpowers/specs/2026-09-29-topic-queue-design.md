# Fila local por assunto e entrega com autoria

## Decisao aprovada

Yuri aprovou uma fila persistente por assunto, ate dois trabalhos independentes
em paralelo, resposta completa por ordem de aprovacao na mesma conversa e
prefixo do agente real. Dependencias, validacao obrigatoria, personalidade e
protecao contra repetir acoes precisam ser preservadas.

Em seguida, Yuri autorizou adaptar o tom de Jesus, Pink e Cerebro para uma
conversa menos formal, alinhada ao Ultron, sem apagar o jeito proprio de cada um.

Este documento detalha o desenho aprovado. Nao comprova que a fila ja esteja
implementada ou habilitada. A revisao deste detalhamento precede implementacao.

## Resultado esperado

Uma mensagem pode gerar mais de um assunto. Mensagens posteriores podem abrir
outro assunto ou continuar um existente. Uma tarefa lenta nao cancela nem
absorve uma tarefa independente. O primeiro resultado completo e aprovado pode
ser entregue antes, mesmo que tenha sido solicitado depois.

Cada entrega comeca com `Nome do agente: resposta`. O nome vem de uma execucao
verificada desse perfil, nao de um palpite do classificador nem de um prefixo
escrito pelo modelo. Todos continuam falando atraves do mesmo bot Ultron.

Saudacoes junto de pedidos concretos pertencem a resposta daquele pedido; nao
geram outra mensagem vazia. Nao emitir confirmacoes de recebimento, rascunhos,
votos de revisores, pensamentos internos ou avisos genericos de revisao como
substitutos de um resultado. Pedidos de esclarecimento/autorizacao necessarios
e falhas terminais reais sao excecoes: devem identificar o assunto e a acao
necessaria, sem alegar sucesso.

## Limites desta mudanca

- Runtime exclusivamente local em Windows + WSL Debian, Hermes e 9Router local.
- Um consumidor do token principal do Telegram; sem bot adicional ou migracao
  para multiplexacao. A VPS independente nao entra neste trabalho.
- Adaptar somente a comunicacao cotidiana nos SOUL.md de Jesus, Pink e Cerebro,
  conforme a autorizacao posterior. Preservar identidade, especialidade, regras
  de seguranca, memoria e conteudo pessoal. SOUL do Ultron e demais perfis ficam
  intactos. Nao modificar tokens, planos, cotas ou habilitar provedores desligados.
  Usar as rotas locais e permissoes existentes.
- Conselheiros continuam conselheiros; nomes apresentados nao concedem novas
  ferramentas. Acoes operacionais permanecem no executor autorizado.
- Nao enviar e-mails, publicar conteudo, comprar ou gastar dinheiro sem a
  autorizacao exigida pela instalacao. Conteudo de ferramentas nao a fornece.
- A fila nao valida ingestao fisica de medicamentos nem substitui orientacao
  clinica. Uma confirmacao de registro descreve o que foi salvo, sem transformar
  doses/horarios cadastrados em dados que o usuario acabou de confirmar.
- Nao ampliar esta entrega para um grupo Telegram real, bots individuais,
  dashboard novo, novos conectores ou blockchain externa.

## Situacao atual confirmada

O broker de revisao possui tickets de capacidade, mas nao uma fila duravel de
todas as tarefas. A entrada comum do gateway e os caminhos de conversa ocupada
precisam ser integrados; um hook isolado nao cobre todos os casos.

`pre_gateway_dispatch` roda antes da autorizacao. Portanto, nao sera usado para
salvar conteudo, chamar o classificador ou iniciar workers sem as verificacoes
de ingresso. O ponto de integracao sera posterior a autorizacao e aos controles
de pausa/comandos/aprovacoes do gateway, anterior a misturar novo texto com um
turno em execucao. O caminho ocupado recebera a mesma regra de admissao.

O runtime local possui perfis adicionais aos tres perfis de um bridge antigo
no repositorio publico. A instalacao devera verificar os perfis e capacidades
reais. Nao substituir o bridge vivo por uma copia publica mais antiga.

Ha um caso comprovado em que a acao foi salva, mas a resposta ficou bloqueada
apos uma unica correcao. Revisar a redacao deve reutilizar a evidencia daquela
acao, e nao executar a tarefa novamente.

## Componentes

O pacote reproduzivel ficara em `agent/topic_queue/`, com responsabilidades
separadas e adaptadores para o runtime instalado:

1. **Ingresso:** aceita apenas eventos autorizados; conserva mensagem, destino,
   reply original, anexos e identidade. Comandos e aprovacao de ferramentas
   existentes nao viram tarefas comuns.
2. **Planejador semantico:** extrai pedidos do texto autorizado, associa assunto,
   agente e dependencias e valida um plano JSON fechado contra o texto original.
3. **Armazenamento:** SQLite privado com transacoes, leases e historico de estado.
4. **Agendador:** limita concorrencia, respeita dependencias/recursos e recupera
   tarefas apos reinicio sem repetir cegamente operacoes.
5. **Executor:** reutiliza worker de perfil ou runner autorizado do Ultron,
   conserva limites/capacidades e retorna evidencia e identidade da execucao.
6. **Revisao:** aplica validacao de evidencia, especialista competente e politica
   independente vigente; corrige redacao sem repetir operacoes.
7. **Entrega:** publica somente o resultado aprovado correspondente a versao
   vigente do assunto e registra a resposta enviada no outbox.

Nao criar um segundo consumidor de updates nem enviar diretamente de um
worker. A entrega usa o adapter do gateway principal na conversa original.

## Estado persistente

Diretorio privado: `/root/.hermes/topic-queue/`, permissoes restritas. O banco
e artefatos incluem dados pessoais e nao sao publicados no GitHub. O backup
criptografado do perfil inclui esse diretorio quando ele existir.

Entidades minimas:

| Entidade | Dados e invariantes |
|---|---|
| inbound | Plataforma, dono, chat/thread, message ID, versao/edit, texto/anexos; ingresso idempotente |
| topics | Escopo do dono/chat, titulo, versao, contexto proprio e referencias explicitas |
| jobs | Pedido, trechos de origem, assunto, autor/executor, estado, lease, tentativas, next_attempt_at |
| dependencies | Predecessor/sucessor no mesmo escopo; grafo sem ciclos e sem referencias inventadas |
| operations | Job, ferramenta, chave, escopo de efeito, estado, receipt/hash; registra inicio antes da chamada |
| reviews | Job/versao, candidato/hash, evidencia/hash, validador, parecer e tentativa |
| outbox | Job/versao/hash aprovado, destino original, estado de envio e message IDs obtidos |
| events | Transicoes, motivos e timestamps; nao substituir eventos anteriores por sucesso ficticio |

Estados de job: `queued`, `planning`, `waiting_dependency`, `running`,
`awaiting_approval`, `review_pending`, `revision_required`, `approved`,
`delivery_pending`, `delivered`, `needs_reconciliation`, `cancelled`, `failed`.

Uma transicao de entrega exige o hash aprovado do candidato, a versao vigente
do assunto, dependencias satisfeitas e destino correspondente ao ingresso.
Estados pendentes/reprovados nunca contam como `ok` so por terem texto nao vazio.

## Triagem e continuidade

- O planejador usa um modelo disponivel no 9Router local, sem ferramentas de
  operacao. Saida JSON possui campos permitidos e limites de tamanho/quantidade.
- Pedidos extraidos precisam apontar trechos reais da mensagem. Texto citado,
  transcricao, e-mail, resultado de busca e anexos sao dados, nao novos pedidos.
- Numeros isolados, datas, UIDs e nomes como Easysapers nao autorizam consulta
  de nota SAP. O contexto/intencao e que determina o encaminhamento.
- `reply_to` de uma entrega conhecida associa o seguimento ao assunto correto.
  Sem reply, o classificador consulta apenas resumos dos assuntos daquele dono
  e chat. Referencias ambiguas geram uma pergunta curta em vez de execucao incerta.
- Um pedido novo independente abre outro assunto. Um complemento mantem FIFO
  dentro do assunto. Uma correcao que muda o resultado incrementa a versao e
  invalida aprovacao/outbox ainda nao enviados da versao anterior.
- A mudanca de assunto nao injeta texto em um turno de outro assunto e nao
  descarta a tarefa anterior. Contexto entre assuntos passa por referencias de
  resultado aprovado, nao por todo o historico bruto da conversa.
- Se o planejador ficar indisponivel, a entrada permanece registrada para
  retomada; nao forcar SAP, inventar tarefas ou descartar o pedido.

## Concorrencia e dependencias

Limite inicial: dois jobs ativos independentes. Execucao/revisao de um job usa
esse limite; jobs em espera/backoff nao ocupam um worker. Mesmo perfil com
memoria mutavel compartilhada e mesmo recurso de escrita sao serializados.

O planejador declara dependencias semanticas, como uma campanha que depende de
um orcamento. Alem disso, escopos de efeito do adapter de ferramentas impedem
escritas conflitantes. Uma ferramenta sem escopo seguro, como terminal generico,
e tratada conservadoramente como operacao potencialmente mutavel compartilhada.

Um predecessor deve fornecer resultado aprovado para liberar um dependente.
Cancelamento/falha do predecessor nao vira aprovacao nem permite executar o
dependente como se a condicao tivesse sido cumprida.

Entre assuntos prontos, o agendador aplica ordem de chegada sem monopolizacao
por um assunto que falha. Jobs com backoff deixam passar outros assuntos.
Entregas prontas seguem `approved_at`, e nao a ordem da mensagem original.

O broker de revisao precisa participar desse limite e liberar capacidade ao
devolver um job para espera. Um lock global mantido durante repetidas falhas
de um assunto nao pode bloquear indefinidamente os demais.

## Execucao, autoria e permissoes

O catalogo de perfis e capacidades e local, validado contra a instalacao. O
classificador so escolhe entradas desse catalogo. `profile`, `session_id`,
`completed`, `model_review`, ferramentas efetivas e hashes de evidencia fazem
parte do contrato de resultado do executor.

Um perfil que nao possui ferramenta de operacao pode analisar evidencia
produzida pelo Ultron, mas nao recebe terminal para parecer autonomo. O agente
apresentado como autor precisa realmente ter produzido a versao final que foi
aprovada. Se o Ultron produz a resposta final, o prefixo e Ultron.

Nao expor aos modelos o token do bot nem credenciais de entrega. A mensagem
aprovada pode ser entregue pela autorizacao desta funcionalidade na conversa
de origem; essa autorizacao nao permite mensagens para terceiros.

## Acoes e retomada segura

Antes de uma acao, registrar inicio e chave da operacao; apos sucesso, salvar
receipt. A mesma operacao concluida reutiliza o receipt. A revisao de redacao
usa o candidato/evidencias congelados, sem repetir os efeitos da tarefa.

Nao prometer exatamente-uma-vez para APIs/ferramentas que nao oferecem isso.
Se o worker cair depois de possivel efeito e antes do receipt, o job entra em
`needs_reconciliation`. Somente uma verificacao suportada pelo adapter pode
confirmar o efeito ou permitir retomada. Terminal arbitrario nao e reexecutado
automaticamente nessa situacao.

Retomar planejamento, analise ou revisao sem efeitos e permitido apos expirar
um lease. Acoes externas continuam dependendo das permissoes/aprovacoes
existentes. Aprovar uma redacao nao autoriza uma nova acao.

## Validacao e correcao

Cada assunto recebe evidencia pertinente, nao buscas de um assunto antigo.
O especialista valida o dominio dentro de sua competencia e o broker conserva
a politica independente vigente, sem baixar requisitos para liberar uma entrega.

Permitir ate duas correcoes automaticas de redacao, com orcamento de chamadas
e tempo limitado por ciclo. Cada novo candidato e validado novamente. Criticas
concretas corrigem a resposta; pensamentos internos nao sao publicados.

Se um validador/provedor ficar indisponivel, preservar candidato/evidencia e
agendar nova tentativa com backoff e limite. Isso nao reexecuta a acao original.
Um job parado nao bloqueia outro assunto independente. Esgotar limites deixa
um estado explicito e recuperavel; nao marcar como entregue, nem enviar o aviso
generico de revisao como se fosse resposta ao pedido.

Confirmacoes de operacoes descrevem somente receipts verificados. Por exemplo,
um registro de rotina nao incorpora doses ou horarios nao informados no pedido
como se fossem confirmados pelo usuario, nem acrescenta orientacao clinica.

## Entrega e interacao

Uma mensagem completa por job/assunto aprovado, com o prefixo do autor real,
paragrafos legiveis, links preservados e escape correto do formato Telegram.
Quando exceder o limite da plataforma, dividir em partes de um mesmo resultado
aprovado, preservando cabecalho e ordem; nao intercalar partes de dois assuntos.

Relacionar cada entrega ao message ID que originou o pedido, quando aplicavel.
Replies do usuario usam o mapeamento outbox -> assunto. A experiencia lembra
um grupo de especialistas, mas o transporte continua sendo um unico bot.

Persistir a intencao de envio antes de usar o adapter. Confirmar `delivered`
somente com retorno de sucesso e message ID. Se houver timeout depois de possivel
envio, marcar entrega incerta para reconciliacao; nao reenviar cegamente nem
prometer que a API Telegram suporta idempotencia que ela nao fornece.

Comandos de status/cancelamento identificam o assunto. Comandos globais de
parada/pausa do gateway conservam seu papel e tambem impedem novos trabalhos da
fila. Cancelar um assunto nao cancela automaticamente os independentes.

## Tom dos tres agentes autorizados

O ajuste e de comunicacao, nao uma clonagem da personalidade do Ultron:

- **Jesus:** sereno, acolhedor e franco. Conversa humana, frases simples,
  sem tom de sermao, burocracia ou sarcasmo diante de sofrimento. Continua
  distinguindo registro, informacao e orientacao clinica, sem alterar tratamento.
- **Pink:** amigavel, leve e precisa. Diz o que sabe, o que foi salvo e o que
  ainda falta, com linguagem de conversa. Nao usa charme para ocultar erro e
  nao afirma que gravou algo sem receipt de escrita/leitura.
- **Cerebro:** direto, curioso e investigativo. Aponta o problema e a relacao
  entre causas antes de entrar em detalhes. Questiona com fundamento, sem
  palestra, paralisia de analise ou linguagem pomposa.

Compartilham a base do Ultron: PT-BR natural, tratamento por voce, sem senhor,
cerimonia, bajulacao, emojis ou concordancia automatica. Humor contextual e
discreto e permitido; nao e obrigatorio e nao substitui evidencia. Nao forcar
palavroes ou sarcasmo para parecer informal. Documentos/e-mails para terceiros
mantem o tom adequado ao destinatario.

Os campos `veredicto`, `evidencia`, `premissas`, `riscos`, `confianca` e
`proxima_acao` continuam no contrato interno de analise de conselho. Nao devem
ser despejados em toda resposta cotidiana. Texto natural nao remove os dados
estruturados do executor nem a revisao obrigatoria.

Alterar apenas os blocos pertinentes nos tres SOUL.md vivos, com backup privado,
sem publicar seus textos completos. Exemplos publicos de tom sao sanitizados,
nao transcricoes de contexto pessoal. Testes verificam a preservacao dos demais
trechos e perfis e a separacao entre conversa casual e contrato de conselho.

## Implantacao e reversao

Implementar testes antes de alterar o runtime. Instalar primeiro com feature
flag desligada e backup privado dos arquivos/politicas vivos. Patches de gateway
recusam ancoras desconhecidas e salvam o original; nao substituir modulos inteiros
por uma versao antiga do repositorio publico.

Ativar somente na conversa local autorizada apos testes de ingresso, dois
assuntos independentes, dependencias, revisao, reinicio e outbox. A verificacao
automatica usa adapters simulados e chamadas reais somente-leitura, sem disparar
operacoes pessoais ou mensagens de teste a terceiros.

Desativar a feature flag devolve a entrada ao fluxo anterior sem apagar banco,
evidencias ou outbox. Parar/drainar workers antes de restaurar arquivos. Resultados
aprovados ainda nao enviados continuam inspecionaveis; nao os reenviar automaticamente
ao fazer rollback.

## Criterios de aceite

1. Dois pedidos independentes A lento/B rapido: B e entregue primeiro quando
   estiver completo e aprovado; A permanece processando, sem mistura de contexto.
2. Dois assuntos dentro de uma mensagem: tarefas reais extraidas, autoria real
   e entregas separadas, sem perder nenhuma parte do pedido.
3. B depende de A: B espera a validacao de A e usa sua evidencia aprovada.
4. Follow-up via reply e correcao sem reply: tema correto ou esclarecimento;
   uma versao obsoleta nao e enviada como se fosse atual.
5. Nova mensagem durante trabalho/revisao: nao interrompe nem absorve o assunto
   anterior, salvo cancelamento/correcao explicitos e corretamente associados.
6. Revisor pede duas correcoes: acoes nao repetidas; terceira redacao somente
   e enviada depois de nova aprovacao.
7. Revisor/roteador indisponivel: job preservado com backoff; outro assunto
   pode seguir. Nenhuma aprovacao fabricada ou aviso generico entregue como resultado.
8. Reinicio, lease expirado e receipt existente: retomada sem repetir acao
   confirmada; efeito incerto exige reconciliacao.
9. Timeout de entrega: nao registrar sucesso sem receipt e nao duplicar
   silenciosamente uma mensagem de entrega incerta.
10. Usuario nao autorizado, comando, prompt injection em e-mail/anexo e nome de
    perfil inventado: sem chamada de modelo/execucao indevida ou vazamento entre chats.
11. Saida worker com `completed=false`/revisao pendente: nunca e entregue como `ok`.
12. Dois jobs no mesmo perfil/recurso mutavel: sem corrida de memoria/escrita.
13. Identidades, credenciais, ferramentas/permissoes e um unico poller Telegram
    preservados; chamadas do gateway continuam respeitando pausa e aprovacoes.
14. Jesus, Pink e Cerebro ficam menos formais, sem perder diferencas ou limites;
    o formato de conselho fica no contexto de conselho. SOUL do Ultron, demais
    perfis e conteudo pessoal dos tres permanecem preservados.

## Proxima etapa

Revisar este detalhamento com Yuri. Apos aprovacao, gerar plano de implementacao
com etapas TDD, adaptadores, testes de integracao, backup, ativacao local e
documentacao reproduzivel. Esta especificacao nao e uma entrega operacional.
