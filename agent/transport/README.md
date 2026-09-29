# Compatibilidade do 9Router local

Hermes/Ultron roda localmente em Windows + WSL Debian. Os exemplos abaixo
nao sao comandos para VPS e nao devem ser aplicados a servidores externos.

## Resultado de ferramenta contendo schema

No 9Router 0.5.91, a traducao OpenAI -> Gemini ainda transforma JSON de
resultados tool em `functionResponse.response`. Um `$ref` interno a um schema
retornado pela ferramenta pode ser interpretado pelo Gemini como referencia
do protocolo e rejeitado com HTTP 400.

`ultron_router_compat.py` mantem esses resultados como texto opaco somente para
`http://localhost:20130/v1` ou `http://127.0.0.1:20130/v1`, em chat completions.
Nao remove schema, nao muda instrucoes/persona, nao toca no historico salvo,
nao altera imagens e nao interfere em resultados JSON comuns.

`patch_router_compat.py` acrescenta uma chamada no builder upstream do Hermes,
salva backup antes de alterar e recusa uma ancora desconhecida. A instalacao
e idempotente. Revise novamente esse patch apos atualizar o Hermes.

```sh
# No Debian local; ajuste HERMES_ROOT ao checkout realmente instalado.
HERMES_ROOT=/opt/hermes-agent-20260924
"$HERMES_ROOT/venv/bin/python" -m unittest discover -s agent/transport -p 'test_*.py' -v
sudo install -m 600 agent/transport/ultron_router_compat.py "$HERMES_ROOT/agent/ultron_router_compat.py"
sudo python3 agent/transport/patch_router_compat.py "$HERMES_ROOT/agent/chat_completion_helpers.py"
sudo systemctl restart hermes-gateway.service
```

Antes de substituir um modulo de compatibilidade ja existente, preserve-o
em um backup privado. O script salva o builder original como
`chat_completion_helpers.py.bak-ultron-router-*`; restaurar esse arquivo e
reiniciar o gateway desfaz o hook. Nao sobrescreva outras alteracoes upstream.

## Reserva de modelos verificados

`repair_fallbacks.py` recebe uma lista explicitamente verificada em chamadas
reais. Nao inventa acesso, nao valida credenciais e nao promete disponibilidade.
Preserva o modelo principal, outras configuracoes e provedores nao descartados.
Deduplica localhost/127.0.0.1 e evita fallback para o proprio modelo principal.

```sh
# Primeiro: simular. Use o Python do venv do Hermes (dependencia: PyYAML).
sudo "$HERMES_ROOT/venv/bin/python" agent/transport/repair_fallbacks.py /root/.hermes \
  --models openrouter/openrouter/free openrouter/nvidia/nemotron-3-super-120b-a12b:free \
           qd/efficient openrouter/nvidia/nemotron-3.5-lightning:free \
  --drop-host api.xkiro.com --profiles
```

Os nomes acima foram testados em 29/09/2026; nao sao um catalogo eterno.
O descarte de api.xkiro.com foi especifico desta instalacao (HTTP 403).
Nao copie esse descarte para uma instalacao onde esse provedor funciona.
Acrescentar `--apply` aplica a simulacao, com escrita atomica, checagem de
alteracao concorrente e backup 0600 para cada config alterado. O script nunca
imprime chaves e nao altera arquivos SOUL.md nem regras de aprovacao.

Modelos `:free` sao gratuitos no provedor correspondente, mas dependem de
acesso, cota, suporte a ferramentas e disponibilidade. Qoder e acessado pela
conexao ja configurada; nao e declarado gratuito por este modulo.
