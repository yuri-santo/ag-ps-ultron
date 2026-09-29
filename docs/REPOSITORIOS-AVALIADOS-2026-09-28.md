# Repositorios avaliados

Consulta autenticada ao GitHub em 2026-09-28. Popularidade nao substitui
revisao de codigo, licenca, manutencao ou teste no hardware local.
Nenhuma destas referencias concede acesso a contas ou autoriza gastos.

## Links sugeridos pelo usuario

| Projeto | Decisao para o Ultron | Limite |
|---|---|---|
| [marketingskills](https://github.com/coreyhaines31/marketingskills) | Dez skills adaptadas e instaladas apenas no Money; [pacote e instalador](../agent/marketing/README.md). | MIT; sem ferramentas, parceiros, credenciais nem mudanca da personalidade. |
| [public-apis](https://github.com/public-apis/public-apis) | Catalogo para descobrir provedores por tarefa. | Lista, nao conector. Conferir API oficial, precos, quota, termos e tratamento de dados de cada candidato. A licenca da lista nao licencia as APIs. |
| [awesome](https://github.com/sindresorhus/awesome) | Indice para pesquisa tecnica sob demanda. | Nao carregar a lista inteira no prompt nem instalar seus links automaticamente. |
| [Flowise](https://github.com/FlowiseAI/Flowise) | Apenas referencia de editor visual e composicao de fluxos. | O README e o campo `isArchived` do GitHub indicavam arquivamento nesta consulta. Nao adicionar como dependencia central nova; licencas de componentes tambem precisam de revisao. |
| [coreyhaines31](https://github.com/coreyhaines31/coreyhaines31) | Perfil do autor, util para descobrir projetos. | E um README de perfil, nao uma ferramenta executavel. |

O snapshot de marketingskills examinado foi
`5b2c0007766c6a1cf1d53fd8fc73e979e0821022`. O skill `ads` presume
acesso direto a contas: essa premissa **nao** vale para o Ultron. Seus
benchmarks e regras de orcamento precisam de verificacao contextual, nao de
execucao literal. O catalogo tambem inclui integracoes patrocinadas declaradas.

### Aplicacao proposta sem mudar personalidade

1. Money prepara briefing, publico, oferta, criativos e plano de medicao.
2. Bigode verifica custos e margem; Harvey revisa riscos quando aplicavel.
3. Tanos exige evidencias, distingue hipotese de resultado e revisa a entrega.
4. Ultron apresenta rascunhos. Publicar, enviar mensagens, conectar contas,
   alterar campanhas ou gastar exige autorizacao explicita e escopo definido.

Pacote instalado: `product-marketing`, `customer-research`, `copywriting`,
`content-strategy`, `social`, `seo-audit`, `ad-creative`, `ads`, `analytics`,
`ab-testing`. A instalacao foi verificada com `hermes --profile money skills list`;
o perfil Bigode nao recebeu essas skills.
Nao existe garantia de renda passiva: medir receita recebida, custos, margem,
tempo humano e cancelamentos por experimento antes de escalar.

## Transcricao e CPU Intel

| Projeto | Utilidade | Decisao |
|---|---|---|
| [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) | Contexto e estabilizacao de resultados em streaming. | Inspiracao para continuidade; benchmarks de GPU/idiomas diferentes nao comprovam ganho neste notebook. |
| [WhisperLive](https://github.com/collabora/WhisperLive) | Streaming com faster-whisper e opcao OpenVINO. | Candidato a experimento isolado; revisar limites de duracao de sessao. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | ASR local e aceleracao de encoder com OpenVINO. | Comparar CPU Intel com o mesmo audio PT-BR antes de migrar. |
| [OpenVINO GenAI](https://github.com/openvinotoolkit/openvino.genai) | Pipeline ASR em CPU/GPU Intel. | Alternativa experimental, nao backend instalado. |
| [Silero VAD](https://github.com/snakers4/silero-vad) | Deteccao de fala. | Ja utilizado pelo faster-whisper; evitar uma segunda camada redundante. |
| [stable-ts](https://github.com/jianfch/stable-ts) | Refinamento temporal. | Estava arquivado nesta consulta; nao tornar dependencia central. |

Meetily e Transcriptonic continuam documentados em
[EVOLUCAO-AGENTE](EVOLUCAO-AGENTE-2026-09-28.md). Legenda importada,
ASR local e identificacao de falante devem conservar sua procedencia.

## Evidencia local e proximo criterio de qualidade

A amostra privada possui 586 arquivos de audio; 95 contêm ao menos uma fala
marcada com baixa confianca. Nao foram detectados arquivos com clipping pelo
limiar do diagnostico. Isso nao comprova inteligibilidade nem completude.
Tres arquivos foram comparados com o mesmo modelo small, com e sem dois
segundos de contexto contiguo: os textos mudaram de forma mista. Pontuacao
interna maior nao prova texto correto. Nenhum candidato substituiu o original.

O [reprocessador offline](../agent/stt/README.md) registra candidatos e permite
retomada. Antes de promover um backend, criar referencia humana de trechos
representativos e medir WER/CER, nomes/termos tecnicos, tempos, falantes,
latencia e memoria. O relatorio deve conservar a transcricao completa,
tempos, origem e incertezas; resumo nao pode preencher lacunas do audio.
