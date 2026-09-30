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

## Testes

```bash
python -m unittest discover -s agent/tests -p 'test_render_report.py' -v
python -m unittest discover -s agent/tests -p 'test_meeting_delivery_quality.py' -v
python -m unittest discover -s agent/tests -p 'test_import_transcriptonic.py' -v
python -m unittest discover -s agent/stt -p 'test_diarizar.py' -v
```
