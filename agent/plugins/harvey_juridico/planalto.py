"""Texto vigente no Planalto (legislação compilada), para conferir alterações e datas após jan/2026.

Só busca páginas de www.planalto.gov.br. Remove o texto riscado (<strike>/<s>/<del>) das
versões compiladas, que é redação revogada, e mantém as notas "Redação dada pela Lei nº ...".
"""
import html
import re
import urllib.parse
from html.parser import HTMLParser

from .oficiais import FonteErro, _http

# Atalhos para as normas do Vade Mecum (versões compiladas). Se algum falhar, localizar com
# web_search site:planalto.gov.br e passar a URL.
ATALHOS = {
    'CF': 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm',
    'CC': 'https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm',
    'CPC': 'https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm',
    'CP': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm',
    'CPP': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm',
    'CTN': 'https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm',
    'CDC': 'https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm',
    'CLT': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm',
    'ECA': 'https://www.planalto.gov.br/ccivil_03/leis/l8069compilado.htm',
    'LINDB': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm',
    'LLC': 'https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm',
    'LRF': 'https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm',
    'RJU': 'https://www.planalto.gov.br/ccivil_03/leis/l8112cons.htm',
    'LMP': 'https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm',
    'LAD': 'https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm',
    'LGPD': 'https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm',
}


class _Texto(HTMLParser):
    RISCADO = {'strike', 's', 'del'}
    BLOCO = {'p', 'br', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'table'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self.riscado, self.ignorar = [], 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.RISCADO:
            self.riscado += 1
        elif tag in ('script', 'style', 'head'):
            self.ignorar += 1
        elif tag in self.BLOCO:
            self.partes.append('\n')

    def handle_endtag(self, tag):
        if tag in self.RISCADO and self.riscado:
            self.riscado -= 1
        elif tag in ('script', 'style', 'head') and self.ignorar:
            self.ignorar -= 1
        elif tag in self.BLOCO:
            self.partes.append('\n')

    def handle_data(self, data):
        if not self.riscado and not self.ignorar:
            self.partes.append(data)


def texto_vigente(html_text):
    parser = _Texto()
    parser.feed(html_text)
    text = html.unescape(''.join(parser.partes)).replace('\xa0', ' ').replace('\r', '')
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n+', '\n', text).strip()


def extrair_artigo(texto, artigo):
    m = re.fullmatch(r'\s*(?:art\.?\s*)?(\d{1,4}(?:\.\d{3})?)\s*[ºo°]?\s*(?:-\s*([A-Za-z]{1,2}))?\s*', str(artigo), re.I)
    if not m:
        raise ValueError('artigo_invalido')
    numero = m[1]
    variantes = {numero, numero.replace('.', ''), f'{int(numero.replace(".", "")):,}'.replace(',', '.')}
    sufixo = (r'\s*-\s*' + m[2].upper()) if m[2] else r'(?!\s*-\s*[A-Z]\b)'
    alvo = re.compile(r'(?m)^\s*Art\.\s*(?:' + '|'.join(re.escape(v) for v in variantes) + r')\s*[ºo°]?' + sufixo + r'(?!\d)\s*[.\-–]?')
    inicio = alvo.search(texto)
    if not inicio:
        return ''
    proximo = re.compile(r'(?m)^\s*Art\.\s*\d').search(texto, inicio.end())
    return texto[inicio.start(): proximo.start() if proximo else inicio.start() + 8000].strip()


def planalto_artigo(artigo, norma='', url='', opener=None):
    norma = str(norma or '').upper().strip()
    url = str(url or ATALHOS.get(norma, '')).strip()
    if not url:
        raise ValueError('informe_url_do_planalto_ou_norma_com_atalho:' + ','.join(sorted(ATALHOS)))
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('www.planalto.gov.br', 'planalto.gov.br'):
        raise ValueError('somente_urls_https_do_planalto')
    # O Planalto (F5) derruba conexões de clientes que não se identificam como navegador.
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Harvey-Ultron/1.0',
               'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'pt-BR,pt;q=0.9'}
    try:
        raw = _http(url, timeout=45, opener=opener, headers=headers)
    except FonteErro:
        raw = _http(url, timeout=60, opener=opener, headers=headers)
    charset = 'utf-8'
    head = raw[:3000].decode('ascii', errors='ignore').lower()
    if 'windows-1252' in head or 'iso-8859-1' in head:
        charset = 'cp1252'
    try:
        page = raw.decode(charset)
    except UnicodeDecodeError:
        page = raw.decode('cp1252', errors='replace')
    trecho = extrair_artigo(texto_vigente(page), artigo)
    if not trecho:
        return {'status': 'ok', 'url': url, 'encontrado': False,
                'observacao': 'Artigo não localizado na página; confira a URL (versão compilada) ou o número.'}
    cortado = len(trecho) > 6000
    notas = re.findall(r'\((?:Redação dada|Incluído|Incluída|Revogado|Revogada|Vide|Vigência)[^)]{0,200}\)', trecho)
    notas = [re.sub(r'\s+', ' ', n) for n in notas]
    return {'status': 'ok', 'url': url, 'encontrado': True, 'texto_vigente': trecho[:6000] + (' …[truncado]' if cortado else ''),
            'notas_de_alteracao': notas[:20], 'fonte': 'Planalto — legislação compilada (texto riscado removido)',
            'observacao': 'Compare com o Vade Mecum (jan/2026); nota "Redação dada pela Lei ..., de ..." mostra quando mudou. Cite a data da consulta.'}
