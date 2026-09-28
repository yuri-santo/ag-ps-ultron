"""Dados financeiros de fontes públicas: Banco Central (SGS), BrasilAPI e Yahoo Finance (yfinance, via venv)."""
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

UA = 'Ultron-Financas/1.0 (uso pessoal)'
SERIES = {'selic': 11, 'selic_meta': 432, 'cdi': 12, 'ipca': 433, 'igpm': 189, 'inpc': 188, 'dolar': 1,
          'euro': 21619, 'tr': 226, 'poupanca': 195}
UNIDADE = {11: '% ao dia', 432: '% ao ano', 12: '% ao dia', 433: '% no mês', 189: '% no mês', 188: '% no mês',
           1: 'R$ por US$ (PTAX venda)', 21619: 'R$ por € (PTAX venda)', 226: '% ao mês', 195: '% ao mês'}
FIN_PYTHON = '/root/tools/fin-venv/bin/python'


class FonteErro(RuntimeError):
    pass


def _get(url, timeout=30, opener=None, tentativas=3):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    erro = None
    for tentativa in range(tentativas):
        try:
            with (opener or urllib.request.urlopen)(req, timeout=timeout) as resp:
                return json.loads(resp.read(5_000_000))
        except urllib.error.HTTPError as exc:
            erro = FonteErro(f'http_{exc.code}')
            if exc.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            erro = FonteErro('fonte_indisponivel:' + type(exc).__name__)
        if tentativa + 1 < tentativas:
            __import__('time').sleep(1.5 * (tentativa + 1))
    raise erro


def _data_br(value):
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', str(value)):
        raise ValueError('data_use_dd/mm/aaaa')
    return value


def bcb_serie(serie, ultimos=12, data_inicial='', data_final='', opener=None):
    key = str(serie).strip().lower()
    code = SERIES.get(key) or (int(key) if key.isdigit() and 0 < int(key) < 100000 else None)
    if not code:
        raise ValueError('serie_desconhecida:' + ','.join(SERIES))
    base = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados'
    if data_inicial:
        params = {'formato': 'json', 'dataInicial': _data_br(data_inicial)}
        if data_final:
            params['dataFinal'] = _data_br(data_final)
        url = base + '?' + urllib.parse.urlencode(params)
    else:
        url = f'{base}/ultimos/{max(1, min(int(ultimos or 12), 120))}?formato=json'
    rows = _get(url, opener=opener)
    valores = [{'data': r.get('data'), 'valor': float(str(r.get('valor')).replace(',', '.'))} for r in rows if r.get('valor') not in (None, '')]
    hoje = date.today()
    def _d(txt):
        try:
            dd, mm, aa = str(txt).split('/')
            return date(int(aa), int(mm), int(dd))
        except ValueError:
            return hoje
    # A série da meta Selic (432) traz a data de validade até a próxima reunião do Copom; não apresentar data futura.
    passados = [v for v in valores if _d(v['data']) <= hoje]
    futuros = [v for v in valores if _d(v['data']) > hoje]
    valores = passados or [dict(futuros[0], data=hoje.strftime('%d/%m/%Y'))] if futuros or passados else []
    out = {'status': 'ok', 'fonte': f'Banco Central do Brasil — SGS {code}', 'serie': key, 'unidade': UNIDADE.get(code, ''),
           'valores': valores[-120:]}
    if code in (433, 189, 188) and len(valores) >= 12:
        acumulado = 1.0
        for v in valores[-12:]:
            acumulado *= 1 + v['valor'] / 100
        out['acumulado_12_meses_pct'] = round((acumulado - 1) * 100, 2)
    return out


def brasilapi(recurso, valor='', opener=None):
    base = 'https://brasilapi.com.br/api'
    if recurso == 'feriados':
        ano = str(valor or date.today().year)
        if not re.fullmatch(r'\d{4}', ano):
            raise ValueError('ano_invalido')
        data = _get(f'{base}/feriados/v1/{ano}', opener=opener)
    elif recurso == 'cnpj':
        cnpj = re.sub(r'\D', '', str(valor))
        if len(cnpj) != 14:
            raise ValueError('cnpj_invalido')
        data = _get(f'{base}/cnpj/v1/{cnpj}', opener=opener)
        data = {k: v for k, v in data.items() if k in (
            'cnpj', 'razao_social', 'nome_fantasia', 'descricao_situacao_cadastral', 'data_situacao_cadastral',
            'data_inicio_atividade', 'cnae_fiscal_descricao', 'natureza_juridica', 'porte', 'capital_social',
            'municipio', 'uf', 'opcao_pelo_simples', 'opcao_pelo_mei', 'qsa')}
    elif recurso == 'taxas':
        data = _get(f'{base}/taxas/v1', opener=opener)
    elif recurso == 'banco':
        codigo = re.sub(r'\D', '', str(valor))
        if not codigo:
            raise ValueError('codigo_do_banco_obrigatorio')
        data = _get(f'{base}/banks/v1/{codigo}', opener=opener)
    else:
        raise ValueError('recurso_invalido')
    return {'status': 'ok', 'fonte': 'BrasilAPI (agrega fontes públicas: Receita, BCB, ANBIMA)', 'recurso': recurso, 'dados': data}


def cotacao_b3(ticker, periodo='1y', python=FIN_PYTHON, runner=subprocess.run):
    ticker = str(ticker or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{4,6}(\.SA)?|\^BVSP', ticker):
        raise ValueError('ticker_invalido')
    if ticker != '^BVSP' and not ticker.endswith('.SA'):
        ticker += '.SA'
    if periodo not in ('1mo', '3mo', '6mo', '1y', '2y', '5y'):
        raise ValueError('periodo_invalido')
    if not Path(python).exists():
        return {'status': 'error', 'error': 'yfinance_nao_instalado'}
    helper = str(Path(__file__).with_name('yf_helper.py'))
    proc = runner([python, helper, ticker, periodo], capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        return {'status': 'error', 'error': 'consulta_falhou', 'detalhe': (proc.stderr or '')[-300:]}
    data = json.loads(proc.stdout)
    data.update(status='ok', fonte='Yahoo Finance via yfinance (não oficial; pode ter atraso de 15 min ou mais)')
    return data
