"""Public adapter for the original Ultron finance modules. No private defaults."""
import hashlib
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timedelta

import dash
from dash import Input, Output, State, ctx, dash_table, dcc, html
import dash_bootstrap_components as dbc
import flask
import plotly.graph_objects as go

from finance_engine import estado, fluxo_mensal, mes_corrente, brl
from finance_motion import spatial_page
from finance_planning import install as install_planning
from finance_tree import install as install_tree

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('FIN_DATA_DIR', str(BASE / 'data'))).resolve()
DB = str(Path(os.environ.get('FIN_DB_PATH', str(DATA / 'finance-demo.db'))).resolve())
PORT = int(os.environ.get('FIN_PORT', '9501'))
PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
if not PASSWORD:
    raise SystemExit('Set DASHBOARD_PASSWORD before starting the dashboard.')
if not Path(DB).is_file():
    raise SystemExit('Database missing. Run: python bootstrap.py --demo')
DATA.mkdir(parents=True, exist_ok=True)
secret_path = DATA / 'session.key'
if not secret_path.exists():
    with secret_path.open('x', encoding='ascii') as stream:
        stream.write(secrets.token_hex(32))
    secret_path.chmod(0o600)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True, title='Ultron Finance',
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}])
server = app.server
server.secret_key = secret_path.read_text(encoding='ascii').strip()
server.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                     MAX_CONTENT_LENGTH=6 * 1024 * 1024)
MAX_ATTEMPTS = 5


def is_authed():
    return bool(flask.session.get('auth'))


@server.before_request
def protect_callbacks():
    if flask.request.method == 'POST':
        origin = flask.request.headers.get('Origin')
        if origin and origin.rstrip('/') != flask.request.host_url.rstrip('/'):
            return flask.abort(403)
    if flask.request.path == '/_dash-update-component' and not is_authed():
        payload = flask.request.get_json(silent=True) or {}
        if payload.get('output') not in ('root.children', 'login-result.children'):
            return flask.abort(401)


TABLES = {
    'contas_a_pagar': 'Contas', 'gastos_fatura': 'Gastos do cartao',
    'cartoes_credito': 'Cartoes', 'faturas_fechadas': 'Faturas fechadas',
    'compras_parceladas': 'Parcelas', 'assinaturas': 'Assinaturas',
    'horas_receber': 'Recebimentos', 'tickets_pagamento': 'Chamados',
    'metas': 'Metas', 'caixinhas': 'Reservas', 'caixinhas_movimentos': 'Movimentos',
    'carteira_real': 'Carteira', 'moradia': 'Moradia', 'config': 'Premissas',
}
GROUPS = {
    '/receita': ['contas_a_pagar', 'gastos_fatura'],
    '/cartoes': ['cartoes_credito', 'faturas_fechadas', 'compras_parceladas'],
    '/assinaturas': ['assinaturas'], '/horas': ['tickets_pagamento', 'horas_receber'],
    '/metas': ['metas', 'caixinhas', 'caixinhas_movimentos', 'moradia'],
    '/investimentos': ['carteira_real'], '/config': ['config'],
}
NAV = [('/', 'Visao geral'), ('/categorias', 'Despesas'), ('/receita', 'Contas e gastos'),
       ('/cartoes', 'Cartoes'), ('/assinaturas', 'Assinaturas'), ('/horas', 'Horas e recebimentos'),
       ('/comportamento', 'Historico'), ('/preditivo', 'Projecao'), ('/investimentos', 'Carteira'),
       ('/metas', 'Metas e reservas'), ('/mapa', 'Mapa de decisoes'),
       ('/planejamento-antigo', 'Cenarios e imagens'), ('/config', 'Premissas')]


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def read_table(name):
    if name not in TABLES:
        raise ValueError('Tabela desconhecida')
    with connect() as db:
        info = list(db.execute(f'PRAGMA table_info({name})'))
        rows = [dict(row) for row in db.execute(f'SELECT * FROM {name}')]
    return info, rows


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save_table(name, rows, expected):
    if not is_authed():
        raise PermissionError('Login necessario')
    info, old = read_table(name)
    if fingerprint(old) != expected:
        raise ValueError('Dados mudaram em outra sessao. Reabra a tabela antes de salvar.')
    columns = [row['name'] for row in info]
    if len(rows) > 10000:
        raise ValueError('Limite de linhas excedido')
    cleaned = []
    for row in rows:
        if set(row) - set(columns):
            raise ValueError('Coluna desconhecida')
        values = []
        for col in info:
            value = row.get(col['name'])
            if value == '':
                value = None
            if col['type'] in ('REAL', 'INTEGER') and value is not None:
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError('Use numeros finitos')
                if col['type'] == 'INTEGER':
                    if not value.is_integer():
                        raise ValueError('Coluna exige um numero inteiro')
                    value = int(value)
            if isinstance(value, str) and len(value) > 4000:
                raise ValueError('Texto excede limite')
            values.append(value)
        cleaned.append(values)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = [dict(row) for row in db.execute(f'SELECT * FROM {name}')]
        if fingerprint(current) != expected:
            raise ValueError('Dados mudaram em outra sessao')
        db.execute(f'DELETE FROM {name}')
        db.executemany(f'INSERT INTO {name} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', cleaned)
        if name == 'tickets_pagamento':
            db.execute('DELETE FROM horas_mensal')
            db.execute("INSERT INTO horas_mensal SELECT substr(data,1,7), SUM(horas) FROM tickets_pagamento WHERE status='Realizado' AND data IS NOT NULL GROUP BY substr(data,1,7)")


