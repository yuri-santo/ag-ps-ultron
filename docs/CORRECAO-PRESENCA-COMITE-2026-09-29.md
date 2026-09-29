# Correcao de presenca e comite do Ultron

## Incidente confirmado

Em 29/09, `ta ai ?` recebeu aviso de revisao pendente. Nao foi falha da
conexao de modelos: o revisor respondeu, mas interpretou a frase como outro
idioma e pediu nova redacao mesmo quando o candidato ja dizia estar presente.
Tambem recebeu evidencias de temas antigos porque `_db_persisted`/`_row_id`
faziam o filtro ignorar a mensagem atual.

## Correcoes instaladas localmente

- Presenca/saudacao isolada tem validacao deterministica e resposta canonica,
  com identificador e hashes. Texto arbitrario do modelo nao recebe aprovacao.
- Evidencias sao limitadas ao turno real, mantendo dados internos de persistencia
  como metadados, nao como sinal de mensagem sintetica.
- Anexos, pedidos mistos e chamadas de ferramenta exigem revisao substantiva;
  entrada longa nao vira saudacao por truncamento.
- Broker recebe contexto de idioma PT-BR sem impedir pedido explicito diferente.
- Finalizador persiste a resposta validada. Pareceres sinteticos e candidatos
  rejeitados nao viram mensagens comuns no historico novo.
- Worker do especialista deixa de devolver sucesso se `completed` nao for true,
  houver interrupcao ou revisao pendente. Permissoes e perfis preservados.

Nao foram apagadas mensagens antigas nem executadas acoes pessoais. A correcao
nao afirma resolver todas as causas de revisao pendente em tarefas substantivas.

## Comite configurado

O contrato de sistema `ultron_sdd` e a skill `conselho-sdd` foram atualizados:
Ultron lidera, decompoe por assunto, seleciona especialistas pertinentes,
coleta pareceres e decide com justificativa. Maioria nao supera requisitos
obrigatorios, dados ausentes ou autorizacao para executar.

Fluxo: triagem/completude -> escopos/dependencias -> requisitos -> investigacao
e pareceres -> deliberacao do Ultron -> revisao independente -> entrega.
Etapas dependentes esperam; independentes podem avancar conforme o executor.
Saudacoes nao convocam comite. Parecer favoravel nao autoriza gastos, publicacoes,
envios externos ou alteracoes de producao. Nenhum SOUL foi alterado nesta etapa.

Fontes reproduziveis:
- `agent/plugins/ultron_team/conselho_sdd.md`: contrato sempre carregado no root.
- `agent/skills/conselho-sdd/SKILL.md`: procedimento e cenarios.
- `agent/review/patch_worker_completion.py`: atualiza somente o contrato do worker
  vivo, sem sobrescrever o catalogo de perfis com uma copia publica antiga.

No ambiente atual, o plugin vivo ja registra `ultron_sdd` separadamente. O
repositorio publico passou a registrar essa secao tambem. A copia publica ainda
tem um catalogo de perfis menor; nao substitua o plugin vivo inteiro sem migrar
e validar esse catalogo. Instale a skill e o contrato nos caminhos equivalentes
do home local, com backup e conferindo o limite de 4000 caracteres da secao.

**Limite:** isto ativa o protocolo de raciocinio/delegacao no Hermes existente.
Nao implementa sozinho a fila duravel por assunto, o outbox nem barreiras
deterministicas para todas as etapas do comite. Essas integracoes continuam
pendentes conforme a especificacao da fila. Nao alegar comite end-to-end testado
em todos os dominios somente porque o prompt foi carregado.

## Verificacao e reversao

- 49 testes de revisao/patches, incluindo integracao isolada com Hermes, passaram.
- 7 testes do plugin, incluindo carregamento sem truncamento, passaram.
- Replay somente-leitura da mensagem do incidente no codigo instalado retornou
  `Tô aqui. O que manda?`, `approved`, `completed=true`, sem broker remoto.
- Registro real do plugin em contexto isolado confirmou contrato de 3831
  caracteres e 21 especialistas disponiveis. Nao executou esses especialistas.
- Simulacao textual dos cenarios de saudacao, orcamento desconhecido e SAP/agenda
  independentes foi revisada. Nao e teste operacional completo nem envio Telegram.

Backups Restic privados: `ed0fa44b` (`pre-presence-review-fix`) preserva gate,
broker, politica, finalizador e persistencia; `b6e021ae` (`pre-committee-contract`)
preserva contrato, skill e worker. Patches tambem mantem backups locais.

Para rollback, parar/drainar gateway, restaurar os arquivos afetados do snapshot
para staging, conferir diferencas e somente entao substituir os ativos. Nao
restaurar bancos antigos nem apagar historico para reverter arquivos de codigo.
Reiniciar gateway e verificar conexao Telegram. Nenhuma VPS participa.
