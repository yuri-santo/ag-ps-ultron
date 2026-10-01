# Relatorios e entrada de legendas

Os renderizadores aceitam o report-input.json do copiloto instalado.
Tambem funcionam isoladamente com Python e as dependencias de
`../requirements-report.txt`. Nao alteram personalidade, nao chamam modelos
e nao enviam documentos.

## Demonstracao offline

Execute na raiz do repositorio, usando um diretorio de saida ainda inexistente
ou nomes de arquivo novos:

```bash
python agent/meeting/import_transcriptonic.py agent/meeting/examples/transcriptonic.json --output meeting.json
python agent/meeting/render_report.py meeting.json ata.pdf
python agent/meeting/render_docx.py meeting.json ata.docx
```

O exemplo e sintetico. A ausencia de decisoes e esperada: importar legendas nao
equivale a analisar e confirmar compromissos.

## Transcriptonic

Contrato estudado em
[extension/background-script/index.js](https://github.com/vivek-nexus/transcriptonic/blob/main/extension/background-script/index.js)
e nos utilitarios do projeto. Use JSON capturado do webhook **advanced**:
`meetingSoftware`, `meetingTitle`, `meetingStartTimestamp`,
`meetingEndTimestamp`, `transcript[{personName,timestamp,transcriptText}]`.

O importador rejeita exportacao simples/TXT e timestamps sem fuso ou ambiguos,
mantem o payload original, separa chat e nao sobrescreve a saida.
Os nomes sao rotulos exibidos pela plataforma, nao identidade verificada.
Os horarios representam captura das legendas, nao alinhamento preciso com audio.
Nenhum endpoint de webhook ou extensao de navegador e instalado automaticamente.

## Entrega

A transcricao integral no PDF preserva caracteres literais (`#`, `**`, crases
e marcadores), sem interpreta-los como Markdown. `patch_transcript_email.py`
adiciona o TXT existente aos anexos do envio nativo, mantendo PDF e Word.
Teste de integridade em `test_report_integrity.py`; teste SMTP simulado local
confirmou os tres anexos sem enviar mensagem real. Estas correcoes nao
retranscrevem gravacoes antigas nem medem nova precisao do reconhecimento.

PDF e Word usam o mesmo `build_minutes`: resumo extrativo inicial, qualidade,
decisoes, encaminhamentos, pendencias, transcricao e indice de referencias.
O ID completo continua no indice; a tabela usa F001 etc.
Organizador do convite nao implica presidencia. Presenca exige registro.
Campo opcional `chair` so deve vir de confirmacao externa explicita.

Registros confirmados sao recebidos do consolidador; o renderer nao valida
semanticamente cada compromisso. Citar uma fala nao prova, por si so, a interpretacao.
Para payloads antigos sem eventos, referencias apontam ao indice de IDs,
mas nao existe correspondencia navegavel garantida com a transcricao textual.

O resumo continua baseado em trechos literais. Uma futura sintese por tema deve
manter evidencias separadas e passar por avaliacao em PT-BR.
Consulte [o plano de evolucao](../../docs/EVOLUCAO-AGENTE-2026-09-28.md).

## Horario de encerramento

`patch_capture_stop.py` fornece `transform_capture(source)` para o
`capture_agent.py` e `transform_runtime(source)` para o `runtime.py` instalado.
Sao transformacoes puras, com validacao de sintaxe, idempotencia e rejeicao de
layout desconhecido: nao alteram instalacoes, nao reiniciam captura e nao leem
dados de reunioes. As duas migracoes foram aplicadas no ambiente local em
01/10/2026, junto deste `render_report.py` (tambem usado pelo Word), apos backup
criptografado e testes. Em outra instalacao, revisar os fontes e aplicar ambas;
nao basta substituir somente o renderizador.

O timestamp novo mede o fechamento dos dois streams no Windows, antes da
persistencia final e da transcricao. Nao afirma o fim real da reuniao. Quando um
stream falha ou nao confirma o fechamento, o fim fica desconhecido. Eventos
reproduzidos nao substituem o fim atual, e uma nova captura limpa o fim anterior.

Agentes antigos emitem `stopped` depois de processar a fila de ASR. Esse horario
fica explicitamente estimado pelo aviso de parada, sem confirmar o fim real e
sem tratar o aviso como limite superior garantido. Payloads antigos sem origem
recebem aviso de origem nao verificada; `ended_at` explicitamente desconhecido
nao recorre ao horario de geracao do documento. Nenhum registro original,
transcricao ou payload historico e regravado por estas funcoes.

Exemplo para produzir uma copia candidata sem sobrescrever o original:

```python
from pathlib import Path
from patch_capture_stop import transform_runtime

original = Path('/caminho/para/runtime.py')
candidate = Path('/diretorio-de-revisao/runtime.py')
updated = transform_runtime(original.read_bytes().decode('utf-8'))
with candidate.open('xb') as stream:
    stream.write(updated.encode('utf-8'))
```

Teste isolado: `python -m unittest discover -s agent/meeting -p test_capture_stop.py -v`.
Para validar tambem os fontes instalados, somente leitura, defina
`MEETING_RUNTIME_SOURCE` e `MEETING_CAPTURE_SOURCE` para os caminhos desses
arquivos. A cobertura executa os metodos de ingestao/finalizacao com registros
sinteticos, interrompendo antes de subprocessos e entrega; nao abre microfones,
nao transcreve audio real e nao envia documentos.

## Testes

```bash
python -m unittest discover -s agent/tests -p 'test_render_report.py' -v
python -m unittest discover -s agent/tests -p 'test_meeting_delivery_quality.py' -v
python -m unittest discover -s agent/tests -p 'test_import_transcriptonic.py' -v
python -m unittest discover -s agent/stt -p 'test_diarizar.py' -v
```
