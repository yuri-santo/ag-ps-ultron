"""Owner-scoped durable profile choices and immutable per-message snapshots."""
import json
import os
from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager

try:
    from .contract import require
except ImportError:
    from contract import require


ALIASES = {'default': 'ultron', 'celebro': 'cerebro', 'creg': 'greg', 'pinky': 'pink'}


def parse_command(text, profiles, bot_username=''):
    match = re.fullmatch(r'/([a-zA-Z_][a-zA-Z_0-9]*)(?:@([a-zA-Z_0-9]+))?(?:\s+([\s\S]*))?', text.strip())
    if not match or (match[2] and match[2].lower() != bot_username.lower()):
        return None
    name = ALIASES.get(match[1].lower(), match[1].lower())
    if name not in set(profiles) | {'ultron', 'perfil', 'profile', 'perfis'}:
        return None
    return name, (match[3] or '').strip()


class Selection:
    def __init__(self, home, profiles):
        self.home = Path(home).resolve()
        self.profiles = set(profiles) | {'ultron'}
        self.path = self.home / 'topic-queue' / 'profiles.db'

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.close(fd)
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS choices(scope TEXT PRIMARY KEY, profile TEXT, message_id INTEGER)')
                db.execute('CREATE TABLE IF NOT EXISTS snapshots(scope TEXT, message_id TEXT, profile TEXT, '
                           'PRIMARY KEY(scope,message_id))')
                db.execute('CREATE TABLE IF NOT EXISTS choice_history(scope TEXT, message_id INTEGER, profile TEXT, '
                           'PRIMARY KEY(scope,message_id))')
                db.execute('INSERT OR IGNORE INTO choice_history SELECT scope,message_id,profile FROM choices')
                yield db
        finally:
            db.close()

    def available(self, profile):
        directory = self.home if profile == 'ultron' else self.home / 'profiles' / profile
        return profile in self.profiles and directory.resolve() == directory and all(
            (directory / name).is_file() for name in ('config.yaml', 'SOUL.md'))

    def current(self, scope):
        with self.connect() as db:
            row = db.execute('SELECT profile FROM choices WHERE scope=?', (scope.key(),)).fetchone()
        # An unavailable explicit choice must never silently borrow another identity.
        return row[0] if row else 'ultron'

    def choose(self, scope, profile, message_id):
        require(self.available(profile), 'Profile unavailable')
        require(str(message_id).isdigit(), 'Native Telegram message ID required')
        with self.connect() as db:
            previous = db.execute('SELECT profile FROM choice_history WHERE scope=? AND message_id=?',
                                  (scope.key(), int(message_id))).fetchone()
            require(previous is None or previous[0] == profile, 'Profile command identity conflict')
            db.execute('INSERT OR IGNORE INTO choice_history VALUES(?,?,?)',
                       (scope.key(), int(message_id), profile))
            db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?)', (scope.key(), str(message_id), profile))
            db.execute('INSERT INTO choices VALUES(?,?,?) ON CONFLICT(scope) DO UPDATE SET '
                       'profile=excluded.profile,message_id=excluded.message_id '
                       'WHERE excluded.message_id>choices.message_id', (scope.key(), profile, int(message_id)))
        return self.current(scope)

    def snapshot(self, scope, message_id):
        with self.connect() as db:
            row = db.execute('SELECT profile FROM snapshots WHERE scope=? AND message_id=?',
                             (scope.key(), str(message_id))).fetchone()
            if row:
                return row[0]
            if str(message_id).isdigit():
                choice = db.execute('SELECT profile FROM choice_history WHERE scope=? AND message_id<=? '
                                    'ORDER BY message_id DESC LIMIT 1', (scope.key(), int(message_id))).fetchone()
            else:
                choice = db.execute('SELECT profile FROM choices WHERE scope=?', (scope.key(),)).fetchone()
            profile = choice[0] if choice else 'ultron'
            require(self.available(profile), 'Selected profile unavailable')
            db.execute('INSERT INTO snapshots VALUES(?,?,?)', (scope.key(), str(message_id), profile))
            return profile

    def pinned(self, scope, message_id):
        with self.connect() as db:
            row = db.execute('SELECT profile FROM snapshots WHERE scope=? AND message_id=?',
                             (scope.key(), str(message_id))).fetchone()
            return row[0] if row else None
