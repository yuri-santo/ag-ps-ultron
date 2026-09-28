"""Leitura somente-leitura da mensagem bruta por UID para a análise de golpe.

Reaproveita as credenciais e a conta vinculada do ultron_team.MailTools
(mesmo accounts.json, mesma checagem de conta por perfil) e usa BODY.PEEK com
INBOX em modo readonly, então a mensagem não é marcada como lida.
"""
from pathlib import Path
import re
import sys

from . import golpe

MAX_MESSAGE = 2 * 1024 * 1024


class MailCheckError(ValueError):
    pass


# Conta lógica -> tipo de conta no accounts.json. O nome do perfil varia por instalação
# (gmail/easysapers na VPS antiga; greg/cris no Hermes local), então o perfil é resolvido pelo tipo.
TIPO_CONTA = {'gmail': 'gmail', 'easysapers': 'workmail'}


def _mail_module(plugins_dir):
    plugins_dir = str(plugins_dir)
    if plugins_dir not in sys.path:
        sys.path.insert(0, plugins_dir)
    from ultron_team import mail_tools
    return mail_tools


def _mail_tools_class(plugins_dir):
    return _mail_module(plugins_dir).MailTools


def resolve_profile(conta, accounts_map):
    """Devolve a chave de ACCOUNTS do ultron_team que corresponde à conta lógica (gmail/easysapers)."""
    if conta in accounts_map:
        return conta
    tipo = TIPO_CONTA.get(conta)
    for key, value in accounts_map.items():
        if isinstance(value, (tuple, list)) and value and value[0] == tipo:
            return key
    return conta


def build_mail_tools(conta, base):
    base = Path(base)
    module = _mail_module(base / 'plugins')
    profile = resolve_profile(conta, getattr(module, 'ACCOUNTS', {}))
    return module.MailTools(profile, base / 'skills/email-manager/scripts/accounts.json', base / 'ultron_lab' / 'data')


def fetch_raw(mail_tools, uid):
    if isinstance(uid, bool) or not re.fullmatch(r'[1-9][0-9]{0,9}', str(uid)) or int(uid) > 4294967295:
        raise MailCheckError('uid_invalido')
    value = str(uid)
    with mail_tools._mail() as (mail, _count, validity):
        status, rows = mail.uid('fetch', value, '(RFC822.SIZE)')
        header = b' '.join(row if isinstance(row, bytes) else row[0] for row in rows or []
                           if isinstance(row, bytes) or (isinstance(row, tuple) and isinstance(row[0], bytes)))
        match = re.search(rb'RFC822\.SIZE (\d+)', header)
        if status != 'OK' or not match:
            raise MailCheckError('mensagem_nao_encontrada')
        if int(match[1]) > MAX_MESSAGE:
            raise MailCheckError('mensagem_grande_demais')
        status, rows = mail.uid('fetch', value, f'(BODY.PEEK[]<0.{MAX_MESSAGE + 1}>)')
        chunks = [row[1] for row in rows or [] if isinstance(row, tuple) and isinstance(row[1], bytes)]
        if status != 'OK' or not chunks:
            raise MailCheckError('mensagem_nao_encontrada')
        data = b''.join(chunks)
        if len(data) > MAX_MESSAGE:
            raise MailCheckError('mensagem_grande_demais')
        return data, validity


def check_uid(profile, base, home, uid, *, mail_tools=None):
    """Analisa a mensagem UID da INBOX da conta do perfil. Nunca envia, move ou marca como lida."""
    try:
        if mail_tools is None:
            if Path(home) == Path(base):
                mail_tools = build_mail_tools(profile, base)
            else:
                MailTools = _mail_tools_class(Path(home) / 'plugins')
                mail_tools = MailTools(profile, Path(base) / 'skills/email-manager/scripts/accounts.json',
                                       Path(home) / 'data')
        raw, validity = fetch_raw(mail_tools, uid)
        result = golpe.analyze(raw)
        result.update(uid=str(uid), uidvalidity=validity, conta=getattr(mail_tools, 'account', profile))
        return result
    except (MailCheckError, golpe.GolpeError) as exc:
        return {'status': 'error', 'error': str(exc)}
    except ImportError:
        return {'status': 'error', 'error': 'ultron_team_indisponivel'}
    except Exception as exc:
        code = str(exc) if type(exc).__name__ == 'MailError' else 'mail_indisponivel'
        return {'status': 'error', 'error': code}
