# Entrega nativa pendente

Atualizacao de 02/10/2026. Hermes e gateway rodam inteiramente locais.

## Incidente

Uma solicitacao com DOCX/XLSX entrou pelo fluxo nativo de documentos, nao pela
fila de mensagens simples. O texto final e quatro arquivos foram produzidos,
mas os revisores selecionados responderam HTTP 503. A recuperacao automatica
de midia nativa anexou somente o resultado do TTS a uma mensagem de pendencia.

O nome generico do combo foi classificado como todos os seus modelos possiveis,
excluindo revisores elegiveis para o modelo efetivamente usado. Agora o campo
`model` observado na resposta alimenta a identidade do produtor. Valores
desconhecidos continuam sujeitos a politica conservadora; nao ha aprovacao
automatica por falha do provedor.

## Correcao

- Pacote pendente e recuperado do ledger privado de revisao, com verificacao
  de identidade do turno, fingerprint e assinatura do candidato.
- Texto e documentos ficam na SQLite privada; arquivos possuem caminho,
  tamanho e SHA-256. Mudancas posteriores impedem o envio.
- Revisao pode tentar novamente ate tres vezes, sem repetir as ferramentas.
  Cada versao de pacote tem identidade propria de revisao.
- Apos aprovacao, partes do texto e cada documento recebem recibo individual.
  A conclusao depende de todos os itens obrigatorios.
- Audio nao participa da revisao e nao substitui nenhum item obrigatorio.
  O caminho nativo nao anexa audio automaticamente a uma resposta bloqueada.
- Envio ambiguo nao e repetido automaticamente. Bloqueio, necessidade de
  correcao e envio incerto geram um aviso de estado, com tentativa registrada.
- `/stop` e `/new` cancelam os pacotes pendentes do escopo autorizado.

## Limites explicitos

O mecanismo nao certifica a exatidao de documentos SAP por existencia ou hash.
Se a revisao encontrar lacunas de conteudo, o pacote permanece em
`needs_revision`. Nao se transforma rejeicao em aprovacao nem se inventa recibo.
Esta recuperacao cobre turnos nativos retidos pela revisao; nao substitui todo
o transporte nativo de anexos que ja tenham sido aprovados normalmente.

Formatos desta recuperacao: DOCX, XLSX, PDF, CSV, TXT, PPTX, PNG, JPG, JPEG e MP4,
ate 45 MB por arquivo, sob o diretorio do usuario do runtime, fora de caminhos
ocultos. Outros caminhos/formatos precisam de tratamento especifico.

## Aplicacao e testes

`agent/topic_queue/install_native_delivery.py` exige gateway parado, confere
checksums e guarda backups privados antes de aplicar hooks estreitos no Hermes.
O tick existente do gateway executa a entrega; nenhum daemon adicional.

Testes incluem pacote idempotente, alteracao de arquivo, captura de identidade,
revisor indisponivel, envio de todas as partes, recibos, cancelamento durante
revisao e aviso unico de bloqueio. Testes usam escopos e transportes isolados.
