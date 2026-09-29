# marketingskills no Money

Subconjunto de 10 skills de [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills),
snapshot `5b2c0007766c6a1cf1d53fd8fc73e979e0821022`, licença MIT em
[`marketingskills/LICENSE`](marketingskills/LICENSE). Os arquivos Markdown e
referências estão vendorizados aqui para uma reinstalação reproduzível. Nenhum
script do projeto externo é copiado ou executado.

O instalador insere regras de escopo no início de cada `SKILL.md`: acesso a
contas nunca é presumido; análise e rascunhos são permitidos; publicação,
mensagens, gastos e mudanças de campanha exigem autorização explícita para a
ação concreta. Os `SOUL.md` não são lidos nem alterados.

## Instalar no WSL existente

Na raiz deste repositório, com Python 3.11+:

```sh
sudo python3 agent/marketing/install_marketingskills.py \
  --profile-home /root/.hermes/profiles/money
hermes --profile money skills list
```

O instalador recusa outro perfil e skills preexistentes sem a marca de gerência.
Instalações posteriores guardam a versão anterior em
`/root/.hermes/profiles/money/backups/marketingskills/`. Sessões já abertas podem
precisar de nova sessão ou recarga de skills para reconhecer a lista atual.

## Escopo

`product-marketing`, `customer-research`, `copywriting`, `content-strategy`,
`social`, `seo-audit`, `ad-creative`, `ads`, `analytics`, `ab-testing`.
São métodos e referências, não conectores para TikTok Ads, Google Ads ou Meta.
Money só opera contas se uma integração separada estiver configurada e o dono
autorizar a operação. Não há promessa de receita automática.

## Verificação

```sh
python3 -m unittest discover -s agent/marketing -p 'test_*.py' -v
hermes --profile money skills list
sha256sum /root/.hermes/profiles/money/SOUL.md
```

O último comando deve dar o mesmo hash de antes da instalação. Outro perfil,
por exemplo `hermes --profile bigode skills list`, não deve listar este pacote.
