# Validacao da continuacao

Esta entrega complementa [a validacao anterior](VALIDACAO-2026-09-28.md).

## Resultados executados

| Escopo | Resultado |
|---|---|
| Desktop: `src/main/hermes.test.ts` | 9 testes passaram; prazo de STT teve teste vermelho antes da correcao. |
| Desktop: `lat check` | Passou. |
| Desktop instalado | STT pelo IPC retornou a frase do audio de teste; TTS concluiu a reproducao. |
| Reprocessador offline | 18 testes passaram. |
| Diarizacao | 8 testes passaram. |
| Qualidade de entrega PDF/DOCX | 6 testes passaram. |
| Dashboard publico | 7 testes passaram, incluindo autenticacao, origem, concorrencia, rollback e todas as rotas renderizadas. |
| Navegador | Desktop 1440x1000 e celular 390x844; telas sem overflow e sem pageerrors. |
| Interacao | Zoom do mapa mudou; grafico de cenarios atualizou ao alterar aporte em ambos os tamanhos, com pixels nao uniformes. |

O ambiente financeiro foi instalado separadamente, com Python 3.14 e Dash
3.4.0. O DataTable emite aviso de deprecacao futura; a faixa publicada limita
Dash a versao principal 3. Nao foi migrado o dashboard privado em producao.

## Qualidade da transcricao

O processamento real usou small local/CPU/int8, tres threads, sem download.
Processou 3 de 95 arquivos elegiveis, 60 segundos centrais de audio, sem falhas
de execucao. O tempo total foi cerca de 306 segundos sob a carga desta maquina.
Os candidatos contêm erros aparentes e nao foram aprovados ou inseridos no
relatorio. Nao ha WER/CER sem referencia humana; nao afirmamos melhoria de
acuracia com base apenas em pontuacoes internas do modelo.

O relatorio revisado anterior permanece completo, com sua transcricao. A
segunda passagem e opt-in e produz material de revisao, nao substituicao cega.

## Escopo da revisao

Fontes financeiras foram selecionadas e adaptadas sem copiar DB, credenciais,
dados de saude, clientes ou imagens pessoais. A busca de padroes sensiveis nos
arquivos novos nao encontrou ocorrencias; isso nao equivale a auditoria de
seguranca exaustiva. A revisao independente final dos subagentes foi interrompida
por limite de uso; verificacao final e testes foram realizados pelo orquestrador.

Nenhum SOUL, conta de anuncio, permissao social, publicacao ou gasto foi
alterado. Marketingskills e os catalogos foram avaliados; nao foram instalados
automaticamente nem receberam credenciais.
