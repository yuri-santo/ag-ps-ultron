# Verificacao da entrega de reunioes

## Resultado

43 testes focados passaram: 6 de qualidade da entrega, 5 de regressao do
renderizador, 11 do importador Transcriptonic, 8 de diarizacao, 2 de caminhos
de instalacao, 3 do instalador Team e 8 do instalador Lab.

Os testes Lab foram executados no WSL/Linux, que implementa as permissoes POSIX
esperadas. Na primeira tentativa Windows, o teste de modo 0600 encontrou 0666.
As demais suites foram verificadas no Windows. Nao foi executada a suite completa
de todos os plugins, painel ou integrações externas.

Comandos na raiz do clone (Python com as dependencias de relatorio e PyYAML):

```bash
python -m unittest discover -s agent/tests -p 'test_meeting_delivery_quality.py' -v
python -m unittest discover -s agent/tests -p 'test_render_report.py' -v
python -m unittest discover -s agent/tests -p 'test_import_transcriptonic.py' -v
python -m unittest discover -s agent/stt -p 'test_diarizar.py' -v
python -m unittest discover -s agent/tests -p 'test_deploy_paths.py' -v
PYTHONPATH=agent python -m unittest discover -s agent/tests -p 'test_install.py' -v
PYTHONPATH=agent python -m unittest discover -s agent/tests -p 'test_lab_install.py' -v
```

As duas ultimas formas de definir PYTHONPATH sao para Linux/WSL.

## Instalacao verificada

Na instalacao existente, foram atualizados somente os renderizadores PDF/DOCX
do meeting_copilot e o script de diarizacao. Houve backup, verificacao de hashes
antes da escrita e renderizacao do payload real depois da copia.
Os 22 arquivos SOUL examinados permaneceram com os mesmos hashes.
O runtime chama esses scripts em subprocessos, dispensando reiniciar o gateway.

O relatorio privado foi regenerado em PDF e DOCX, e sua primeira pagina foi
inspecionada visualmente. Um PDF de leitura rapida contem as duas paginas iniciais;
o documento completo preserva transcricao e indice. Dados e documentos reais
nao foram adicionados ao GitHub. Nao houve envio por Telegram ou e-mail.

## Limites

- Regenerar o relatorio reaproveita a transcricao e os registros existentes.
  Nao recupera o conteudo rejeitado nem melhora retroativamente o reconhecimento.
- O resumo e extrativo, sem nova sintese semantica por temas.
- A correcao temporal da diarizacao foi testada com intervalos sinteticos.
  Nao foi medido ganho acustico/DER em uma reuniao real.
- O importador e offline, sem webhook HTTP ou extensao instalada automaticamente.
- A nova documentacao de canais e renda e um plano de integracao, nao operacao
  ativa de contas, anuncios ou monetizacao.
- A reproducao completa em maquina nova continua dependendo dos componentes
  listados em RECRIAR-ULTRON.md.
