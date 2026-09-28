"""Jurisprudência: links oficiais prontos, consulta aos TJs via juscraper e link do Jusbrasil
só para conferência humana (os Termos de Uso do Jusbrasil proíbem robôs e automação)."""
import json
import subprocess
import urllib.parse
from pathlib import Path

TJS_JUSCRAPER = ('tjsp', 'tjes', 'tjto', 'tjba', 'tjce', 'tjdft', 'tjmt', 'tjpa', 'tjpb', 'tjpe', 'tjpi', 'tjpr',
                 'tjrn', 'tjro', 'tjrr', 'tjrs', 'tjsc')


def links_oficiais(tema):
    q = str(tema or '').strip()[:300]
    if not q:
        raise ValueError('tema_vazio')
    enc = urllib.parse.quote(q)
    return {'status': 'ok', 'tema': q, 'links': [
        {'fonte': 'STF — Pesquisa de Jurisprudência (oficial)', 'url': f'https://jurisprudencia.stf.jus.br/pages/search?base=acordaos&sinonimo=true&plural=true&page=1&pageSize=10&queryString={enc}&sort=_score&sortBy=desc'},
        {'fonte': 'STF — Repercussão Geral (temas)', 'url': 'https://portal.stf.jus.br/jurisprudenciaRepercussao/'},
        {'fonte': 'STJ — SCON (oficial)', 'url': f'https://scon.stj.jus.br/SCON/pesquisar.jsp?livre={enc}'},
        {'fonte': 'STJ — Dados Abertos (espelhos de acórdãos)', 'url': 'https://dadosabertos.web.stj.jus.br/'},
        {'fonte': 'TST — Jurisprudência (oficial)', 'url': 'https://jurisprudencia.tst.jus.br/'},
        {'fonte': 'CNJ — Banco Nacional de Precedentes', 'url': 'https://pangeabnp.pdpj.jus.br/'},
        {'fonte': 'Jusbrasil — somente conferência humana (não automatizar)', 'url': f'https://www.jusbrasil.com.br/jurisprudencia/busca?q={enc}'}],
        'como_usar': ('Para STF/STJ/TST use web_search restrito a site:stf.jus.br, site:stj.jus.br, site:tst.jus.br e leia o '
                      'acórdão/tema no domínio oficial com web_extract; cite número, órgão julgador, relator e DATA de julgamento '
                      'e de publicação. O link do Jusbrasil vai na resposta para o Yuri conferir; não raspe nem leia o Jusbrasil por automação.')}


def tj_jurisprudencia(tribunal, termo, pagina=1, python='/root/tools/juridico-venv/bin/python', helper=None, runner=subprocess.run):
    tribunal = str(tribunal or '').lower().strip()
    if tribunal not in TJS_JUSCRAPER:
        raise ValueError('tribunal_nao_suportado')
    termo = str(termo or '').strip()[:300]
    if not termo:
        raise ValueError('termo_vazio')
    pagina = max(1, min(int(pagina or 1), 5))
    helper = helper or str(Path(__file__).with_name('juscraper_cjsg.py'))
    if not Path(python).exists():
        return {'status': 'error', 'error': 'juscraper_nao_instalado'}
    proc = runner([python, helper, tribunal, termo, str(pagina)], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return {'status': 'error', 'error': 'consulta_tj_falhou', 'detalhe': (proc.stderr or '')[-300:]}
    data = json.loads(proc.stdout or '{}')
    data.update(status='ok', fonte=f'{tribunal.upper()} — consulta de jurisprudência (juscraper, página oficial do tribunal)',
                observacao='Confira a ementa no site do tribunal antes de citar; cite número, órgão, relator e data.')
    return data
