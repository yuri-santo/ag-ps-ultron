# Autonomia contextual no Hermes local

O agendador nativo aceita um pre-script cuja ultima linha JSON pode conter
`wakeAgent: false`. O filtro roda antes do modelo e dos coletores; nao cria outro
agendador, nao faz polling de rede e nao muda horarios ou destinos existentes.

`interests.py` guarda interesses privados com escrita atomica e lock Linux.
Somente registros ativos, explicitos, nao expirados e completos acordam o job.
Shopping exige produto e orcamento/moeda ou pedido explicito de menor preco
verificado; viagem exige rota, datas e passageiros; trading exige objetivo,
instrumentos e risco para pesquisa informativa. Imoveis podem ser pesquisa sem
orcamento conhecido, sem afirmar capacidade de compra. Arquivo corrompido
bloqueia o wake e nao e sobrescrito. Dados pessoais nunca entram no Git.

`interest_manage.py list/upsert/close` fornece manutencao via terminal nativo.
Upsert recebe JSON em stdin e limita renovacoes a 90 dias. Inferencias podem
ser registradas como proposed, mas nao acordam jobs. A origem source_quote e
obrigatoria; a automacao ainda depende de o agente extrair fielmente o pedido.
Isso nao e uma garantia semantica nem autorizacao para transacoes.

`cron_interests.py` migra seis jobs existentes. `deploy_local.py --apply` exige
instalacao local com caminhos conhecidos, backup previo e nenhum claim ativo.
Jobs pausados continuam pausados na migracao. Na maquina do titular, o monitor
de imoveis foi reativado separadamente por pedido explicito, por pesquisa de
30 dias nas regioes ja configuradas. Outros interesses nao foram inventados.

`CONTEXT-POLICY.md` e registrado no plugin compartilhado: ferramentas por
intencao, fontes atuais, NotebookLM referencial, mensagens sem emojis, nomes
reais e autorizacao especifica para efeitos externos. Essas orientacoes nao
substituem validacao de codigo ou garantem que o modelo nunca falhe. Nao ha
deduplicacao transacional nova entre os dois jobs de promocao; o prompt exige
consultar o historico existente antes de entregar. Fila persistente por assunto
e outbox continuam trabalho separado, nao implementado por este modulo.

Testes: `python -m unittest discover -s agent/context -v` no Linux/WSL.
No runtime local, os quatro scripts passaram tambem pelo executor e parser
reais do cron. Sem interesses: wake false; imoveis com pedido valido: true.

## Sessao NotebookLM

`notebooklm_keepalive.py` e o payload sem modelo do job nativo existente,
mantendo 30 minutos. Usa o perfil default explicitamente, ignora auth JSON
herdado, nao copia cookies de outra maquina e nao registra saida do provedor.
Arquivo privado de saude usa lock, escrita atomica e modo 600. Sucesso regular
nao entrega mensagem; somente transicao de falha/recuperacao e notificada.
Tres testes cobrem silencio, permissoes, timeout e ausencia de segredos.
O Cookie Sync legado deve continuar desativado para nao sobrescrever o login.