page_planning = install_planning(app, DB, is_authed)
page_mapa = install_tree(app, DB, is_authed)


def login_page():
    return html.Main([
        html.H1('Ultron Finance'),
        dbc.Input(id='login-password', type='password', placeholder='Senha', autoComplete='current-password'),
        dbc.Button('Entrar', id='login-btn', className='mt-3'), html.Div(id='login-result'),
    ], className='public-login')


app.layout = html.Div([dcc.Location(id='url'), dcc.Store(id='month', data=mes_corrente()), html.Div(id='root')])


@app.callback(Output('root', 'children'), Input('url', 'pathname'))
def render_root(path):
    if not is_authed():
        return login_page()
    with connect() as db:
        marker = db.execute("SELECT value FROM config WHERE key='dataset'").fetchone()
    return html.Div([
        html.Header([html.Strong('Ultron Finance'), html.Span('Dados ficticios' if marker and marker[0] == 'synthetic' else 'Base local'),
                     dcc.Input(id='month-input', type='text', value=mes_corrente(), placeholder='AAAA-MM', maxLength=7),
                     dbc.Button('Sair', id='logout', color='secondary', size='sm'), html.Div(id='logout-result')], className='public-header'),
        html.Nav([dcc.Link(label, href=url, className='active' if path == url else '') for url, label in NAV], className='public-nav'),
        html.Main(id='page', className='public-content'),
    ])


@app.callback(Output('month', 'data'), Input('month-input', 'value'))
def select_month(value):
    try:
        return datetime.strptime(value, '%Y-%m').strftime('%Y-%m')
    except (ValueError, TypeError):
        return dash.no_update


@app.callback(Output('login-result', 'children'), Input('login-btn', 'n_clicks'), Input('login-password', 'n_submit'), State('login-password', 'value'), prevent_initial_call=True)
def login(click, enter, password):
    ip = flask.request.remote_addr or 'local'
    now = datetime.now()
    with connect() as db:
        row = db.execute('SELECT * FROM login_attempts WHERE ip=?', (ip,)).fetchone()
        if row and row['bloqueado_ate'] and datetime.fromisoformat(row['bloqueado_ate']) > now:
            return dbc.Alert('Acesso temporariamente bloqueado.', color='warning')
        if secrets.compare_digest(str(password or ''), PASSWORD):
            db.execute('DELETE FROM login_attempts WHERE ip=?', (ip,))
            flask.session.clear()
            flask.session['auth'] = True
            return dcc.Location(id='signed-in', href='/', refresh=True)
        count = (row['tentativas'] if row else 0) + 1
        block = (now + timedelta(minutes=30)).isoformat() if count >= MAX_ATTEMPTS else None
        db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?,?)', (ip, 0 if block else count, block, now.isoformat()))
    return dbc.Alert('Senha incorreta.', color='danger')


@app.callback(Output('logout-result', 'children'), Input('logout', 'n_clicks'), prevent_initial_call=True)
def logout(click):
    flask.session.clear()
    return dcc.Location(id='signed-out', href='/', refresh=True)


def kpi(label, value):
    return html.Div([html.Span(label), html.Strong('R$ '+brl(value))], className='public-kpi')


def overview(month):
    current = estado(DB, month)
    figure = go.Figure(go.Bar(x=['Entradas previstas', 'Despesas', 'Saldo previsto'],
                              y=[current['renda_mes'], current['despesas_total'], current['sobra']],
                              marker_color=['#139579', '#d45068', '#357bba']))
    figure.update_layout(height=340)
    return html.Div([html.H2('Visao geral'), html.Div([
        kpi('Recebido', current['renda_paga']), kpi('A receber', current['renda_pendente']),
        kpi('Despesas do mes', current['despesas_total']), kpi('Saldo previsto', current['sobra']),
    ], className='public-kpis'), dcc.Graph(figure=figure),
        html.H3('Metas'), html.Ul([html.Li(f"{goal['nome']}: R$ {brl(goal['atual'])} / R$ {brl(goal['alvo'])}") for goal in current['metas']])])


