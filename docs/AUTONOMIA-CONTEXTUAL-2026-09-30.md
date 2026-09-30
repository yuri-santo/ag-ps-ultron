# Entrega local de 30/09/2026

## Aplicado

- [Filtro de interesses](../agent/context/README.md) nos seis jobs nativos de
  promocoes, viagens, trading e imoveis. Mantidos horarios/destinos; saude,
  agenda, backups e producoes autorizadas nao foram alterados.
- Imoveis retomados como pesquisa informativa nas regioes existentes, sem
  inferir orcamento ou elegibilidade. Interesse com prazo de 30 dias.
- Politica contextual compartilhada, sem mudar SOULs, orienta ferramentas,
  fontes, NotebookLM, nomes reais e entregas sem emojis. Gateway recarregado
  depois de verificar ausencia de reuniao e claim de cron em andamento.
- [Identidade do produto](../agent/video/PRODUCT-IDENTITY.md): guard de envio
  exige manifesto, referencias e inspecoes por cena vinculadas aos hashes.
  Broker recebe os mesmos artefatos. Metadados nao comprovam verdade visual.
- [Reunioes](../agent/meeting/README.md): TXT integral anexado ao e-mail e
  caracteres literais preservados no PDF. Nenhum e-mail real enviado em testes.
- [PhoneHarness](../agent/phone/README.md) fixado e isolado, ajuda/testes sem
  rede. Android autorizado via USB; nenhum proxy/ADB TCP aberto.

## Verificacao

50 testes de video passaram, incluindo render FFmpeg sintetico real; 8 testes
de interesses; 14 testes de relatorios (3 novos e 11 de regressao); teste SMTP
com mock, verificando PDF/TXT/Word. Pagina de transcricao renderizada e inspecionada.
PhoneHarness: 11 testes upstream offline e 6 testes do launcher. Nao houve
publicacao, compra, reserva, mudanca de SOUL ou acesso a VPS.

## Autenticacao Restabelecida

Depois desta entrega, o login interativo nativo autenticou o NotebookLM local:
auth check --test retornou status ok e token_fetch true; list --json funcionou.
O CLI esta no PATH. O job existente Auth Keepalive foi corrigido para o caminho
local atual e script nativo sem modelo, mantendo intervalo de 30 minutos.
Sucesso normal e silencioso; falha e recuperacao notificam apenas transicoes.
O antigo Cookie Sync continua desativado, para nao sobrescrever a sessao valida.

Cookies Seller fornecidos pelo titular foram verificados por consulta real e
instalados privadamente. Catalogo local atualizado com 100 oportunidades, sem
publicar ou alterar vitrine. Sessao de publicacao do criador foi preservada.
Credenciais e conteudo dos cadernos nao foram incluidos no Git.

## Limites Pendentes

- NotebookLM agora autenticado; adicionar livros exige arquivos/fontes
  indicados pelo titular. Ingestao e referencia, nao treino do modelo.
- PhoneHarness upstream referencia helpers ADB ausentes e proxy sem auth.
  Instalacao nao equivale a controle autonomo do Android; somente ADB USB foi
  validado. A configuracao do Deck no aparelho ainda nao foi alterada.
- Seller ja permite coleta autenticada, mas alteracao da vitrine ainda exige
  identificacao da conta/fluxo correto, SKUs, elegibilidade e recibos. Esta
  entrega nao atualizou a vitrine nem publicou.
- Novos videos sem evidencias reais serao bloqueados; preencher um manifesto
  ficticio nao substitui visao, escuta e verificacao comercial.
- Nao foi medida nova precisao ASR com audio real. A auditoria identificou que
  o runtime pode registrar fim do processamento como fim da captura; essa
  correcao de lifecycle ainda nao foi aplicada nesta etapa.
- Fila persistente por assunto/outbox e garantia deterministica de ausencia de
  emojis em todos os caminhos nao foram implementadas por estas politicas.

Backup privado antes das alteracoes: snapshots Restic `d38f499a` e `38f461c1`.
Restaurar arquivos em staging e comparar, nao sobrescrever o banco de estado.
