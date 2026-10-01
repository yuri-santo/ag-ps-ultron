# Separacao dos programas de afiliados

**Goal:** preservar links do titular sem confundir afiliacao Mercado Livre com
vitrine TikTok Shop. Desenho autorizado pelo titular nesta conversa.

**Architecture:** manter pool e ledger existentes; enriquecer classificacao de
canal sem alterar URLs, nem fabricar produto/variante/comissao. Produtos Shop
exigem ID nativo, identidade confirmada, elegibilidade e recibo antes de registrar
adicao. Importar oferta como vendedor nao faz parte desta autorizacao.

**Tech Stack:** Python stdlib, JSON atomico/lock Linux e testes unittest.

- [x] Criar testes de classificacao, preservacao exata de URL, spoofed domains,
  duplicatas e bloqueio de links ML na vitrine Shop.
- [x] Implementar modulo independente de separacao, sem rede ou publicacao.
- [x] Validar pool privado existente; gerar catalogo anotado para pesquisa.
- [x] Integrar classificacao na leitura do catalogo oficial e instrucoes.
- [ ] Inspecionar acesso real de criador Shop antes de qualquer adicao.
- [x] Testar regressao, documentar pendencias e preservar backup privado.

Codigo e testes preparados para publicacao sem dados de conta. A adicao real
de produtos Shop continua pendente e nao e liberada por esta migracao.

Em 01/10/2026: 57 testes de video aprovados, incluindo render FFmpeg sintetico.
20 links existentes Mercado Livre classificados, URLs preservadas. Nenhum item
adicionado a vitrine nem video publicado nesta validacao. Seller autenticado
permite pesquisa, mas nao comprova elegibilidade do perfil de criador.

Em paralelo: corrigir fim da captura nos relatorios e iniciar fundacao de
admissao duravel do desenho de fila ja aprovado. Nenhuma dessas tarefas autoriza
novos provedores pagos, estoque ficticio, anuncios pagos ou bypass de revisao.
