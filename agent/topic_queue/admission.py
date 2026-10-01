"""Private metadata for topic admission; no gateway or scheduler registration."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

try:
    from .contract import QueueError, acyclic, canonical, intervals, nonempty, require, validate_plan
except ImportError:
    from contract import QueueError, acyclic, canonical, intervals, nonempty, require, validate_plan


@dataclass(frozen=True)
class Scope:
    platform: str
    account_id: str
    owner_id: str
    chat_id: str
    thread_id: str = ''

    def key(self):
        require(all(nonempty(getattr(self, name)) for name in
                    ('platform', 'account_id', 'owner_id', 'chat_id')), 'Invalid origin scope')
        require(isinstance(self.thread_id, str), 'Invalid thread scope')
        return canonical(asdict(self))


SCHEMA = (
    'CREATE TABLE IF NOT EXISTS ingress ('
    'id TEXT PRIMARY KEY, scope TEXT NOT NULL, message_id TEXT NOT NULL, payload TEXT NOT NULL,'
    'plan TEXT, result TEXT, UNIQUE(scope, message_id))',
    'CREATE TABLE IF NOT EXISTS topics ('
    'id TEXT PRIMARY KEY, scope TEXT NOT NULL, current_version INTEGER NOT NULL)',
    'CREATE TABLE IF NOT EXISTS versions ('
    'topic_id TEXT NOT NULL REFERENCES topics(id), version INTEGER NOT NULL, '
    'ingress_id TEXT NOT NULL REFERENCES ingress(id), contract TEXT NOT NULL, '
    'valid INTEGER NOT NULL, invalid_reason TEXT, PRIMARY KEY(topic_id, version))',
    'CREATE TABLE IF NOT EXISTS card_intents ('
    'topic_id TEXT NOT NULL, version INTEGER NOT NULL, correlation TEXT UNIQUE NOT NULL, '
    'PRIMARY KEY(topic_id, version), FOREIGN KEY(topic_id, version) REFERENCES versions(topic_id, version))',
    'CREATE TABLE IF NOT EXISTS delivery_references ('
    'scope TEXT NOT NULL, message_id TEXT NOT NULL, topic_id TEXT NOT NULL, version INTEGER NOT NULL, '
    'PRIMARY KEY(scope, message_id), FOREIGN KEY(topic_id, version) REFERENCES versions(topic_id, version))',
)


class TopicStore:
    def __init__(self, path, *, allowed_profiles):
        self.path = Path(path)
        self.allowed_profiles = frozenset(allowed_profiles)
        require(bool(self.allowed_profiles) and all(nonempty(x) for x in self.allowed_profiles),
                'A trusted profile allowlist is required')

    @contextmanager
    def _transaction(self):
        db = None
        try:
            # Dedicated private directory; never place this beside public artifacts.
            require(not self.path.is_symlink() and not self.path.parent.is_symlink(),
                    'Private storage cannot be a symlink')
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.path.parent, 0o700)
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            os.close(fd)
            os.chmod(self.path, 0o600)
            require(os.stat(self.path).st_mode & 0o777 == 0o600, 'Private storage permissions unavailable')
            db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            require(db.execute('PRAGMA user_version').fetchone()[0] in (0, 1),
                    'Unsupported private storage schema')
            for statement in SCHEMA:
                db.execute(statement)
            db.execute('PRAGMA user_version=1')
            yield db
            db.commit()
        except (OSError, sqlite3.Error) as exc:
            raise QueueError('Private storage unavailable; operation was not acknowledged') from exc
        finally:
            if db is not None:
                db.close()

    def admit(self, scope, message_id, text, *, request_spans, authorized, reply_to=None):
        """Call ONLY after native auth, pause, commands and approval handling.

        request_spans must come from trusted ingress handling, never model output.
        Return only after the FULL-synchronous transaction has committed.
        """
        require(authorized is True, 'Ingress is not authorized')
        origin = scope.key()
        require(nonempty(message_id) and nonempty(text), 'Message ID and text are required')
        require(reply_to is None or nonempty(reply_to), 'Invalid reply ID')
        spans = intervals(request_spans, text)
        payload = canonical(dict(text=text, request_spans=spans, reply_to=reply_to))
        with self._transaction() as db:
            previous = db.execute('SELECT id, payload FROM ingress WHERE scope=? AND message_id=?',
                                  (origin, message_id)).fetchone()
            if previous:
                require(previous['payload'] == payload, 'Conflicting ingress idempotency key')
                result = previous['id']
            else:
                result = uuid.uuid4().hex
                db.execute('INSERT INTO ingress(id, scope, message_id, payload) VALUES(?,?,?,?)',
                           (result, origin, message_id, payload))
        return result

    def pending(self, scope):
        origin = scope.key()
        with self._transaction() as db:
            result = []
            for row in db.execute('SELECT * FROM ingress WHERE scope=? AND plan IS NULL ORDER BY rowid',
                                  (origin,)).fetchall():
                payload = json.loads(row['payload'])
                reply = db.execute('SELECT topic_id FROM delivery_references WHERE scope=? AND message_id=?',
                                   (origin, payload['reply_to'])).fetchone()
                result.append(dict(id=row['id'], message_id=row['message_id'], **payload,
                                   reply_topic_id=reply['topic_id'] if reply else None))
        return result

    @staticmethod
    def _topic(db, origin, topic_id):
        row = db.execute('SELECT t.*, v.contract, v.valid, v.invalid_reason FROM topics t '
                         'JOIN versions v ON t.id=v.topic_id AND t.current_version=v.version '
                         'WHERE t.scope=? AND t.id=?', (origin, topic_id)).fetchone()
        require(row is not None, 'Unknown topic in origin scope')
        return dict(row)

    def get_topic(self, scope, topic_id):
        with self._transaction() as db:
            result = self._topic(db, scope.key(), topic_id)
            result['contract'] = json.loads(result['contract'])
            result['valid'] = bool(result['valid'])
        return result

    def revision_is_current(self, scope, topic_id, version):
        topic = self.get_topic(scope, topic_id)
        return type(version) is int and topic['current_version'] == version and topic['valid']

    def apply_plan(self, scope, ingress_id, value):
        """Validate and atomically persist a proposal; no native task is released."""
        origin = scope.key()
        encoded = canonical(value)
        # Snapshot model-owned input before validation to prevent caller mutation races.
        value = json.loads(encoded)
        with self._transaction() as db:
            ingress = db.execute('SELECT * FROM ingress WHERE id=? AND scope=?',
                                 (ingress_id, origin)).fetchone()
            require(ingress is not None, 'Unknown ingress in origin scope')
            if ingress['plan'] is not None:
                require(ingress['plan'] == encoded, 'Ingress already has a different accepted plan')
                return json.loads(ingress['result'])
            payload = json.loads(ingress['payload'])
            validate_plan(value, payload['text'], payload['request_spans'], self.allowed_profiles)
            if payload['reply_to'] is not None:
                reply = db.execute('SELECT topic_id FROM delivery_references WHERE scope=? AND message_id=?',
                                   (origin, payload['reply_to'])).fetchone()
                require(reply is not None, 'Unknown reply requires clarification')
                require(any(t['topic_id'] == reply['topic_id'] for t in value['topics']),
                        'Known reply must continue its topic')
            assigned = {}
            reopened = set()
            for topic in value['topics']:
                topic_id = topic['topic_id']
                version = 1
                if topic_id is not None:
                    current = self._topic(db, origin, topic_id)
                    require(current['current_version'] == topic['expected_version'], 'Stale topic version')
                    version = current['current_version'] + 1
                    reopened.add(topic_id)
                else:
                    topic_id = uuid.uuid4().hex
                assigned[topic['key']] = dict(topic_id=topic_id, version=version)

            # Dependency declarations are immutable version metadata, not a scheduler.
            graph = {}
            for row in db.execute('SELECT t.id, v.contract FROM topics t JOIN versions v '
                                  'ON t.id=v.topic_id AND t.current_version=v.version WHERE scope=?', (origin,)):
                graph[row['id']] = [d['topic_id'] for d in json.loads(row['contract'])['depends_on']]
            old_graph = dict(graph)
            contracts = {}
            for topic in value['topics']:
                assignment = assigned[topic['key']]
                contract = dict(title=topic['title'], profile=topic['profile'],
                                ingress_id=ingress_id, spans=topic['spans'],
                                depends_on=[assigned[key] for key in topic['depends_on']])
                contracts[assignment['topic_id']] = contract
                graph[assignment['topic_id']] = [d['topic_id'] for d in contract['depends_on']]
            acyclic(graph)
            affected = set(reopened)
            while True:
                children = {key for key, deps in old_graph.items() if any(d in affected for d in deps)}
                expanded = affected | children
                if expanded == affected:
                    break
                affected = expanded
            for topic_id in affected:
                reason = 'scope_revised' if topic_id in reopened else 'predecessor_reopened'
                db.execute('UPDATE versions SET valid=0, invalid_reason=? WHERE topic_id=? AND valid=1',
                           (reason, topic_id))
            result = []
            for assignment in assigned.values():
                topic_id, version = assignment['topic_id'], assignment['version']
                db.execute('INSERT INTO topics VALUES(?,?,?) ON CONFLICT(id) DO UPDATE '
                           'SET current_version=excluded.current_version', (topic_id, origin, version))
                db.execute('INSERT INTO versions VALUES(?,?,?,?,1,NULL)',
                           (topic_id, version, ingress_id, canonical(contracts[topic_id])))
                correlation = hashlib.sha256(canonical([origin, topic_id, version]).encode()).hexdigest()
                db.execute('INSERT INTO card_intents VALUES(?,?,?)', (topic_id, version, correlation))
                result.append(assignment)
            db.execute('UPDATE ingress SET plan=?, result=? WHERE id=?',
                       (encoded, canonical(result), ingress_id))
        return result

    def card_intents(self, scope):
        with self._transaction() as db:
            rows = db.execute('SELECT i.*, v.valid FROM card_intents i JOIN topics t ON t.id=i.topic_id '
                              'JOIN versions v ON v.topic_id=i.topic_id AND v.version=i.version '
                              'WHERE t.scope=? ORDER BY i.rowid', (scope.key(),)).fetchall()
            result = [dict(row, valid=bool(row['valid']), native_card_id=None, released=False) for row in rows]
        return result

    def record_delivery_reference(self, scope, topic_id, version, message_id):
        """Trusted receipt adapter ONLY: message_id must be an actual successful send.

        This records routing metadata, not proof of approval or a transport receipt.
        No model, gateway hook or worker is connected to this method.
        """
        origin = scope.key()
        require(nonempty(message_id) and type(version) is int and version > 0, 'Invalid delivery reference')
        with self._transaction() as db:
            self._topic(db, origin, topic_id)
            require(db.execute('SELECT 1 FROM versions WHERE topic_id=? AND version=?',
                               (topic_id, version)).fetchone() is not None, 'Unknown delivered version')
            previous = db.execute('SELECT * FROM delivery_references WHERE scope=? AND message_id=?',
                                  (origin, message_id)).fetchone()
            if previous:
                require(previous['topic_id'] == topic_id and previous['version'] == version,
                        'Delivered message already belongs to a different topic/version')
            else:
                db.execute('INSERT INTO delivery_references VALUES(?,?,?,?)',
                           (origin, message_id, topic_id, version))
