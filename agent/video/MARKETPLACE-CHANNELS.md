# Afiliacao por canal

Decisao do titular: separar Mercado Livre e TikTok Shop. Nunca converter um
link ML em SKU Shop ou alegar que comissoes migram de um programa para outro.

O pool privado existente conserva os 20 links fornecidos pelo titular. A leitura
do catalogo acrescenta commerce.program/channel e marca identidade e comissao
como nao verificadas. Classificar dominio NAO valida oferta nem afiliacao.
Preservar URL original completa para divulgacao; resolved_url/IDs sao evidencia
separada, nunca substitutos silenciosos. Nao remover parametros de afiliacao.

Para Mercado Livre: abrir o link, distinguir produto destacado de recomendacoes,
confirmar ID do anuncio, catalogo, variante, vendedor, disponibilidade e fonte.
Links meli.la podem abrir perfil social com muitos produtos. Nao assumir que o
primeiro item recomendado ou a imagem de outro vendedor e o produto do link.
Um preco visto nao e historico de precos nem promessa de frete/estoque futuro.

Para TikTok Shop: obter o produto do Marketplace do Criador, confirmar SKU,
variante, elegibilidade, conta de comissao e identidade do criador. Registrar
adicao somente apos recibo/estado persistido da vitrine. O coletor Seller de
oportunidades nao comprova afiliacao nem altera vitrine. Produto equivalente
precisa nova verificacao visual; nao reutilizar video de uma variante diferente.

O executor instalado affiliate_autonomy.py e para campanhas de links externos.
Ele nao implementa adicao a vitrine. require_channel bloqueia tentativas de
encaminhar produtos Shop por esse executor, inclusive acesso direto ao guard.
Campanhas externas permanecem sujeitas a regras do destino; nao misturar CTA
Mercado Livre em video com produto TikTok Shop vinculado. Nenhuma permissao
de publicar e concedida por classificacao ou anotacao do catalogo.

Fontes oficiais BR consultadas em 2026-09-30:
- https://seller-br.tiktok.com/university/essay?knowledge_id=6250796942821137&lang=pt-BR
  Anunciar com URL importa dados para oferta de vendedor, nao comissao externa.
- https://seller-br.tiktok.com/university/essay?knowledge_id=6825383530710785
  Vitrine usa produtos elegiveis e programa de afiliados TikTok Shop.
- https://seller-br.tiktok.com/university/essay?knowledge_id=5721853217900304
  Conteudo com produtos a venda nao deve redirecionar compra para fora do Shop.
