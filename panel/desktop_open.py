"""Abre links e reuniões no Saitama (desktop Windows), nunca no celular que tocou o botão.

O celular só envia o endereço; quem abre é o Windows, com o navegador padrão ou o app
registrado para o protocolo (Teams, Zoom). Só http/https e protocolos de reunião conhecidos
são aceitos; nada de file:, javascript:, caminhos locais ou comandos.
"""
import os
import re
import urllib.parse

MAX_URL = 4096
SCHEMES = {'http', 'https', 'msteams', 'zoommtg', 'zoomus'}
FORBIDDEN = re.compile(r'[\x00-\x20\x7f"\'<>\\`]')

TEAMS_HOSTS = ('teams.microsoft.com', 'teams.live.com', 'teams.cloud.microsoft')
# Provedores aceitos para "Entrar na reunião". Convites de calendário vêm de terceiros, então
# o botão de reunião só abre salas desses provedores; links comuns usam /open.
MEETING_HOSTS = {
    'teams': TEAMS_HOSTS,
    'zoom': ('zoom.us', 'zoomgov.com'),
    'meet': ('meet.google.com',),
    'webex': ('webex.com',),
    'goto': ('meet.goto.com', 'gotomeeting.com', 'goto.com'),
    'whereby': ('whereby.com',),
    'jitsi': ('meet.jit.si',),
    'chime': ('chime.aws',),
}
APP_LABEL = {'teams': 'Teams', 'zoom': 'Zoom', 'meet': 'Google Meet', 'webex': 'Webex', 'goto': 'GoTo',
             'whereby': 'Whereby', 'jitsi': 'Jitsi', 'chime': 'Chime', 'browser': 'navegador'}


class LinkError(ValueError):
    pass


def _host_matches(host, suffixes):
    return any(host == s or host.endswith('.' + s) for s in suffixes)


def validate(url):
    if not isinstance(url, str) or not url or len(url) > MAX_URL or FORBIDDEN.search(url):
        raise LinkError('Link não permitido para abrir no Saitama.')
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in SCHEMES:
        raise LinkError('Link não permitido para abrir no Saitama.')
    if scheme in ('http', 'https'):
        if not parsed.hostname or parsed.username or parsed.password or '@' in parsed.netloc:
            raise LinkError('Link não permitido para abrir no Saitama.')
    return url


def provider(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ('msteams',):
        return 'teams'
    if parsed.scheme in ('zoommtg', 'zoomus'):
        return 'zoom'
    host = (parsed.hostname or '').lower().rstrip('.')
    for name, hosts in MEETING_HOSTS.items():
        if _host_matches(host, hosts):
            return name
    return 'browser'


def app_targets(url):
    """Pares (endereço, via) a tentar, do app nativo para o navegador."""
    parsed = urllib.parse.urlparse(url)
    kind = provider(url)
    targets = []
    if parsed.scheme == 'https' and kind == 'teams':
        targets.append(('msteams:' + url[len('https:'):], 'app'))
    elif parsed.scheme == 'https' and kind == 'zoom':
        match = re.fullmatch(r'/(?:j|w|s)/(\d{9,12})', parsed.path or '')
        if match:
            query = urllib.parse.parse_qs(parsed.query)
            params = {'action': 'join', 'confno': match[1]}
            if query.get('pwd'):
                params['pwd'] = query['pwd'][0]
            targets.append(('zoommtg://zoom.us/join?' + urllib.parse.urlencode(params), 'app'))
    targets.append((url, 'browser' if parsed.scheme in ('http', 'https') else 'app'))
    return kind, targets


def open_url(url, opener=None):
    """Abre no desktop. Devolve só metadados; o celular não navega para lugar nenhum."""
    opener = opener or os.startfile
    try:
        url = validate(url)
    except LinkError as exc:
        return {'ok': False, 'error': str(exc)}
    kind, targets = app_targets(url)
    last = None
    for target, via in targets:
        try:
            opener(target)
        except OSError as exc:
            last = exc
            continue
        return {'ok': True, 'status': 'opened_on_desktop', 'opened_on': 'Saitama', 'provider': kind, 'via': via,
                'app': APP_LABEL.get(kind, kind) if via == 'app' else 'navegador'}
    return {'ok': False, 'error': 'O Windows não conseguiu abrir o link: ' + type(last).__name__}


def open_meeting(url, opener=None):
    """Como open_url, mas só para salas de reunião de provedores conhecidos."""
    try:
        url = validate(url)
    except LinkError:
        return {'ok': False, 'error': 'Este convite não tem um link de reunião válido.'}
    if provider(url) == 'browser':
        host = urllib.parse.urlparse(url).hostname or 'desconhecido'
        return {'ok': False, 'error': 'Link de reunião de provedor desconhecido (' + host + '); abra pelo e-mail.'}
    return open_url(url, opener)
