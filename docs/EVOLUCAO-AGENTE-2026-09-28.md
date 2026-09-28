# Evolucao do Ultron: reunioes, raciocinio e execucao

Pesquisa verificada em 28/09/2026 por GitHub CLI autenticado e documentacao oficial.
Estrelas sao uma fotografia da consulta, nao uma medida de qualidade.
Este documento descreve recomendacoes de engenharia; nao significa que os projetos estejam instalados.
Nenhuma alteracao de SOUL, personalidade ou perfis faz parte desta entrega.

## Diagnostico da entrega de reuniao

A amostra privada foi examinada localmente e nao integra este repositorio.
Ela antepunha referencias de chamados ao resultado da conversa, colocava IDs extensos
na tabela de acoes, reproduzia compromissos como fragmentos de fala e reportava
15 registros/blocos rejeitados. O organizador do convite era tratado como presidente,
sem confirmacao. O encerramento tambem tinha uma formula que pressupunha consenso.

No runtime examinado, o prompt de consolidacao exige copia literal das falas.
Isso protege a evidencia, mas nao produz, sozinho, uma sintese narrativa.
Uma rejeicao pode ser erro de formato, citacao ou falha de bloco; o PDF anterior
atribuia todas a falta de citacao. Alterar so o modelo ou a cor do PDF nao resolve isso.

## O que mudou no codigo

- PDF e Word abrem com um resumo dos registros confirmados e indicadores de qualidade.
- Referencias curtas F001, F002 etc. possuem indice com o ID original e aparecem na transcricao.
- Referencias de sistemas externos ficam ao final, separadas das falas.
- Organizador, presidencia e presenca sao conceitos separados; ausencia de dado nao vira afirmacao.
- Linhas extensas da transcricao deixam de ser cortadas silenciosamente em 6.000 caracteres.
- A diarizacao recorta segmentos na fronteira de cada arquivo e acumula evidencia por falante.
  Cobertura temporal insuficiente ou voz ambigua permanece sem rotulo.
- Um importador offline aceita o webhook advanced do Transcriptonic.
- Caminhos quebrados dos instaladores foram corrigidos e ganharam testes com a arvore publicada.

O resumo atual e extrativo: organiza registros existentes, mas nao reescreve a conversa
inteira nem recupera compromissos rejeitados. Nao ha comprovacao de qualidade equivalente
ao Notion. Os testes usam dados sinteticos; precisao acustica exige audio e referencia revisada.

## Referencia de produto: Notion

