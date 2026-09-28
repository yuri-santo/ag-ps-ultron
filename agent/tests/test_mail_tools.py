import imaplib
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

try:
    from ultron_team.mail_tools import MailTools
except ModuleNotFoundError:
    MailTools = None


def email_bytes(subject='Invoice', body='Hello', charset='utf-8', html=False):
    kind = 'html' if html else 'plain'
    return (f'From: Alice <alice@example.com>\r\nTo: voce@gmail.com\r\n'
            f'Subject: {subject}\r\nDate: Sun, 13 Sep 2026 12:00:00 +0000\r\n'
            f'Message-ID: <message@example.com>\r\nContent-Type: text/{kind}; charset={charset}\r\n'
            f'\r\n{body}').encode('utf-8')


class FakeIMAP:
    def __init__(self, messages=None):
        self.messages = messages or {'101': email_bytes()}
        self.calls = []
        self.reported_size = None
        self.login_error = None
        self.logout_called = False

    def login(self, email, password):
        self.calls.append(('login', email))
        if self.login_error:
            raise self.login_error
        return 'OK', [b'Logged in']

    def select(self, mailbox, readonly=False):
        self.calls.append(('select', mailbox, readonly))
        return 'OK', [str(len(self.messages)).encode()]

    def response(self, code):
        return code, [b'123456']

    def fetch(self, sequence_set, items):
        self.calls.append(('fetch', sequence_set, items))
        assert items == '(UID)', 'Only bounded UID discovery is allowed'
        first, last = map(int, sequence_set.split(':'))
        uids = list(self.messages)
        return 'OK', [f'{i} (UID {uids[i-1]})'.encode() for i in range(first, last + 1)]

    def uid(self, command, uid, items):
        self.calls.append(('uid', command, uid, items))
        assert command.lower() == 'fetch', 'IMAP search/send is not allowed'
        raw = self.messages.get(str(uid))
        if raw is None:
            return 'OK', [None]
        if items == '(RFC822.SIZE)':
            size = self.reported_size if self.reported_size is not None else len(raw)
            return 'OK', [f'1 (UID {uid} RFC822.SIZE {size})'.encode()]
        assert 'BODY.PEEK[' in items, 'Fetch must not mark a message read'
        if 'HEADER' in items:
            raw = raw.split(b'\r\n\r\n', 1)[0] + b'\r\n\r\n'
        partial = re.search(r'<0\.(\d+)>', items)
        if partial:
            raw = raw[:int(partial.group(1))]
        return 'OK', [(f'1 (UID {uid} BODY[] {{{len(raw)}}}'.encode(), raw), b')']

    def logout(self):
        self.logout_called = True
        return 'BYE', [b'Logged out']


class MailToolsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(MailTools, 'MailTools implementation is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.accounts_path = self.root / 'accounts.json'
        self.accounts = {
            'gmail': {'email': 'voce@gmail.com', 'password': 'test-secret', 'imap_host': 'imap.gmail.test', 'imap_port': 993},
            'workmail': {'email': 'voce@empresa.com', 'password': 'test-secret', 'imap_host': 'imap.work.test', 'imap_port': 993},
        }
        self.accounts_path.write_text(json.dumps(self.accounts), encoding='utf-8')
        self.imap = FakeIMAP()
        self.connections = []

    def factory(self, host, port, **kwargs):
        self.connections.append((host, port))
        return self.imap

    def mail(self, profile='gmail'):
        return MailTools(profile, self.accounts_path, self.root / 'data', imap_factory=self.factory)

    def test_profile_uses_fixed_account_and_readonly_peek(self):
        result = self.mail('easysapers').list_messages()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['account'], 'workmail')
        self.assertEqual(result['messages'][0]['uid'], '101')
        self.assertEqual(result['messages'][0]['subject'], 'Invoice')
        self.assertIn(('login', 'voce@empresa.com'), self.imap.calls)
        self.assertIn(('select', 'INBOX', True), self.imap.calls)
        self.assertTrue(any('BODY.PEEK[HEADER' in call[-1] for call in self.imap.calls if call[0] == 'uid'))
        self.assertTrue(self.imap.logout_called)
        json.dumps(result)

    def test_invalid_profile_uid_and_limit_rejected_before_io(self):
        for profile in ('other', 'workmail', None):
            self.assertEqual(self.mail(profile).list_messages()['status'], 'error')
        for uid in ('1:*', '101) BODY[]', 0, -1, True, '0001', '4294967296'):
            self.assertEqual(self.mail().read_message(uid)['status'], 'error')
        for limit in (0, 31, True, '10'):
            self.assertEqual(self.mail().list_messages(limit)['status'], 'error')
        self.assertEqual(self.connections, [])

    def test_wrong_email_rejected_before_imap(self):
        self.accounts['gmail']['email'] = 'someoneelse@example.com'
        self.accounts_path.write_text(json.dumps(self.accounts), encoding='utf-8')
        result = self.mail().list_messages()
        self.assertEqual(result['error']['code'], 'account_mismatch')
        self.assertEqual(self.connections, [])

    def test_read_unknown_charset_and_uidvalidity(self):
        self.imap.messages['101'] = email_bytes(body='Olá mundo', charset='invented-charset')
        result = self.mail().read_message('101')
        self.assertEqual(result['body'], 'Olá mundo')
        self.assertFalse(result['truncated'])
        self.assertEqual(result['uidvalidity'], '123456')
        self.assertIn(('uid', 'fetch', '101', '(RFC822.SIZE)'), self.imap.calls)
        self.assertTrue(any('BODY.PEEK[]' in call[-1] for call in self.imap.calls if call[0] == 'uid'))

    def test_body_is_bounded_and_html_scripts_are_omitted(self):
        self.imap.messages['101'] = email_bytes(body='<p>Visible</p><script>hidden</script><style>secret</style><p>&amp; More</p>', html=True)
        result = self.mail().read_message('101')
        self.assertIn('Visible', result['body'])
        self.assertIn('& More', result['body'])
        self.assertNotIn('hidden', result['body'])
        self.assertNotIn('secret', result['body'])
        self.imap.messages['101'] = email_bytes(body='x' * 13000)
        result = self.mail().read_message('101')
        self.assertEqual(len(result['body']), 12000)
        self.assertTrue(result['truncated'])

    def test_oversized_message_rejected_before_body_fetch(self):
        self.imap.reported_size = 2 * 1024 * 1024 + 1
        result = self.mail().read_message('101')
        self.assertEqual(result['error']['code'], 'message_too_large')
        self.assertFalse(any('BODY.PEEK[]' in call[-1] for call in self.imap.calls if call[0] == 'uid'))

    def test_actual_payload_size_checked_even_if_server_size_is_wrong(self):
        self.imap.messages['101'] = email_bytes(body='x' * (2 * 1024 * 1024 + 10))
        self.imap.reported_size = 100
        self.assertEqual(self.mail().read_message('101')['error']['code'], 'message_too_large')

    def test_missing_uid_returns_clean_not_found(self):
        result = self.mail().read_message('999')
        self.assertEqual(result['error']['code'], 'message_not_found')
        self.assertTrue(self.imap.logout_called)

    def test_search_only_recent_100_headers_and_compares_locally(self):
        self.imap.messages = {str(i): email_bytes(subject='Report' if i in (1, 149) else 'Other') for i in range(1, 151)}
        result = self.mail().search_messages('rEpOrT', 10)
        self.assertEqual([item['uid'] for item in result['messages']], ['149'])
        self.assertEqual(result['scope']['scanned'], 100)
        self.assertTrue(result['scope']['limited'])
        self.assertIn('100', result['notice'])
        self.assertIn(('fetch', '51:150', '(UID)'), self.imap.calls)
        self.assertFalse(any(call[0] == 'uid' and call[1] != 'fetch' for call in self.imap.calls))
        self.assertFalse(any('BODY.PEEK[]' in call[-1] for call in self.imap.calls if call[0] == 'uid'))
        self.assertEqual(self.mail().search_messages('" OR ALL')['messages'], [])

    def test_list_fetches_only_requested_recent_messages(self):
        self.imap.messages = {str(i): email_bytes(subject=f'Subject {i}') for i in range(1, 51)}
        result = self.mail().list_messages(2)
        self.assertEqual([item['uid'] for item in result['messages']], ['50', '49'])
        self.assertIn(('fetch', '49:50', '(UID)'), self.imap.calls)

    def test_empty_inbox_returns_no_messages(self):
        self.imap.messages = {}
        self.assertEqual(self.mail().list_messages()['messages'], [])
        self.assertFalse(any(call[0] == 'fetch' for call in self.imap.calls))

    def test_draft_is_local_utf8_and_never_connects(self):
        result = self.mail('easysapers').save_draft('alice@example.com', 'Olá', 'Reunião amanhã')
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['stored_locally'])
        self.assertFalse(result['sent'])
        draft = result['draft']
        self.assertTrue(draft['stored_locally'])
        self.assertFalse(draft['sent'])
        path = Path(draft['path'])
        self.assertEqual(path.parent, self.root / 'data' / 'drafts')
        saved = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(saved['body'], 'Reunião amanhã')
        self.assertEqual(saved['from'], 'voce@empresa.com')
        self.assertEqual(saved['account'], 'workmail')
        self.assertEqual(self.connections, [])
        if os.name != 'nt':
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_draft_validation_rejects_header_injection_and_empty_body(self):
        for to, subject, body in [('a@example.com\r\nBcc: b@example.com', 'Hello', 'Body'),
                                  ('a@example.com', 'Hello\nBcc: b@example.com', 'Body'),
                                  ('not-an-email', 'Hello', 'Body'),
                                  ('a@example.com', 'Hello', '   ')]:
            self.assertEqual(self.mail().save_draft(to, subject, body)['status'], 'error')
        self.assertFalse((self.root / 'data' / 'drafts').exists())
        self.assertEqual(self.connections, [])

    def test_safe_failure_does_not_expose_credentials_or_server_text(self):
        self.imap.login_error = imaplib.IMAP4.error('server raw contains test-secret')
        result = self.mail().list_messages()
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error']['code'], 'mail_unavailable')
        self.assertNotIn('test-secret', json.dumps(result))
        self.assertNotIn('server raw', json.dumps(result))
        self.assertTrue(self.imap.logout_called)


if __name__ == '__main__':
    unittest.main()
