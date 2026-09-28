# Varredura de ferramentas no GitHub — 28/09/2026

Adaptadas e instaladas agora:
- **jtrecenti/juscraper** (MIT): jurisprudência dos TJs → ferramenta `tj_jurisprudencia` do Harvey (venv /root/tools/juridico-venv).
- **DataJud/CNJ, DJEN (Comunica PJe) e LexML**: clientes próprios em `harvey_juridico/oficiais.py`, a partir das notas de uso de rvsanches/skills-datajud-djen e da documentação oficial.
- **Planalto (legislação compilada)**: `planalto_artigo` lê o texto vigente sem a redação riscada e com as notas "Redação dada pela Lei ...".
- **Vade Mecum do Senado (3ª ed., jan/2026)**: índice local por norma/artigo (SQLite FTS5), exclusivo do Harvey.

Recomendadas para a próxima rodada (não instaladas):
1. **k2-fsa/sherpa-onnx + nvidia/parakeet-tdt-0.6b-v3 (int8)** — transcrição em CPU bem mais rápida e com pontuação; diarização em CPU. Substituto natural do faster-whisper `base`.
2. **pyannote/pyannote-audio (community-1, modo exclusivo)** — nomes de quem falou na ata, processado depois da reunião.
3. **DeHor-Labs/mcp-juridico-brasil** — MCP de DataJud com calculadora de prazos do CPC (conferência cruzada do `prazo_processual`).
4. **Mcp-Brasil/mcp-brasil** — ~70 APIs públicas (TCU, Senado, Transparência) para Frank e Bigode; o módulo STF/STJ/TST dele retorna vazio, não usar.
5. **elapouya/python-docx-template** — ata também em Word editável.
6. **MarkusPfundstein/mcp-obsidian**, **homeassistant-ai/ha-mcp**, **paperless-ngx** — integração com Obsidian, Casa e arquivo de documentos.

Cuidados:
- **Jusbrasil**: os Termos de Uso proíbem robôs e automação; o Harvey só gera o link de busca para conferência humana.
- STF, STJ e TST colocaram proteção anti-robô nas buscas; o Harvey usa os portais oficiais via web_search/web_extract e os links oficiais.
- Nesta rede, `www.lexml.gov.br` e `legis.senado.leg.br` não respondem em HTTPS (timeout); o Planalto responde.
- Chave pública do DataJud muda sem aviso: ajuste `datajud_api_key` se a consulta começar a dar 401/403.
