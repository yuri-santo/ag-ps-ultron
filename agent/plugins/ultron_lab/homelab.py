"""Status do homelab a partir de um inventário administrado por Yuri.

O modelo só escolhe filtros (grupo/nome). URLs, cabeçalhos e timeouts vêm do
arquivo de inventário, então um texto injetado não consegue fazer o Ultron
sondar endereços arbitrários. Cabeçalhos secretos são lidos de variáveis de
ambiente pelo nome; o valor nunca aparece na resposta.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

MAX_INVENTORY = 256 * 1024
MAX_SERVICES = 80
NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,39}$')
ENV_RE = re.compile(r'^[A-Z][A-Z0-9_]{1,63}$')


class HomelabError(ValueError):
    pass


def _expected(value):
    if value is None:
        return list(range(200, 400))
    if value == 'qualquer':
        # Serviço sem rota de saúde conhecida: qualquer resposta HTTP abaixo de 500 prova que está de pé.
        return list(range(100, 500))
    values = value if isinstance(value, list) else [value]
    if not values or not all(type(v) is int and 100 <= v <= 599 for v in values):
        raise HomelabError('esperado_invalido')
    return values


def load_inventory(path):
    path = Path(path)
    if not path.is_file():
        raise HomelabError('inventario_ausente')
    if path.stat().st_size > MAX_INVENTORY:
        raise HomelabError('inventario_grande_demais')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError:
        raise HomelabError('inventario_json_invalido') from None
    raw = data.get('servicos') if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise HomelabError('inventario_sem_servicos')
    if len(raw) > MAX_SERVICES:
        raise HomelabError('servicos_demais')
    services, seen = [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise HomelabError('servico_invalido')
        name = entry.get('nome')
        if not isinstance(name, str) or not NAME_RE.match(name) or name in seen:
            raise HomelabError('nome_invalido')
        seen.add(name)
        url = entry.get('url')
        parsed = urlparse(url) if isinstance(url, str) else None
        if not parsed or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
            raise HomelabError('url_invalida:' + name)
        timeout = entry.get('timeout', 5)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 15:
            raise HomelabError('timeout_invalido:' + name)
        headers_env = entry.get('headers_env', {})
        if not isinstance(headers_env, dict) or not all(
                isinstance(k, str) and re.fullmatch(r'[A-Za-z0-9-]{1,64}', k) and isinstance(v, str) and ENV_RE.match(v)
                for k, v in headers_env.items()):
            raise HomelabError('headers_env_invalido:' + name)
        services.append({
            'nome': name, 'url': url, 'grupo': str(entry.get('grupo', 'geral'))[:40],
            'descricao': str(entry.get('descricao', ''))[:120], 'esperado': _expected(entry.get('esperado')),
            'timeout': float(timeout), 'headers_env': headers_env, 'critico': bool(entry.get('critico', False)),
            'alertar': bool(entry.get('alertar', True)),
        })
    return services


def check_service(service, opener=None, environ=None):
    environ = os.environ if environ is None else environ
    opener = opener or urllib.request.build_opener()
    headers = {'User-Agent': 'ultron-homelab/1.0'}
    missing = [var for var in service['headers_env'].values() if not environ.get(var)]
    for header, var in service['headers_env'].items():
        if environ.get(var):
            headers[header] = environ[var]
    request = urllib.request.Request(service['url'], method='GET', headers=headers)
    started = time.monotonic()
    code, error = None, None
    try:
        with opener.open(request, timeout=service['timeout']) as response:
            code = response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, 'reason', exc)
        error = type(reason).__name__ if not isinstance(reason, str) else 'URLError'
    elapsed = int((time.monotonic() - started) * 1000)
    ok = code in service['esperado']
    result = {'nome': service['nome'], 'grupo': service['grupo'], 'status': 'ok' if ok else 'falha',
              'http': code, 'ms': elapsed, 'critico': service['critico'],
              'alertar': service.get('alertar', True)}
    if service['descricao']:
        result['descricao'] = service['descricao']
    if error:
        result['erro'] = error
    if missing:
        result['aviso'] = 'variáveis de cabeçalho ausentes: ' + ', '.join(missing)
    return result


def status(inventory_path, *, grupo='', nome='', opener=None, environ=None, workers=8):
    services = load_inventory(inventory_path)
    if grupo:
        services = [s for s in services if s['grupo'] == grupo]
    if nome:
        services = [s for s in services if s['nome'] == nome]
    if not services:
        raise HomelabError('nenhum_servico_no_filtro')
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(services)))) as pool:
        results = list(pool.map(lambda s: check_service(s, opener, environ), services))
    down = [r['nome'] for r in results if r['status'] != 'ok']
    critical = [r['nome'] for r in results if r['status'] != 'ok' and r['critico']]
    return {'status': 'ok', 'verificados': len(results), 'no_ar': len(results) - len(down), 'fora': down,
            'criticos_fora': critical, 'servicos': results,
            'grupos': sorted({r['grupo'] for r in results}),
            'limites': 'Checagem HTTP pontual a partir do Hermes; "ok" significa que respondeu com o código esperado, '
                       'não que o serviço está funcionalmente correto.'}
