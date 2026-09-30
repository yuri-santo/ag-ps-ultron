# Producao e revisao de videos

Este procedimento complementa AUTONOMIA.md, sem alterar personalidades, permissoes,
contas, horarios ou a regra de um trabalho de video por vez. Ultron coordena;
Money cuida do conteudo; especialistas existentes atuam somente no seu escopo.

## Acionamento pelo contexto

| Situacao | Acao automatica pertinente | Evidencia / limite |
|---|---|---|
| Horario TikTok ja configurado | `python3 /root/tools/tiktok/affiliate_autonomy.py tick` | Retomar campanha pendente ou criar cadeia nativa; nao e recibo de postagem |
| Pedido de produzir video | Ler `catalog` e `status` no mesmo CLI | Nao iniciar segundo trabalho nem produto excluido |
| Dados de oferta incompletos | Pesquisa autorizada com fontes e data | Login ausente pede autenticacao do titular; nao inventar preco, estoque ou desconto |
| Cenas geradas | Validar arquivos, hashes e checkpoints existentes | Canvas ou job submetido nao significa MP4 pronto |
| Montagem | `affiliate_autonomy.py render --brief CAMINHO` | Render atual exige preflight; versao antiga nao recebe aprovacao retroativa |
| Revisao de MP4 avulso | `python3 /root/tools/tiktok/media_preflight.py VIDEO --output RELATORIO` | Somente evidencia tecnica; nao autoriza publicar |
| Pendencia de publicacao | Ler reserva e recibos; reconciliar | Nunca reenviar para descobrir se a primeira tentativa funcionou |
| Post confirmado, comentario pendente | Retomar somente comentario | Nao regenerar/republicar video |

Cron dispara o trabalho nos horarios existentes. Nao chamar todos os jobs ou
todas as ferramentas a cada mensagem. Conversa casual nao executa pesquisa,
geracao, publicacao ou agendamento. Nao usar `auto_tiktok_publicador_loop.py`
ou `tiktok_uploader.py` como atalho da cadeia revisada.

## Antes de gerar

Defina publico, produto exato, fato demonstravel, gancho, sequencia e encerramento.
Cada cena precisa de acao ou demonstracao que ajude a entender o produto, nao
apenas uma imagem com excesso de texto. Quando houver apenas fotos, declare
montagem de fotos: nao chamar isso de cenas generativas ou demonstracao real.
Nao converter automaticamente material estatico em prova de funcionamento.

O roteiro deve soar natural em pt-BR e conservar a voz do agente. Corte frases
genericas, superlativos vazios e falsa urgencia. Nao substituir por estatisticas
inventadas. Preco, desconto, frete, certificacao, comparacao e promessa de
resultado precisam de evidencia atual e pertinente. A revisao editorial nao
muda SOULs nem permite inventar fatos. Suplementos exigem especial cuidado com
afirmacoes de saude; o anuncio nao e consulta ou prescricao.

## Montagem e avaliacao

Use tempos reais de palavras para as legendas e respeite a area segura da
plataforma. O renderer existente aplica entrada/saida de audio de 30 ms por
trecho para reduzir estalos e mantem normalizacao de volume. Nao cortar a
ultima palavra, acelerar fala para caber ou cobrir o produto com legendas.

O preflight verifica formato vertical, audio, duracao e decodificacao integral.
Ele sinaliza preto, silencio e congelamento para inspecao; esses sinais nao
provam sozinhos defeito ou aprovacao. Um plano parado pode ser intencional,
mas nao satisfaz um pedido de demonstracao em movimento.

Inspecione inicio, fim, cada cena e ambos os lados das transicoes no MP4 FINAL.
Confira identidade do produto, texto legivel, fala, sincronismo e continuidade.
Uma contact sheet ajuda a localizar problemas; nao substitui ouvir o audio ou
ver movimento. Registre o que realmente foi examinado e o hash do arquivo.

`technical_pass=true` nao significa `visual_approval` nem aprovacao comercial.
O broker recebe os avisos e o hash do relatorio de preflight; a revisao visual,
ASR e autorizacao existentes continuam necessarias. Falha tecnica ou evidencia
alterada bloqueia a entrega. Corrigir em nova revisao preservando a anterior.

## Ferramentas externas

video-use inspira timeline textual, inspecao em cortes e fades. Seus helpers
de transcricao usam ElevenLabs; nao enviar midia privada nem contratar servico
quando a transcricao local atende. no-ai-slop inspira revisao editorial, nao
um detector confiavel de autoria. SkillSpector deve rodar isolado ao incorporar
skills novas/alteradas: scan estatico primeiro; nao enviar perfis ou segredos
a um LLM. Nao instalar outro harness, distro ou emulador para gerar um video.
