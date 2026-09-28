"""Indexa o Vade Mecum do Senado (3ª ed., atualizado até jan/2026) por norma e artigo em SQLite FTS5."""
import json, re, sqlite3, sys, unicodedata
from pathlib import Path

LAYOUT, RAW, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
layout = Path(LAYOUT).read_text(encoding='utf-8').split('\f')
raw = Path(RAW).read_text(encoding='utf-8').split('\f')

# 1) Sumário -> (título, página inicial)
entries = []
for page in layout[3:8]:
    for line in page.splitlines():
        m = re.match(r'\s*(.+?)\s*[�.·]{3,}\s*(\d{1,3})\s*$', line)
        if m:
            entries.append((re.sub(r'\s+', ' ', m[1]).strip(), int(m[2])))
entries.sort(key=lambda x: x[1])
SIGLAS = {
 'Constituição da República Federativa do Brasil': ('CF', ['cf', 'cf/88', 'constituicao', 'constituição federal', 'crfb']),
 'Ato das Disposições Constitucionais Transitórias': ('ADCT', ['adct']),
 'Lei de Introdução às Normas do Direito Brasileiro': ('LINDB', ['lindb', 'licc']),
 'Código Civil': ('CC', ['cc', 'codigo civil', 'cc/2002']),
 'Código de Processo Civil': ('CPC', ['cpc', 'cpc/2015']),
 'Código Penal': ('CP', ['cp', 'codigo penal']),
 'Lei das Contravenções Penais': ('LCP', ['lcp']),
 'Código de Processo Penal': ('CPP', ['cpp']),
 'Código Tributário Nacional': ('CTN', ['ctn']),
 'Código de Defesa do Consumidor': ('CDC', ['cdc']),
 'Código Eleitoral': ('CE', ['codigo eleitoral']),
 'Código Florestal': ('CFlo', ['codigo florestal']),
 'Consolidação das Leis do Trabalho': ('CLT', ['clt']),
 'Estatuto da Cidade': ('EC', ['estatuto da cidade']),
 'Estatuto da Criança e do Adolescente': ('ECA', ['eca']),
 'Estatuto da Igualdade Racial': ('EIR', []),
 'Estatuto da Juventude': ('EJ', []),
 'Estatuto da Pessoa com Deficiência': ('EPD', ['lbi']),
 'Estatuto da Pessoa Idosa': ('EPI', ['estatuto do idoso']),
 'Lei Antidrogas': ('LAD', ['lei de drogas', '11.343']),
 'Lei de Diretrizes e Bases da Educação Nacional': ('LDB', ['ldb']),
 'Lei de Licitações e Contratos Administrativos': ('LLC', ['14.133', 'lei de licitacoes']),
 'Lei de Responsabilidade Fiscal': ('LRF', ['lrf']),
 'Lei do Emprego Doméstico': ('LED', ['lc 150']),
 'Lei do Regime Jurídico dos Servidores Públicos Civis': ('RJU', ['8.112']),
 'Lei Maria da Penha': ('LMP', ['11.340']),
}
def sigla_de(title):
    for nome, (sig, _) in SIGLAS.items():
        if title.startswith(nome):
            return sig, nome
    return None, None

ranges = []
for i, (title, start) in enumerate(entries):
    end = entries[i + 1][1] - 1 if i + 1 < len(entries) else len(raw)
    ranges.append((title, start, end))

def fix(text):
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)          # hifenização de fim de linha
    text = re.sub(r'[ \t]*\n[ \t]*', '\n', text)
    return text

ART = re.compile(r'^Art\.\s*(\d{1,4}(?:\.\d{3})?)\s*(?:[oº°])?\s*(?:-\s*([A-Z]{1,2}))?\s*\.?\s', re.M)
rows = []
normas = []
for title, start, end in ranges:
    sig, nome = sigla_de(title)
    if not sig or title.startswith(('Índice', 'Lei de Introdução ao', 'Apresentação')):
        continue
    lei = re.search(r'\(([^)]+)\)', title)
    normas.append({'sigla': sig, 'nome': nome, 'titulo': title, 'lei': lei[1] if lei else '', 'pagina_inicial': start, 'pagina_final': end})
    # texto contínuo com marcação de página
    chunks = []
    for pg in range(start, end + 1):
        body = raw[pg - 1]
        lines = body.split('\n')
        # remove cabeçalho/rodapé (nome da norma e número de página)
        lines = [l for l in lines if not re.fullmatch(r'\s*\d{1,3}\s*', l) and l.strip() not in (nome, title)]
        chunks.append((pg, fix('\n'.join(lines))))
    text = ''
    marks = []
    for pg, body in chunks:
        marks.append((len(text), pg))
        text += body + '\n'
    def page_at(pos):
        cur = start
        for off, pg in marks:
            if off <= pos: cur = pg
            else: break
        return cur
    found = list(ART.finditer(text))
    for j, m in enumerate(found):
        stop = found[j + 1].start() if j + 1 < len(found) else len(text)
        body = text[m.start():stop].strip()
        if len(body) > 20000: body = body[:20000]
        num = m[1].replace('.', '') + (('-' + m[2]) if m[2] else '')
        rows.append((sig, nome, num, page_at(m.start()), body))

def plain(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()

Path(OUT).unlink(missing_ok=True)
db = sqlite3.connect(OUT)
db.executescript('''
CREATE TABLE meta(chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE normas(sigla TEXT PRIMARY KEY, nome TEXT, titulo TEXT, lei TEXT, pagina_inicial INT, pagina_final INT, apelidos TEXT);
CREATE TABLE artigos(id INTEGER PRIMARY KEY, sigla TEXT, norma TEXT, artigo TEXT, pagina INT, texto TEXT);
CREATE INDEX artigos_ref ON artigos(sigla, artigo);
CREATE VIRTUAL TABLE busca USING fts5(texto, norma, content='artigos', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
''')
db.executemany('INSERT INTO meta VALUES (?,?)', [
    ('fonte', 'Vade Mecum Senado Federal, 3ª edição (Brasília, 2026)'),
    ('atualizacao', 'Atualizada até janeiro de 2026'),
    ('aviso', 'As normas aqui apresentadas não substituem as publicações do Diário Oficial da União.'),
    ('isbn_pdf', '978-65-5676-704-8')])
for n in normas:
    db.execute('INSERT OR REPLACE INTO normas VALUES (?,?,?,?,?,?,?)', (n['sigla'], n['nome'], n['titulo'], n['lei'], n['pagina_inicial'], n['pagina_final'], json.dumps(SIGLAS[n['nome']][1], ensure_ascii=False)))
db.executemany('INSERT INTO artigos(sigla, norma, artigo, pagina, texto) VALUES (?,?,?,?,?)', rows)
db.execute("INSERT INTO busca(rowid, texto, norma) SELECT id, texto, norma FROM artigos")
db.commit()
print('normas', len(normas), 'artigos', len(rows))
for sig, cnt in db.execute('SELECT sigla, count(*) FROM artigos GROUP BY sigla ORDER BY 2 DESC'):
    print(sig, cnt)
