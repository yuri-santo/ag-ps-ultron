"""Bounded, account-bound read-only mail access and local draft storage."""
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
import imaplib
import json
import os
from pathlib import Path
import re
import uuid

ACCOUNTS = {'gmail': ('gmail', 'voce@gmail.com'),
            'easysapers': ('workmail', 'voce@empresa.com')}
MAX_MESSAGE = 2 * 1024 * 1024


class MailError(ValueError):
    pass


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'br', 'div', 'li') and not self.hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def decode_part(part):
    raw = part.get_payload(decode=True) or b''
    try:
        return raw.decode(part.get_content_charset() or 'utf-8', errors='replace')
    except LookupError:
        return raw.decode('utf-8', errors='replace')


class MailTools:
    def __init__(self, profile, accounts_path, data_dir, imap_factory=imaplib.IMAP4_SSL):
        self.profile = profile
        self.accounts_path = Path(accounts_path)
        self.data_dir = Path(data_dir)
        self.factory = imap_factory
        self.account = ACCOUNTS.get(profile, ('', ''))[0]

    def _account(self):
        if self.profile not in ACCOUNTS:
            raise MailError('invalid_profile')
        acc = json.loads(self.accounts_path.read_text(encoding='utf-8-sig'))[self.account]
        if acc.get('email', '').casefold() != ACCOUNTS[self.profile][1]:
            raise MailError('account_mismatch')
        return acc

    def _run(self, operation):
        try:
            result = operation()
            return {'status': 'ok', 'account': self.account, **result}
        except Exception as exc:
            return {'status': 'error', 'account': self.account,
                    'error': {'type': type(exc).__name__,
                              'code': str(exc) if isinstance(exc, MailError) else 'mail_unavailable'}}

    @staticmethod
    def _limit(limit):
        if type(limit) is not int or not 1 <= limit <= 30:
            raise MailError('invalid_limit')

    @contextmanager
    def _mail(self):
        acc = self._account()
        mail = None
        try:
            mail = self.factory(acc['imap_host'], acc.get('imap_port', 993), timeout=20)
            mail.login(acc['email'], acc['password'])
            status, data = mail.select('INBOX', readonly=True)
            if status != 'OK':
                raise MailError('inbox_unavailable')
            count = int(data[0])
            _, validity = mail.response('UIDVALIDITY')
            yield mail, count, validity[0].decode() if validity and validity[0] else ''
        finally:
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass

    @staticmethod
    def _uids(mail, count, limit):
        if count == 0:
            return []
        status, rows = mail.fetch(f'{max(1, count-limit+1)}:{count}', '(UID)')
        if status != 'OK':
            raise MailError('mail_read_failed')
        result = []
        for row in rows or []:
            raw = row[0] if isinstance(row, tuple) else row
            if isinstance(raw, bytes):
                match = re.search(rb'\bUID (\d+)', raw)
                if match:
                    result.append(match[1].decode())
        return result[::-1]

    @staticmethod
    def _fetch(mail, uid, headers=False):
        maximum = 65536 if headers else MAX_MESSAGE
        section = 'HEADER' if headers else ''
        status, rows = mail.uid('fetch', uid, f'(BODY.PEEK[{section}]<0.{maximum+1}>)')
        chunks = [row[1] for row in rows or [] if isinstance(row, tuple) and isinstance(row[1], bytes)]
        if status != 'OK' or not chunks:
            raise MailError('message_not_found')
        raw = b''.join(chunks)
        if len(raw) > maximum:
            raise MailError('message_too_large')
        return BytesParser(policy=policy.default).parsebytes(raw)

    @staticmethod
    def _headers(msg, uid):
        return {'uid': uid, 'subject': str(msg.get('Subject', '')),
                'from': str(msg.get('From', '')), 'to': str(msg.get('To', '')),
                'date': str(msg.get('Date', '')), 'message_id': str(msg.get('Message-ID', ''))}

    def list_messages(self, limit=10):
        def operation():
            self._limit(limit)
            with self._mail() as (mail, count, validity):
                messages = [self._headers(self._fetch(mail, uid, True), uid)
                            for uid in self._uids(mail, count, limit)]
                return {'messages': messages, 'uidvalidity': validity, 'inbox_count': count}
        return self._run(operation)

    def read_message(self, uid):
        def operation():
            if isinstance(uid, bool) or not re.fullmatch(r'[1-9][0-9]{0,9}', str(uid)) or int(uid) > 4294967295:
                raise MailError('invalid_uid')
            value = str(uid)
            with self._mail() as (mail, count, validity):
                status, rows = mail.uid('fetch', value, '(RFC822.SIZE)')
                raw = b' '.join(row for row in rows or [] if isinstance(row, bytes))
                match = re.search(rb'RFC822.SIZE (\d+)', raw)
                if status != 'OK' or not match:
                    raise MailError('message_not_found')
                if int(match[1]) > MAX_MESSAGE:
                    raise MailError('message_too_large')
                msg = self._fetch(mail, value)
                parts = [p for p in msg.walk() if p.get_content_disposition() != 'attachment']
                plain = [decode_part(p) for p in parts if p.get_content_type() == 'text/plain']
                if plain:
                    body = '\n'.join(plain)
                else:
                    parser = TextHTML()
                    for part in parts:
                        if part.get_content_type() == 'text/html':
                            parser.feed(decode_part(part))
                    body = ''.join(parser.parts).strip()
                return {**self._headers(msg, value), 'body': body[:12000],
                        'truncated': len(body) > 12000, 'uidvalidity': validity}
        return self._run(operation)

    def search_messages(self, query, limit=10):
        def operation():
            self._limit(limit)
            if not isinstance(query, str) or not query.strip() or len(query) > 200:
                raise MailError('invalid_query')
            with self._mail() as (mail, count, validity):
                uids = self._uids(mail, count, 100)
                found = []
                for uid in uids:
                    record = self._headers(self._fetch(mail, uid, True), uid)
                    if query.casefold() in ' '.join(record.values()).casefold():
                        found.append(record)
                return {'messages': found[:limit], 'uidvalidity': validity,
                        'scope': {'scanned': len(uids), 'limited': count > 100,
                                  'matches_truncated': len(found) > limit},
                        'notice': 'Busca nos cabeçalhos das últimas 100 mensagens da INBOX; não inclui todo o histórico.'}
        return self._run(operation)

    def save_draft(self, to, subject, body):
        def operation():
            if not all(isinstance(value, str) for value in (to, subject, body)):
                raise MailError('invalid_draft')
            if (not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', to)
                    or any(c in to+subject for c in '\r\n\x00') or not body.strip()
                    or len(subject) > 500 or len(body) > 100000):
                raise MailError('invalid_draft')
            acc = self._account()
            directory = self.data_dir / 'drafts'
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            identity = uuid.uuid4().hex
            path = directory / (identity + '.json')
            record = {'id': identity, 'from': acc['email'], 'account': self.account,
                      'to': to, 'subject': subject, 'body': body, 'sent': False}
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
            return {'stored_locally': True, 'sent': False,
                    'draft': {'id': identity, 'path': str(path), 'stored_locally': True, 'sent': False}}
        return self._run(operation)
