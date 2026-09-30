# Identidade visual verificavel

Antes de gerar, fixar no brief a variante exata, canonical_product_id e
product.packaging_required (booleano explicito). Se a caixa faz parte do anuncio,
deve ser true. Nao omitir a caixa para contornar uma divergencia. Pin das imagens
originais em facts.identity_references, com path absoluto, sha256, source_url
oficial HTTPS e source_receipt {path,sha256}. Recibo de fonte contem identidade,
variante, URL, image_sha256, authority manufacturer/official_store, checked_at e
observation. A autoridade precisa ser verificada na fonte, nao autodeclarada.

Todos os artefatos devem ficar dentro da pasta da campanha que contem brief.json.
O exemplo sintetico completo e executavel esta em test_product_identity.py.
Nao copiar seus resultados ficticios para campanhas reais.

quality.json deve conter product_identity {path,sha256}, apontando ao manifesto
JSON version 1. O manifesto vincula campaign_id, canonical_product_id, variant,
brief, video, render_receipt (cada arquivo com path e sha256), references iguais
ao brief, reviewer real, method visual_comparison, checked_at com fuso e scenes.
Cada cena tem scene_id (1-based), source, generation_receipt, frames (arquivo,
hash e timestamp no MP4 final), checks para item, packaging, labels, colors,
shape, accessories, scale. Cada check exige status match e notes concretas.
packaging not_visible so vale quando a caixa nao era exigida. Unknown/mismatch
bloqueiam publicacao. Referencias e revisao devem ter menos de 24 horas.

Inspecionar visualmente inicio, meio e fim de TODAS as cenas no MP4 final;
revisar tambem movimentos/cortes, rotulos pequenos e deformacoes entre amostras.
Nao basta preencher JSON. Extrair frames do video final por ferramenta real,
comparar com imagens oficiais e registrar detalhes observados. Ausencia de
ferramenta visual ou fonte oficial impede aprovacao. Preferir filmagem/imagem
real do produto com composicao quando a geracao nao mantiver identidade.

O validador verifica vinculos e completude, NAO comprova verdade visual nem
garante igualdade de cada pixel. Retorna visual_truth_verified false para nao
enganar o comite. O broker recebe o manifesto e hashes de todos os artefatos;
uma revisao textual nao deve alegar que viu ou ouviu o video. Alterar qualquer
artefato exige nova inspecao e revisao, nunca reutilizar aprovacao anterior.
Esta etapa nao altera horarios, autoriza anuncios pagos nem comprova postagem:
publicacao e atualizacao da vitrine exigem recibo real da conta correta.
