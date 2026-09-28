"""Executado no venv do juscraper: imprime JSON com a 1ª página de jurisprudência de um TJ."""
import json
import sys

import juscraper as jus

tribunal, termo, pagina = sys.argv[1], sys.argv[2], int(sys.argv[3])
df = jus.scraper(tribunal).cjsg(termo, paginas=range(pagina, pagina + 1))
rows = []
for record in df.head(15).to_dict(orient='records'):
    item = {}
    for key, value in record.items():
        text = '' if value is None else str(value)
        if text and text != 'nan':
            item[str(key)] = text[:1500]
    rows.append(item)
print(json.dumps({'tribunal': tribunal, 'termo': termo, 'pagina': pagina, 'resultados': rows}, ensure_ascii=False))