def editor(path):
    names = GROUPS[path]
    return html.Div([html.H2(dict(NAV).get(path, 'Cadastros')),
        dcc.Dropdown(id='table-select', options=[{'label': TABLES[n], 'value': n} for n in names], value=names[0], clearable=False),
        dcc.Store(id='table-version'), dash_table.DataTable(id='editor', editable=True, row_deletable=True,
            page_size=15, sort_action='native', filter_action='native', style_table={'overflowX': 'auto'},
            style_cell={'minWidth': '100px', 'maxWidth': '280px', 'whiteSpace': 'normal', 'textAlign': 'left'}),
        html.Div([dbc.Button('Adicionar', id='add-row', color='secondary'), dbc.Button('Salvar', id='save-rows'),
                  dbc.Button('Exportar CSV', id='export-rows', color='secondary')], className='public-actions'),
        html.Div(id='save-result'), dcc.Download(id='export-data')])


def categories(month):
    with connect() as db:
        rows = list(db.execute('SELECT categoria,SUM(valor) valor FROM gastos_fatura WHERE mes_ref=? GROUP BY categoria', (month,)))
    return html.Div([html.H2('Despesas por categoria'), dcc.Graph(figure=go.Figure(go.Bar(x=[r[0] for r in rows], y=[r[1] for r in rows])))])


@app.callback(Output('page', 'children'), Input('url', 'pathname'), Input('month', 'data'))
def route(path, month):
    if not is_authed():
        return html.Div()
    month = month or mes_corrente()
    if path in GROUPS:
        result = editor(path)
    elif path in ('/mapa', '/planejamento'):
        result = page_mapa(month)
    elif path == '/planejamento-antigo':
        result = page_planning()
    elif path in ('/categorias', '/comportamento'):
        result = categories(month)
    elif path == '/preditivo':
        lines = fluxo_mensal(DB, estado(DB, month), horizonte=24)
        result = html.Div([html.H2('Projecao de caixa'), html.P('Estimativa com renda base e despesas observadas. Nao representa renda garantida.'),
            dcc.Graph(figure=go.Figure(go.Scatter(x=[r['mes'] for r in lines], y=[r['sobra'] for r in lines], mode='lines+markers', name='Saldo projetado')))])
    elif path == '/mei':
        result = html.Div([html.H2('Contabilidade'), html.P('Regras tributarias e integracoes fiscais nao fazem parte desta versao publica.')])
    else:
        result = overview(month)
    return spatial_page(result, month, path or '/')


@app.callback(Output('editor', 'columns'), Output('editor', 'data'), Output('table-version', 'data'),
              Input('table-select', 'value'), Input('add-row', 'n_clicks'), Input('save-rows', 'n_clicks'),
              State('editor', 'data'), State('table-version', 'data'))
def table_change(name, add, save, rows, version):
    if not is_authed():
        return [], [], None
    info, current = read_table(name)
    columns = [{'id': c['name'], 'name': c['name'].replace('_', ' ').title(),
                'type': 'numeric' if c['type'] in ('REAL', 'INTEGER') else 'text'} for c in info]
    if ctx.triggered_id == 'save-rows':
        try:
            save_table(name, rows or [], version)
        except (ValueError, TypeError, sqlite3.Error) as error:
            raise dash.exceptions.PreventUpdate from error
        _, current = read_table(name)
    elif ctx.triggered_id == 'add-row':
        new = {c['name']: (0 if c['type'] in ('REAL', 'INTEGER') else '') for c in info}
        for c in info:
            if c['pk'] and c['type'] == 'INTEGER':
                new[c['name']] = None
        return columns, list(rows or []) + [new], version
    return columns, current, fingerprint(current)


@app.callback(Output('save-result', 'children'), Input('table-version', 'data'), prevent_initial_call=True)
def saved(version):
    return html.Span('Base carregada.', className='text-muted')


@app.callback(Output('export-data', 'data'), Input('export-rows', 'n_clicks'), State('table-select', 'value'), prevent_initial_call=True)
def export(click, name):
    if not is_authed():
        raise dash.exceptions.PreventUpdate
    import csv
    import io
    info, rows = read_table(name)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=[c['name'] for c in info])
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "'"+value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value for key, value in row.items()})
    return dcc.send_string(stream.getvalue(), name+'.csv')


if __name__ == '__main__':
    from waitress import serve
    serve(server, host='127.0.0.1', port=PORT)