A [documentacao oficial](https://www.notion.com/help/ai-meeting-notes) descreve resumo,
itens de acao, citacoes navegaveis, instrucoes por tipo de reuniao e contexto do calendario.
O app desktop captura microfone e audio do sistema; navegador tem limitacoes.
Na consulta, a ajuda restringia rotulos de falantes ao ingles e alertava sobre grupos.
Portanto, a meta para PT-BR deve ser demonstrada em testes locais, sem presumir que
um produto de referencia identifique todos corretamente.

Meta de experiencia: abrir a reuniao, entender o resultado, localizar a fala de apoio,
revisar um responsavel e transformar um compromisso em tarefa rastreavel.

## Os dois projetos sugeridos

| Projeto | Consulta | O que aproveitar | Limites observados |
|---|---|---|---|
| [Transcriptonic](https://github.com/vivek-nexus/transcriptonic) | 229 estrelas; MIT | Legendas da plataforma, nomes exibidos, recuperacao local, webhook advanced | Nao e motor ASR; depende da legenda e do DOM; Teams/Zoom anunciados como beta |
| [Meetily](https://github.com/Zackriya-Solutions/meetily) | 31.208 estrelas; MIT na comunidade | Captura mic+sistema, processamento local, importacao e reprocessamento, separacao captura/sumario | README mistura comunidade e Pro; diarizacao e exports avancados precisam de verificacao por edicao/release |

**Decisao:** manter o Hermes como agente e os perfis atuais. Aproveitar o Transcriptonic
como fonte adicional e estudar o Meetily como referencia de captura/recuperacao.
Substituir o runtime por outro app duplicaria sessao, memoria e distribuicao.
O importador presente aqui foi escrito independentemente a partir do contrato publico.

O [README do Meetily](https://github.com/Zackriya-Solutions/meetily#meetily-pro)
descreve o Pro como outra base de codigo. A descricao geral do repositorio menciona
diarizacao, enquanto a secao Pro ainda contem disponibilidade futura.
Essa divergencia impede afirmar que clonar a edicao MIT entrega todos os recursos.
Usar provedor de resumo na nuvem tambem muda o caminho dos dados.

## Catalogo priorizado

| Projeto oficial | Estrelas | Licenca indicada pelo GitHub | Aplicacao proposta |
|---|---:|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 25.616 | MIT | Baseline local de transcricao; comparar modelo, VAD e vocabulario de dominio |
| [WhisperX](https://github.com/m-bain/whisperX) | 24.290 | BSD-2-Clause | Segunda passagem com alinhamento por palavra e diarizacao; medir RAM/GPU e PT-BR |
| [pyannote.audio](https://github.com/pyannote/pyannote-audio) | 10.598 | MIT | Comparar separacao de falantes; modelos tem termos e requisitos proprios |
| [Minutes](https://github.com/silverstein/minutes) | 1.514 | MIT | Referencia recente de memoria de conversas em Markdown, CLI e MCP |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 42.424 | MIT | Fluxos longos com checkpoints e retomada; manter fluxos pequenos no SQLite existente |
| [Graphiti](https://github.com/getzep/graphiti) | 31.277 | Apache-2.0 | Relacoes e validade temporal de fatos por projeto |
| [Mem0](https://github.com/mem0ai/mem0) | 66.237 | Apache-2.0 | Alternativa para memoria; comparar com a memoria atual antes de adicionar outra |
| [Langfuse](https://github.com/langfuse/langfuse) | 35.149 | Other/mista | Rastrear chamadas, custo, latencia e avaliacoes; conferir componentes/licencas |
| [promptfoo](https://github.com/promptfoo/promptfoo) | 25.537 | MIT | Regressao de qualidade de prompts, recuperacao e respostas |
| [Postiz](https://github.com/gitroomhq/postiz-app) | 36.444 | AGPL-3.0 | Calendario editorial, agendamento, API/MCP e analise dos canais |
| [n8n](https://github.com/n8n-io/n8n) | 206.220 | Other/fair-code | Orquestrar conectores e rotinas; verificar termos antes de distribuir como produto |
| [Nango](https://github.com/NangoHQ/nango) | 12.400 | Other/mista | OAuth e conectores; investigar o Nango ja descrito no homelab |
| [Remotion](https://github.com/remotion-dev/remotion) | 60.935 | Other/propria | Videos parametrizados e variantes; conferir condicoes comerciais |
| [browser-use](https://github.com/browser-use/browser-use) | 116.623 | MIT | Automacao de navegador quando nao existir API adequada |

Nao foi feita auditoria integral desses projetos. Licenca de codigo nao implica
licenca dos modelos, direitos de conteudo ou acesso liberado a APIs.
WhisperX documenta limitacoes com fala sobreposta e diarizacao; benchmarks publicados
nao sao previsao de desempenho no notebook do Ultron.

## Raciocinio sem alterar personalidade

O ganho deve entrar em ferramentas, contratos e memoria, preservando SOUL.md:

1. Formular objetivo, criterio de entrega e contexto profissional/pessoal.
2. Resolver cliente/projeto antes de recuperar fontes.
3. Recuperar evidencias com data, origem e trecho; distinguir fatos atuais de revogados.
4. Escolher ferramentas pelo contrato: entrada, permissao, efeito, timeout e custo.
5. Executar por etapas persistidas, com chave de idempotencia e retomada.
6. Revisar as alegacoes decisivas; chamar especialistas quando houver divergencia material.
7. Verificar o artefato ou efeito real e registrar a evidencia.
8. Entregar resultado, pendencias e proxima acao; atualizar memoria apenas com fatos sustentados.

Evitar convocar todos os especialistas em toda pergunta: isso aumenta custo e latencia,
sem garantir melhores respostas. O conselho deve concentrar-se nas decisoes relevantes.
Primeiro instrumentar o runtime existente; adotar LangGraph so para fluxos cuja retomada
e ramificacao justifiquem a dependencia.

Contrato desejado de resultado:

```json
{
  "status": "complete|partial|blocked",
  "artifact_paths": [],
  "evidence": [{"source_id": "F001", "claim": "afirmacao verificavel"}],
  "unverified": [],
  "next_action": null,
  "cost": {"measured": false}
}
```

Isso e uma especificacao futura, nao um endpoint ja registrado no Hermes.

## Transcricao e reuniao: etapas seguintes

| Etapa | Implementacao proposta | Criterio de aceite |
|---|---|---|
| Captura | Mic e loopback separados; medir saturacao, silencio, perda de chunks e eco | Manifesto de audio com intervalos e falhas explicitadas |
| Primeira passagem | Modelo aquecido para latencia; legenda como fonte independente | Horarios estaveis e original preservado |
| Segunda passagem | Reprocessar trechos ruins com WhisperX/faster-whisper; glossario SAP por projeto | WER e acerto de siglas medidos em corpus PT-BR revisado |
| Falantes | Diarizacao temporal e nomes apenas quando confirmados | DER/atribuicao avaliados; sobreposicao nao vira identidade certa |
| Consolidacao | Evidencia literal separada de sintese por tema; recuperar falas adjacentes | Cada decisao/acao tem apoio; negacao, correcao e responsavel ausente testados |
| Relatorio | Visao geral, assuntos, decisoes, tarefas, pendencias e referencias navegaveis | Usuario encontra a fala e corrige a tarefa sem procurar IDs tecnicos |
| Memoria | Decisoes com validade temporal e links entre reunioes | Revogacao substitui estado atual sem apagar historico |
| Execucao | Tarefa derivada da reuniao entra em fila, respeitando autorizacao persistida | Reexecucao nao duplica tarefa, publicacao ou cobranca |

Para comparar configuracoes: mesmo audio, transcricao humana, mesmos canais e hardware.
Separar WER, acerto de termos tecnicos, atribuicao de falantes, precisao de acoes,
recall de compromissos, latencia p50/p95, custo e intervencoes humanas.
Nao trocar o ASR em producao baseado em uma unica frase de teste.

## Dominios pessoal e profissional

Manter escopos separados por pessoa, conta, cliente e projeto. A mesma personalidade
pode operar ambos; a recuperacao nao deve misturar prontuario, financas e reunioes de cliente.
Prioridades por especialista existente: Maquiavel/Dona nas reunioes; Cerebro/Pink na
memoria; Hercules/Perseu/Iron Man na implementacao; Tanos nas provas; Money/Bigode
em conteudo e viabilidade. Nenhum novo personagem e necessario.

Leia [operacao de canais e renda](CANAIS-E-RENDA.md) e
[reproducao do sistema](RECRIAR-ULTRON.md).
