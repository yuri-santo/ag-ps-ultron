# Perfis persistentes do Ultron

Implementado em 02/10/2026 no Hermes local Windows/WSL. O perfil principal
mantem seu diretorio, configuracao, memoria e SOUL. O identificador interno
continua `default`; o nome de exibicao nativo agora e **Ultron**.

| Comando | Comportamento |
| --- | --- |
| `/ultron` | Seleciona Ultron ate outra escolha explicita |
| `/pink` | Seleciona Pink para a conversa |
| `/cerebro explique esta ideia` | Seleciona Cerebro e encaminha a pergunta |
| `/cris`, `/greg`, `/harvey` etc. | Seleciona o respectivo perfil instalado |
| `/perfil` ou `/profile` | Informa o perfil selecionado |
| `/perfis` | Lista os perfis e seus comandos |

Sem selecao anterior, a conversa inicia no Ultron. A escolha persiste por bot,
usuario, conversa e topico, inclusive apos reinicio do gateway. Os aliases
`/default`, `/celebro`, `/creg` e `/pinky` sao aceitos. Comandos enderecados a
outro bot nao alteram a selecao. Rotas nativas explicitas mantem precedencia.

Cada ingresso guarda o perfil escolhido: trocar de perfil nao reatribui pedidos
ja recebidos. Comandos atrasados nao desfazem uma escolha mais recente. A
triagem divide assuntos, mas nao escolhe outro autor. Ultron pode consultar
especialistas pelas ferramentas de orquestracao existentes; ele continua
responsavel por sua propria resposta. Um perfil indisponivel nao e substituido
silenciosamente pelo Cerebro.

Ultron executa no home principal e usa as ferramentas ja configuradas para o
Telegram. Kanban e entrega de mensagens permanecem sob responsabilidade do
gateway. Especialistas conservam os limites de seus workers. Revisao do
dominio, auditoria, contratos por versao e recibos do outbox permanecem ativos.

## Voz dos perfis

Ultron preserva a alma existente e ganha orientacao Jarvis: preciso, proativo,
ironia seca ocasional e conversa natural. Pink e Cerebro ganham vozes distintas
inspiradas no desenho. Cris e Greg usam humor cotidiano inspirado nos
personagens de Todo Mundo Odeia o Chris, conservando seus dominios de email.
Documentos profissionais e respostas sensiveis continuam proporcionais ao
contexto. Os 22 perfis recebem bordoes curtos ou marcas de fala autorais,
opcionais e contextuais, sem repeticao obrigatoria. As frases autorais nao sao
apresentadas como citacoes famosas.

As novas secoes foram adicionadas aos SOULs privados preservando seu conteudo.
O formato de parecer foi limitado aos pareceres, para evitar que uma saudacao
vire um relatorio de auditoria. Nenhum SOUL pessoal e publicado neste Git.

## Instalacao e verificacao

`agent/topic_queue/install_profiles.py` valida os hashes da instalacao anterior,
prepara as mudancas e, com `--apply` e gateway parado, grava um backup privado
de todos os arquivos alterados. A previa sem `--apply` nao escreve arquivos.
O manifesto registra hashes anteriores/posteriores. O script e especifico ao
runtime local auditado; nao e um instalador generico do Hermes.

Backup inicial desta alteracao:
`/root/ultron-local/maintenance/profile-commands-20261002T093643Z/`.
Reaplicacoes criam novos backups datados. Para reverter, parar o gateway,
verificar que cada arquivo ainda corresponde ao hash `after` e restaurar seu
conteudo de `before/`, preservando mudancas posteriores e os bancos privados.
O backup de outubro de 1 continua contendo as fontes nativas originais.

`probe_profiles.py --telegram-menu` consulta o estado e o menu real sem enviar
mensagens. Todos os 22 comandos de perfil, `/perfil` e `/perfis` foram
confirmados no menu privado do bot. Probe com provedor real e despachante nativo
concluiu dois cards e uma aprovacao do Ultron, sem envio ao Telegram.

Regressao de topic_queue/review: 323 testes aprovados, um pulado e 50 subtestes.
Testes incluem comandos autorizados/negados, persistencia apos reconstruir o
store, isolamento por origem, pedidos antigos, aliases, precedencia nativa e
execucao do Ultron no home principal. Confirmacao de comando e deterministica;
respostas geradas continuam passando pelo comite.
