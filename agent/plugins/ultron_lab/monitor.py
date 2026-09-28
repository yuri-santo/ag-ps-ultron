"""Monitores automáticos do Ultron Lab, sem LLM.

Rodado pelo systemd (ultron-lab-monitor.timer) a cada 10 minutos:
- homelab: avisa no Telegram quando um serviço do inventário cai (2 checagens seguidas) e quando volta;
- email: analisa cada e-mail NOVO da INBOX (Gmail e Easysapers) com o detector de golpe e avisa só
  quando o score passa do limite.

Silencioso quando está tudo bem. Nunca envia, move ou marca e-mail; só lê com BODY.PEEK.
Uso: python -m ultron_lab.monitor [homelab|email|todos] [--dry-run] [--base /root/.hermes]
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from . import homelab, mailcheck

LIMITE_GOLPE = 51
FALHAS_PARA_ALERTAR = 2
MAX_VISTOS = 500
ROTULO_CONTA = {'gmail': 'Gmail', 'easysapers': 'e-mail da Easysapers'}


def read_env(path):
    values = {}
    path = Path(path)
    if not path.is_file():
        return values
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.replace('export ', '', 1).strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


class Telegram:
    def __init__(self, token, chat, opener=None):
        self.token, self.chat = token, str(chat)
        self.opener = opener or urllib.request.build_opener()

    def send(self, text):
        data = urllib.parse.urlencode({'chat_id': self.chat, 'text': text[:3900],
                                       'disable_web_page_preview': 'true'}).encode()
        request = urllib.request.Request(f'https://api.telegram.org/bot{self.token}/sendMessage', data=data)
        try:
            with self.opener.open(request, timeout=15) as response:
                return json.loads(response.read().decode()).get('ok') is True
        except Exception:
            return False


def telegram_from_env(base, environ=None):
    env = read_env(Path(base) / '.env')
    env.update({k: v for k, v in (environ if environ is not None else os.environ).items() if k.startswith(
        ('TELEGRAM_', 'ULTRON_LAB_'))})
    token = env.get('TELEGRAM_BOT_TOKEN')
    chat = env.get('ULTRON_LAB_ALERT_CHAT') or env.get('TELEGRAM_HOME_CHANNEL')
    if not chat and env.get('TELEGRAM_ALLOWED_USERS'):
        chat = env['TELEGRAM_ALLOWED_USERS'].split(',')[0].strip()
    return Telegram(token, chat) if token and chat else None


def load_settings(base):
    import yaml
    config = yaml.safe_load((Path(base) / 'config.yaml').read_text(encoding='utf-8')) or {}
    entries = ((config.get('plugins') or {}).get('entries') or {})
    return ((entries.get('ultron_lab') or {}).get('settings') or {})


def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.monitor-')
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=1)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


@contextmanager
def lock(path):
    import fcntl
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, 'w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit('outra execução do monitor em andamento')
        yield


def check_homelab(inventory, state, status_fn=None):
    status_fn = status_fn or homelab.status
    result = status_fn(inventory)
    previous = state.get('homelab') or {}
    current, down, back = {}, [], []
    for service in result['servicos']:
        entry = dict(previous.get(service['nome']) or {'falhas': 0, 'alertado': False})
        if not service.get('alertar', True):
            current[service['nome']] = {'falhas': 0, 'alertado': False, 'status': service['status']}
            continue
        if service['status'] == 'ok':
            if entry.get('alertado'):
                back.append(service)
            entry = {'falhas': 0, 'alertado': False}
        else:
            entry['falhas'] = int(entry.get('falhas', 0)) + 1
            if entry['falhas'] >= FALHAS_PARA_ALERTAR and not entry.get('alertado'):
                down.append(service)
                entry['alertado'] = True
        current[service['nome']] = entry
    state['homelab'] = current
    messages = []
    if down:
        items = [s['nome'] + (' (crítico)' if s.get('critico') else '') + (f" [{s['erro']}]" if s.get('erro') else '')
                 for s in down]
        messages.append('Homelab: fora do ar -> ' + ', '.join(items))
    if back:
        messages.append('Homelab: voltou -> ' + ', '.join(s['nome'] for s in back))
    return messages


def _reasons(result, limit=3):
    reasons = list(result.get('escalonamentos') or [])
    for layer in sorted(result.get('camadas') or [], key=lambda item: -item.get('score', 0)):
        reasons.extend(layer.get('achados') or [])
    seen, unique = set(), []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)
    return unique[:limit]


def format_email_alert(conta, message, result):
    return (f"Possível golpe no {ROTULO_CONTA.get(conta, conta)}: {result['veredito_label']} "
            f"({result['score']}/100)\n"
            f"De: {str(message.get('from', ''))[:120]}\n"
            f"Assunto: {str(message.get('subject', ''))[:160]}\n"
            f"Motivos: {'; '.join(_reasons(result))}\n"
            f"Não clique em links nem abra anexos. Detalhes: peça ao Ultron mail_fraud_check {conta} {message['uid']}.")


def check_email(contas, state, base, tools_factory, limit=15, threshold=LIMITE_GOLPE):
    messages, errors = [], []
    email_state = state.setdefault('email', {})
    for conta in contas:
        tools = tools_factory(conta)
        listing = tools.list_messages(limit=limit)
        if listing.get('status') != 'ok':
            errors.append(f"{conta}: {(listing.get('error') or {}).get('code', 'indisponivel')}")
            continue
        uids = [item['uid'] for item in listing.get('messages', [])]
        entry = email_state.setdefault(conta, {})
        if entry.get('uidvalidity') != listing.get('uidvalidity') or 'vistos' not in entry:
            entry.update(uidvalidity=listing.get('uidvalidity'), vistos=uids)
            continue
        seen = set(entry['vistos'])
        for item in listing.get('messages', []):
            if item['uid'] in seen:
                continue
            result = mailcheck.check_uid(conta, base, base, item['uid'], mail_tools=tools)
            if result.get('status') == 'ok' and result['score'] >= threshold:
                messages.append(format_email_alert(conta, item, result))
            elif result.get('status') != 'ok':
                errors.append(f"{conta} uid {item['uid']}: {result.get('error')}")
        entry['vistos'] = (uids + [uid for uid in entry['vistos'] if uid not in uids])[:MAX_VISTOS]
    return messages, errors


def default_tools_factory(base):
    return lambda conta: mailcheck.build_mail_tools(conta, base)


def run(target, base, dry_run=False, telegram=None, status_fn=None, tools_factory=None, settings=None):
    base = Path(base)
    settings = settings if settings is not None else load_settings(base)
    work = base / 'ultron_lab'
    state_path = work / 'monitor_estado.json'
    state = load_state(state_path)
    messages, errors = [], []
    if target in ('homelab', 'todos'):
        inventory = Path(settings.get('homelab_inventory') or work / 'homelab.json')
        try:
            messages += check_homelab(inventory, state, status_fn)
        except homelab.HomelabError as exc:
            errors.append('homelab: ' + str(exc))
    if target in ('email', 'todos'):
        contas = [c for c in (settings.get('mail_fraud_contas') or []) if c in ROTULO_CONTA]
        contas += [p for p in ROTULO_CONTA if p not in contas and (base / 'profiles' / p / 'config.yaml').is_file()]
        if contas:
            try:
                found, failed = check_email(contas, state, base, tools_factory or default_tools_factory(base))
                messages += found
                errors += failed
            except ImportError:
                errors.append('email: ultron_team indisponível')
    state['ultima_execucao'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    save_state(state_path, state)
    sent = 0
    if messages and not dry_run:
        telegram = telegram or telegram_from_env(base)
        if telegram is None:
            errors.append('telegram: TELEGRAM_BOT_TOKEN/chat não encontrados')
        else:
            sent = sum(1 for text in messages if telegram.send(text))
    return {'alvo': target, 'alertas': messages, 'enviados': sent, 'erros': errors, 'dry_run': dry_run}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Monitores automáticos do Ultron Lab')
    parser.add_argument('alvo', nargs='?', default='todos', choices=['homelab', 'email', 'todos'])
    parser.add_argument('--base', default=os.environ.get('ULTRON_LAB_BASE', '/root/.hermes'))
    parser.add_argument('--dry-run', action='store_true', help='não envia Telegram, só imprime')
    args = parser.parse_args(argv)
    with lock(Path(args.base) / 'ultron_lab' / 'monitor.lock'):
        summary = run(args.alvo, args.base, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
