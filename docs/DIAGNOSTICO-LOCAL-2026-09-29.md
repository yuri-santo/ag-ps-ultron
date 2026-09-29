# Diagnostico local do Telegram e 9Router

## Limite operacional

Hermes, Ultron, perfis, gateway e 9Router desta instalacao sao exclusivamente
locais. A VPS citada em documentacao historica nao integra esse runtime.
Nao usar esse servidor para diagnosticar, atualizar ou reiniciar o bot.

## Causas confirmadas

- Um bot SAP legado no Windows fazia polling com o mesmo token do gateway
  Hermes. Seu aviso sobre OpenRouter vinha de outro cliente de IA, nao da
  cadeia de fallback do Hermes.
- A triagem do bot antigo combinava numeros de 4 a 8 digitos com a substring
  sap: Easysapers, datas e UIDs de e-mail podiam virar consultas de notas.
- O detector de fraude considerava fonts.googleapis.com imitacao do Google.
- Um schema com `$ref` dentro do resultado de ferramenta provocava HTTP 400
  no caminho OpenAI -> 9Router -> Gemini, inclusive apos atualizar o router.
- Dois fallbacks externos da configuracao principal retornaram HTTP 403.

O Google documenta fonts.googleapis.com como endpoint da
[API CSS do Google Fonts](https://developers.google.com/fonts/docs/css2).
Reconhecer o dominio oficial elimina esse falso sinal isolado, nao prova
que qualquer mensagem que contenha essa URL seja segura.

## Correcao e evidencia

Foi feito backup criptografado completo dos perfis/estado Hermes e dos dados
do 9Router com servicos parados. O check do Restic, incluindo uma amostra de
1% dos dados armazenados, passou. O router foi de 0.5.86 para 0.5.91, mantendo
porta e volume. Container e imagem anteriores ficaram preservados e parados;
rollback de dados exige restauracao revisada em staging.

O poller legado foi encerrado e recebeu uma trava anterior a qualquer tentativa
de rede. Seu teste falhou antes da trava e passou depois. As ferramentas SAP
nao foram removidas. Nao ativar outro poller com o token principal do Hermes.

O detector agora reconhece googleapis.com e gstatic.com por limite DNS exato.
Um dominio como fonts.googleapis.com.evil.example continua sendo suspeito;
outros sinais de phishing continuam escalando. Os tres e-mails do incidente
foram reavaliados somente-leitura: score 60 antes, score 0 depois.

A [protecao de transporte](../agent/transport/README.md) conserva schemas como
texto opaco somente no router local. A mesma requisicao real falhou com HTTP
400 sem protecao e respondeu com HTTP 200 com protecao. O builder instalado
tambem foi testado, confirmando que nao modifica os dados originais.

Reserva principal aplicada: hermes-fast, pool gratuito OpenRouter, Nemotron
3 Super gratuito, Qoder efficient e Nemotron 3.5 Lightning gratuito.
Os perfis locais receberam a reserva sem mudar modelo principal/persona.
As rotas dessa reserva passaram em chamadas simples e com historico tool.

## Limites restantes

- Os seis acessos Antigravity estao habilitados, mas dois constavam como
  unavailable. Habilitado nao equivale a saudavel nem demonstra uso simultaneo.
- As cotas e a disponibilidade podem mudar depois dos testes.
- Liquid gratuito retornou 503 e NVIDIA DeepSeek V4 Flash retornou 410.
  Nao entraram na reserva nova; combos preexistentes ainda contem essas entradas.
- Tokens repetidos nos perfis impedem multiplexacao segura. O Hermes fica
  standalone; nao foi feita migracao nem alteracao de tokens nesta manutencao.
- Fila duravel de todas as tarefas e cadeia de aprovadores por dominio continuam
  sendo trabalho distinto, nao comprovado por estas correcoes operacionais.
- Reenviar a pergunta no Telegram ainda e necessario para verificar a entrega
  completa ao usuario, alem da conectividade e testes de API.

Testes: 53 de plugins, 12 de transporte/configuracao, 29 de revisao e um do
poller legado. Todos passaram no ambiente correspondente.
