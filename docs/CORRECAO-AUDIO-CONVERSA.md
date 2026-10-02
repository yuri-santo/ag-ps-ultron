# Audio separado da resposta

Correção de 02/10/2026 no gateway local.

## Causa

O plugin de voz anexava `MEDIA:` depois da revisão do texto. O worker comparava
a assinatura do texto revisado com o resultado contendo o anexo, rejeitava a
prova e deixava a tarefa bloqueada. As duas mensagens investigadas tinham
respostas aprovadas: não era indisponibilidade do Telegram ou do modelo.

## Comportamento

- Workers da fila usam `ULTRON_HOST_HANDLES_SPEECH=1`, já suportado pelo plugin
  local, para impedir a transformação posterior do texto.
- O texto conserva as revisões e seu envio com recibo.
- O áudio opcional usa o TTS configurado e o `speech_plan` existente, somente
  depois da confirmação do envio do texto. Não passa por revisão de modelo.
- Geração e upload rodam em segundo plano. Falha do áudio não muda o resultado
  da resposta em texto e não exige que o usuário repita sua pergunta.
- `host_speech` registra uma tentativa por resposta. Uma tentativa ambígua ou
  interrompida não é reenviada automaticamente, evitando áudio duplicado.
- Pedidos de somente texto e a configuração `voice_enabled` são respeitados.
- Os únicos controles do anexo são técnicos: destino, arquivo dentro do cache,
  tamanho, estado da conversa e recibo do Telegram. Não há comitê para áudio.

## Aplicação

`agent/topic_queue/install_speech_fix.py` atualiza quatro módulos, verifica as
assinaturas instaladas e mantém backup privado. Exige gateway parado. Em
instalações novas, o instalador de perfis também inclui o módulo de áudio.

As duas respostas retidas foram recuperadas dos registros privados de revisão,
comparando sessão, pedido, assinatura e chamadas de ferramentas. Nenhuma
ferramenta foi repetida. Depois passaram pela revisão final e pelo envio normal
da fila. Foram confirmados dois recibos de texto e dois de áudio no Telegram.
Credenciais, conteúdo privado e banco de sessões não entram no repositório.

## Testes

Testes cobrem preservação do texto nos workers, liberação do áudio somente após
o texto, falha isolada do TTS, recibo separado e proteção contra repetição. Foi
exercitado também o worker com o perfil principal real, plugins habilitados e
revisão aprovada, além das entregas reais recuperadas.
