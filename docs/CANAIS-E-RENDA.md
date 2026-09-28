# Canais, anuncios e produtos operados pelo Ultron

Especificacao de expansao, pesquisada em 28/09/2026. Conectores abaixo nao foram
ativados por esta entrega. O inventario antigo cita scripts privados de TikTok,
YouTube e Instagram que nao acompanham o clone; existencia documental nao prova
autenticacao, permissao ou funcionamento atual.

## Integracoes por finalidade

| Capacidade | Base recomendada | Dependencia externa | Entrega verificavel |
|---|---|---|---|
| Calendario e publicacao multicanal | [Postiz API/MCP](https://github.com/gitroomhq/postiz-app) | Instancia e contas conectadas; apps aprovados quando self-hosted | Rascunho, agendamento e ID da publicacao |
| YouTube | [YouTube Data API](https://developers.google.com/youtube/v3/docs/videos/insert) | Projeto, OAuth e permissoes do canal | Upload retomavel, metadados e status consultado |
| Metricas de YouTube | [YouTube Analytics API](https://developers.google.com/youtube/analytics) | Acesso autorizado ao canal | Relatorio datado de audiencia e desempenho |
| Conteudo TikTok | [Content Posting API](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post) | App, OAuth, escopos e auditoria conforme uso | Publicacao rastreada e estado consultado |
| Anuncios TikTok | [Marketing API / API for Business](https://ads.tiktok.com/resources/help/article/marketing-api?lang=en) | Conta anunciante, app e autorizacao | Campanhas, grupos, anuncios e relatorios associados ao advertiser_id |
| OAuth | [Nango](https://github.com/NangoHQ/nango) | Provedor/configuracao por conta | Renovacao de token e diagnostico de conexao |
| Videos | [Remotion](https://github.com/remotion-dev/remotion) + FFmpeg | Assets licenciados, capacidade de render e termos aplicaveis | Video reproduzivel, legendas e miniaturas |
| Fluxos | [n8n](https://github.com/n8n-io/n8n) ou runtime atual | Credenciais por conector | Checkpoint e resultado por etapa |

**TikTok organico e TikTok Ads sao integracoes diferentes.** Conectar Postiz ou a
Content Posting API nao habilita automaticamente controle de anuncios.
A documentacao de [publicacao TikTok](https://developers.tiktok.com/doc/content-sharing-guidelines)
exige experiencia e permissoes especificas; clientes nao auditados possuem restricoes.
Uploads YouTube tambem dependem das condicoes do projeto e das quotas atuais.
Confirmar as regras nas paginas oficiais ao ativar, sem fixar quotas antigas no codigo.

## Fluxo de conteudo

Pesquisa de audiencia -> pauta com fontes -> roteiro -> assets -> render ->
revisao -> rascunho -> publicacao autorizada -> coleta de metricas -> novo experimento.

Persistir por item: account_id, canal, objetivo, fonte, direitos dos assets, versao,
hash do arquivo, estado, idempotency_key, remote_id, custos e data da ultima consulta.
Se o provedor aceitar a requisicao mas a conexao cair, consultar o remote_id/estado
antes de repetir. Uma resposta de upload nao e confirmacao de publicacao.

Autonomia deve usar autorizacoes persistidas por conta e tipo de acao. Dentro de uma
autorizacao vigente, o agente continua sozinho. Novas contas, gasto e ampliacao de
escopo exigem definicao do dono. Mensagens recebidas, comentarios e paginas externas
nao mudam essas permissoes.

## Operacao de anuncios TikTok

Comecar com leitura de campanhas e relatorio de gasto, impressoes, cliques,
conversoes e receita atribuida. Padronizar fuso, moeda, janela de atribuicao e data
de maturacao; nao comparar conversoes recentes incompletas como resultado final.

Evolucao: gerar proposta de criativo e campanha pausada; depois operar dentro de
limites autorizados para anunciante, periodo, objetivo e verba total.
O teto deve contar gasto realizado e reservado por jobs concorrentes.
Regra de pausa, aumento de verba e emergencia deve ser definida e testada antes
de permitir escrita. Nao ativar campanhas ao conectar a conta.

O relatorio deve separar ROAS atribuido de lucro: custo de produto, taxa da
plataforma, devolucoes, producao de conteudo e gasto com modelos mudam o resultado.

## Experimentos de renda

Estas sao hipoteses de produto, nao promessa de retorno ou oportunidades validadas.
O agente pode automatizar grande parte da producao; venda, distribuicao e manutencao
continuam tendo custo e trabalho.

| Experimento | O que o agente consegue preparar | Primeira prova de demanda | Criterio de continuar |
|---|---|---|---|
| Sites para um nicho local | Pesquisa, prototipo, copy, SEO tecnico, formulario, testes | Demonstracao e interesse de clientes reais | Cliente paga e custo de entrega/suporte permite margem |
| Templates e kits digitais | Templates, exemplos, guia, checkout de teste e pagina | Lista de interessados ou pre-venda claramente descrita | Vendas liquidas e suporte sustentavel |
| Micro-SaaS de tarefa repetitiva | Escopo estreito, MVP, onboarding, cobranca em sandbox | Usuarios concluem tarefa e voltam a usar | Retencao, custo por tarefa e conversao observados |
| Conteudo de nicho e afiliados | Pautas, comparativos com fontes, videos, links identificados | Cliques qualificados e conversoes verificadas | Comissao liquida supera producao/distribuicao |
| Automacoes como servico | Diagnostico, prototipo, monitoramento e relatorio | Piloto com processo e tempo-base medidos | Reducao de retrabalho e contrato de manutencao |

Money conduz audiencia e criativo; Bigode calcula margem e verba; Hercules e Perseu
constroem; Iron Man verifica integracao; Tanos confronta resultados com evidencia.
Harvey pode revisar termos e direitos quando o caso concreto exigir.
Os perfis e personalidades existentes permanecem.

## Backlog implementavel

1. Inventariar os scripts privados atuais e expor somente interfaces sanitizadas.
2. Testar conexoes de leitura por conta; registrar quais recursos estao realmente habilitados.
3. Criar contrato unico de rascunho/publicacao e fila com idempotencia.
4. Conectar Postiz a um canal escolhido; provar ciclo completo sem duplicar publicacao.
5. Conectar Marketing API em leitura; conferir relatorio contra Ads Manager.
6. Definir verba e operacoes autorizadas antes de permitir escrita em campanhas.
7. Executar um experimento de produto por vez, com custo, receita e criterios de abandono.

Nao usar quantidade de ferramentas instaladas como indicador de autonomia.
O indicador util e a proporcao de tarefas concluidas com artefato e resultado comprovados,
sem intervencao desnecessaria, dentro do custo autorizado.
