# 9Router local: Codex Free

Verificado em 07/10/2026. O 9Router local passou de 0.5.91 para 0.5.95
usando a imagem decolua/9router. Porta 127.0.0.1:20130, volume persistente e
limite de memoria foram preservados. Nao houve alteracao na fila do Hermes.

## Contas e modelos

As duas conexoes Codex ativas retornaram `plan=free` na consulta de uso.
O catalogo individual atualizado listou estes modelos visiveis, que responderam
a chamadas de teste pelo router:

- `cx/gpt-6-luna`
- `cx/gpt-5.6-terra`
- `cx/gpt-5.6-luna`

Disponibilidade e limites dependem da conta e podem mudar. Free nao significa
uso ilimitado nem credito gratuito da API OpenAI. As cinco conexoes Codex que
ja estavam desativadas permaneceram desativadas; os demais provedores foram
preservados. Emails, tokens e senhas nao sao publicados neste repositorio.

## Combos

`codex-free` contem somente os tres modelos acima, nessa ordem.
`hermes-reasoning`, `hermes-coding` e `free-fallback` receberam os mesmos modelos
antes dos fallbacks existentes. `hermes-fast` usa Luna 6, Luna 5.6 e Terra 5.6.
O combo `Thor` preserva seu primeiro modelo SAP e acrescenta Codex em seguida.
`antigravity-rotation` nao foi alterado. Referencias antigas Codex em combos
editados foram substituidas, sem apagar modelos ou credenciais de provedores.

Ultron continua configurado com `hermes-reasoning`, portanto recebe a mudanca
no router sem trocar personalidade ou perfil. A selecao das duas contas Codex
permanece sob a politica nativa do 9Router; nao foi implementado contorno de cotas.

## Verificacao e recuperacao

- Testes individuais dos tres modelos: HTTP 200 com resposta.
- Combos `codex-free`, `hermes-fast`, `hermes-coding`: testes aprovados.
- `codex-free`: gerou chamada estruturada `local_probe` com argumento valido;
  ferramenta nao executada. Modelo servido: `gpt-6-luna`.
- Banco: integridade ok, 16 conexoes preservadas, 7 combos finais.
- Dashboard: `/dashboard/quota?provider=codex` filtra as conexoes Codex;
  a API de listagem confirmou as duas contas ativas. Nao foi confirmado um
  defeito visual especifico da tela anterior.

Backups privados de perfil, banco SQLite consistente, credenciais do dashboard,
segredo JWT, identidade da maquina e inspecao do container ficam em
`/root/ultron-local/maintenance/9router-20261007T*/`, com permissoes restritas.
Ha snapshots antes e depois da atualizacao. O container anterior esta parado
como `ultron-9router-before-20261007`; nao o iniciar junto ao atual nem restaurar
tokens antigos sem necessidade, pois provedores podem rotacionar refresh tokens.
Backup de credenciais nao garante que uma sessao continue valida no futuro.
