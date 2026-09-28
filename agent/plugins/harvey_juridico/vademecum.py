"""Consulta local ao Vade Mecum do Senado Federal (3ª ed., atualizado até jan/2026)."""
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

MAX_TEXTO = 4000
AVISO = ('Texto do Vade Mecum do Senado Federal, 3ª ed., atualizado até janeiro de 2026. Normas não substituem o DOU. '
         'Antes de concluir, confira se houve alteração posterior (lexml_buscar ou Planalto) e cite a data da consulta.')


def _plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', str(text)) if unicodedata.category(c) != 'Mn').lower().strip()


def normalizar_artigo(value):
    """'Art. 5º' -> '5'; '1.036' -> '1036'; '4-A' -> '4-A'."""
    raw = str(value or '').strip()
    m = re.search(r'(\d{1,4}(?:\.\d{3})?)\s*[oº°]?\s*(?:-\s*([A-Za-z]{1,2}))?', raw)
    if not m:
        raise ValueError('artigo_invalido')
    return m[1].replace('.', '') + ('-' + m[2].upper() if m[2] else '')


class VadeMecum:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError('vademecum_indisponivel')

    def _db(self):
        db = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def normas(self):
        with self._db() as db:
            return [dict(r) for r in db.execute('SELECT sigla, nome, lei, pagina_inicial, pagina_final FROM normas ORDER BY pagina_inicial')]

    def resolver_norma(self, norma):
        if not norma:
            return None
        key = _plain(norma)
        with self._db() as db:
            rows = [dict(r) for r in db.execute('SELECT sigla, nome, lei, apelidos FROM normas')]
        for r in rows:
            if key in (_plain(r['sigla']), _plain(r['nome'])) or key in [_plain(a) for a in json.loads(r['apelidos'] or '[]')]:
                return r['sigla']
        for r in rows:
            if key and (key in _plain(r['nome']) or key in _plain(r['lei'])):
                return r['sigla']
        raise ValueError('norma_nao_encontrada')

    @staticmethod
    def _formatar(row):
        texto = row['texto']
        cortado = len(texto) > MAX_TEXTO
        return {'sigla': row['sigla'], 'norma': row['norma'], 'artigo': row['artigo'], 'pagina': row['pagina'],
                'citacao': f"{row['sigla']}, art. {row['artigo']} (Vade Mecum Senado Federal, 3ª ed., p. {row['pagina']})",
                'texto': texto[:MAX_TEXTO] + (' …[truncado]' if cortado else ''), 'truncado': cortado}

    def consultar(self, consulta='', norma='', artigo='', limite=5):
        limite = max(1, min(int(limite or 5), 15))
        sigla = self.resolver_norma(norma) if norma else None
        with self._db() as db:
            if artigo:
                numero = normalizar_artigo(artigo)
                sql = 'SELECT * FROM artigos WHERE artigo=?' + (' AND sigla=?' if sigla else '') + ' ORDER BY pagina LIMIT ?'
                params = [numero] + ([sigla] if sigla else []) + [limite]
                rows = db.execute(sql, params).fetchall()
            else:
                termos = [t for t in re.findall(r'\w+', _plain(consulta)) if len(t) >= 3][:12]
                if not termos:
                    raise ValueError('consulta_vazia')
                rows = []
                for joiner in (' AND ', ' OR '):
                    match = joiner.join(f'"{t}"' for t in termos)
                    sql = ('SELECT a.* FROM busca JOIN artigos a ON a.id = busca.rowid WHERE busca MATCH ?'
                           + (' AND a.sigla=?' if sigla else '') + ' ORDER BY bm25(busca) LIMIT ?')
                    rows = db.execute(sql, [match] + ([sigla] if sigla else []) + [limite]).fetchall()
                    if rows:
                        break
            meta = dict(db.execute('SELECT chave, valor FROM meta').fetchall())
        return {'status': 'ok', 'fonte': meta.get('fonte'), 'atualizacao': meta.get('atualizacao'),
                'resultados': [self._formatar(r) for r in rows], 'aviso_vigencia': AVISO,
                'observacao': '' if rows else 'Nada encontrado no Vade Mecum; a norma pode não estar compilada nele (consulte lexml_buscar).'}
