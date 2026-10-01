"""Private approval/outbox metadata, not a scheduler or a registered tool.

The native proof bridge is still pending. A trusted host must inject readers
execution(run_id), review(review_id), policy(scope, topic_id, version, contract),
control(scope, topic_id, version), and outcome(receipt_id). Reader records must
come from verified native execution/roster/transport state, never model claims.
In particular served_identity must identify the actual provider/model, not a
persona alias. No CLI, gateway hook, worker release or real transport is wired.

The formatter receives the real author's prefix plus unchanged candidate text;
its final text parts are frozen BEFORE review. This initial contract supports
text only. Evidence hashes do not imply support for sending attachments.
"""
from contextlib import contextmanager
import hashlib
import json
import os
import uuid

try:
    from .contract import QueueError, canonical, nonempty, require
except ImportError:
    from contract import QueueError, canonical, nonempty, require


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _hash(value):
    return _digest(canonical(value))


def _sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


class _ProofUnavailable(QueueError):
    """A host reader failed; preserve the approved work for a later attempt."""


class _ControlBlocked(QueueError):
    def __init__(self, state):
        self.state = state
        super().__init__('Host control blocks approval/delivery: ' + str(state))


SCHEMA = (
    'CREATE TABLE IF NOT EXISTS delivery_prepared ('
    'id TEXT PRIMARY KEY, scope TEXT NOT NULL, topic_id TEXT NOT NULL, version INTEGER NOT NULL, '
    'payload TEXT NOT NULL, FOREIGN KEY(topic_id, version) REFERENCES versions(topic_id, version))',
    'CREATE TABLE IF NOT EXISTS delivery_approvals ('
    'sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, '
    'prepared_id TEXT UNIQUE NOT NULL REFERENCES delivery_prepared(id), '
    'scope TEXT NOT NULL, topic_id TEXT NOT NULL, version INTEGER NOT NULL, manifest TEXT NOT NULL, '
    'UNIQUE(topic_id, version))',
    'CREATE TABLE IF NOT EXISTS delivery_outbox ('
    'approval_id TEXT PRIMARY KEY REFERENCES delivery_approvals(id), state TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS delivery_parts ('
    'approval_id TEXT NOT NULL REFERENCES delivery_outbox(approval_id), part_index INTEGER NOT NULL, '
    'state TEXT NOT NULL, attempt_id TEXT, receipt_id TEXT, message_id TEXT, '
    'PRIMARY KEY(approval_id, part_index))',
    'CREATE TABLE IF NOT EXISTS delivery_attempts ('
    'id TEXT PRIMARY KEY, approval_id TEXT NOT NULL, part_index INTEGER NOT NULL, '
    'scope TEXT NOT NULL, text_hash TEXT NOT NULL, state TEXT NOT NULL, '
    'receipt_id TEXT UNIQUE, receipt TEXT, message_id TEXT, UNIQUE(scope, message_id), '
    'FOREIGN KEY(approval_id, part_index) REFERENCES delivery_parts(approval_id, part_index))',
)


class Delivery:
    def __init__(self, store, *, proofs, formatter):
        self.store = store
        self.proofs = proofs
        self.formatter = formatter
        require(callable(formatter), 'Trusted formatter required')
        require(all(callable(getattr(proofs, name, None)) for name in
                    ('execution', 'review', 'policy', 'control', 'outcome')), 'Trusted proof readers required')

    @contextmanager
    def _transaction(self):
        with self.store._transaction() as db:
            for statement in SCHEMA:
                db.execute(statement)
            for table in ('delivery_prepared', 'delivery_approvals'):
                for operation in ('UPDATE', 'DELETE'):
                    db.execute(f'CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()} '
                               f'BEFORE {operation} ON {table} BEGIN '
                               "SELECT RAISE(ABORT, 'Approval evidence is immutable'); END")
            yield db

    @staticmethod
    def _read(reader, *args):
        try:
            return json.loads(canonical(reader(*args)))
        except Exception as exc:
            raise _ProofUnavailable('Trusted proof is unavailable or malformed') from exc

    def _active(self, scope, topic_id, version):
        state = self._read(self.proofs.control, scope, topic_id, version)
        if state != 'active':
            raise _ControlBlocked(state)

    def _current(self, db, scope, topic_id, version):
        require(type(version) is int and version > 0, 'Invalid topic version')
        current = self.store._topic(db, scope.key(), topic_id)
        require(current['current_version'] == version and current['valid'], 'Topic revision is stale or invalid')
        return json.loads(current['contract'])

    def _execution(self, db, scope, topic_id, version, run_id, contract):
        require(nonempty(run_id), 'Execution proof ID required')
        proof = self._read(self.proofs.execution, run_id)
        require(isinstance(proof, dict), 'Invalid execution proof')
        link = db.execute('SELECT * FROM card_links WHERE topic_id=? AND version=?',
                          (topic_id, version)).fetchone()
        require(link is not None and nonempty(link['native_card_id']), 'Native card is not reconciled')
        expected = dict(scope=scope.key(), topic_id=topic_id, version=version, run_id=run_id,
                        native_board=link['native_board'], native_card_id=link['native_card_id'],
                        profile=contract['profile'], contract_hash=_hash(contract))
        require(type(proof.get('version')) is int and
                all(proof.get(k) == v for k, v in expected.items()), 'Execution binding mismatch')
        require(proof.get('completed') is True and proof.get('model_review') == 'approved',
                'Execution is incomplete or model review is not approved')
        require(all(nonempty(proof.get(k)) for k in ('candidate', 'author', 'served_identity')),
                'Execution author, served identity and candidate required')
        require(proof.get('candidate_hash') == _digest(proof['candidate']), 'Candidate hash mismatch')
        require(isinstance(proof.get('evidence_hashes'), list) and
                all(_sha256(item) for item in proof['evidence_hashes']), 'Invalid evidence hashes')
        return proof

    def _policy(self, scope, topic_id, version, contract):
        policy = self._read(self.proofs.policy, scope, topic_id, version, contract)
        require(isinstance(policy, dict) and nonempty(policy.get('id')) and nonempty(policy.get('version')),
                'A versioned review policy is required')
        for field in ('required_competencies', 'required_reviewers'):
            require(isinstance(policy.get(field), list) and all(nonempty(x) for x in policy[field]),
                    'Invalid review policy requirements')
        require(bool(policy['required_competencies']), 'Review policy has no competencies')
        roster = policy.get('reviewers')
        require(isinstance(roster, dict) and bool(roster) and
                all(nonempty(k) and isinstance(v, list) and all(nonempty(x) for x in v)
                    for k, v in roster.items()), 'Trusted reviewer competency roster required')
        require(set(policy['required_reviewers']) <= set(roster), 'Mandatory reviewer absent from roster')
        return policy

    def _dependencies(self, db, scope, contract):
        result = []
        for dependency in contract['depends_on']:
            self._current(db, scope, **dependency)
            self._active(scope, **dependency)
            row = db.execute('SELECT id FROM delivery_approvals WHERE scope=? AND topic_id=? AND version=?',
                             (scope.key(), dependency['topic_id'], dependency['version'])).fetchone()
            require(row is not None, 'Dependency has no approval')
            self._approval(db, scope, row['id'])
            result.append(dict(**dependency, approval_id=row['id']))
        return result

    def prepare(self, scope, topic_id, version, *, run_id):
        """Trusted host only: freeze exact wire text and binding before review."""
        with self._transaction() as db:
            contract = self._current(db, scope, topic_id, version)
            self._active(scope, topic_id, version)
            execution = self._execution(db, scope, topic_id, version, run_id, contract)
            prefix = execution['author'] + ': '
            parts = self._read(self.formatter, prefix + execution['candidate'])
            require(isinstance(parts, list) and bool(parts) and all(nonempty(x) for x in parts),
                    'Formatter must return nonempty final text parts')
            require(parts[0].startswith(prefix), 'Formatter must preserve the real author prefix')
            payload = dict(scope=scope.key(), topic_id=topic_id, version=version, execution=execution,
                           contract_hash=_hash(contract), candidate_hash=execution['candidate_hash'],
                           parts=parts, delivery_hash=_hash(parts),
                           policy=self._policy(scope, topic_id, version, contract),
                           dependencies=self._dependencies(db, scope, contract))
            prepared_id = _hash(payload)
            db.execute('INSERT OR IGNORE INTO delivery_prepared VALUES(?,?,?,?,?)',
                       (prepared_id, scope.key(), topic_id, version, canonical(payload)))
        return dict(id=prepared_id, **payload)

    def _prepared(self, db, scope, prepared_id):
        row = db.execute('SELECT * FROM delivery_prepared WHERE id=? AND scope=?',
                         (prepared_id, scope.key())).fetchone()
        require(row is not None, 'Unknown prepared result in scope')
        payload = json.loads(row['payload'])
        require(_hash(payload) == prepared_id, 'Prepared result hash mismatch')
        require(payload['scope'] == scope.key() and payload['topic_id'] == row['topic_id']
                and payload['version'] == row['version'], 'Prepared source binding mismatch')
        contract = self._current(db, scope, payload['topic_id'], payload['version'])
        require(payload['contract_hash'] == _hash(contract), 'Prepared contract mismatch')
        execution = self._execution(db, scope, payload['topic_id'], payload['version'],
                                    payload['execution']['run_id'], contract)
        require(execution == payload['execution'], 'Execution proof changed after preparation')
        require(self._policy(scope, payload['topic_id'], payload['version'], contract) == payload['policy'],
                'Review policy changed after preparation')
        require(self._dependencies(db, scope, contract) == payload['dependencies'], 'Dependency approval changed')
        require(payload['candidate_hash'] == execution['candidate_hash']
                and payload['delivery_hash'] == _hash(payload['parts']), 'Delivery hash mismatch')
        return payload

    def _reviews(self, prepared_id, payload, review_ids):
        require(isinstance(review_ids, (list, tuple)) and all(nonempty(x) for x in review_ids),
                'Review proof IDs required')
        require(len(set(review_ids)) == len(review_ids), 'Duplicate review proof')
        execution, policy = payload['execution'], payload['policy']
        found, profiles, competencies, runs = [], set(), set(), set()
        independent = False
        for proof_id in sorted(review_ids):
            proof = self._read(self.proofs.review, proof_id)
            require(isinstance(proof, dict) and proof.get('id') == proof_id
                    and proof.get('prepared_id') == prepared_id and proof.get('binding_hash') == prepared_id,
                    'Review binding mismatch')
            require(proof.get('completed') is True and proof.get('verdict') == 'approved',
                    'Review is incomplete or rejected')
            profile = proof.get('profile')
            require(profile in policy['reviewers'] and profile not in profiles, 'Invalid reviewer profile')
            require(nonempty(proof.get('run_id')) and proof['run_id'] != execution['run_id']
                    and proof['run_id'] not in runs and nonempty(proof.get('served_identity')),
                    'Invalid review execution identity')
            profiles.add(profile)
            runs.add(proof['run_id'])
            competencies.update(policy['reviewers'][profile])
            independent |= (profile != execution['profile']
                            and proof['served_identity'] != execution['served_identity'])
            found.append(proof)
        require(set(policy['required_competencies']) <= competencies, 'Missing required competency approval')
        require(set(policy['required_reviewers']) <= profiles, 'Missing mandatory reviewer approval')
        require(independent, 'An independent served reviewer is required')
        return found

    def approve(self, scope, prepared_id, review_ids):
        """IDs-only host boundary; reviewers cannot supply authoritative booleans."""
        require(nonempty(prepared_id), 'Prepared result ID required')
        with self._transaction() as db:
            payload = self._prepared(db, scope, prepared_id)
            self._active(scope, payload['topic_id'], payload['version'])
            manifest = dict(prepared_id=prepared_id, scope=scope.key(), topic_id=payload['topic_id'],
                            version=payload['version'], reviews=self._reviews(prepared_id, payload, review_ids))
            approval_id = _hash(manifest)
            existing = db.execute('SELECT id FROM delivery_approvals WHERE topic_id=? AND version=?',
                                  (payload['topic_id'], payload['version'])).fetchone()
            require(existing is None or existing['id'] == approval_id, 'Revision already has another approval')
            db.execute('INSERT OR IGNORE INTO delivery_approvals '
                       '(id, prepared_id, scope, topic_id, version, manifest) VALUES(?,?,?,?,?,?)',
                       (approval_id, prepared_id, scope.key(), payload['topic_id'], payload['version'],
                        canonical(manifest)))
            db.execute('INSERT OR IGNORE INTO delivery_outbox VALUES(?,?)', (approval_id, 'pending'))
            db.executemany('INSERT OR IGNORE INTO delivery_parts '
                           '(approval_id, part_index, state) VALUES(?,?,?)',
                           [(approval_id, index, 'pending') for index in range(len(payload['parts']))])
        return dict(id=approval_id, **manifest)

    def _approval(self, db, scope, approval_id):
        row = db.execute('SELECT * FROM delivery_approvals WHERE id=? AND scope=?',
                         (approval_id, scope.key())).fetchone()
        require(row is not None, 'Unknown approval in scope')
        manifest = json.loads(row['manifest'])
        require(_hash(manifest) == approval_id and manifest['scope'] == scope.key()
                and manifest['prepared_id'] == row['prepared_id']
                and manifest['topic_id'] == row['topic_id'] and manifest['version'] == row['version'],
                'Approval manifest binding mismatch')
        payload = self._prepared(db, scope, manifest['prepared_id'])
        require(payload['topic_id'] == manifest['topic_id'] and payload['version'] == manifest['version'],
                'Approval topic binding mismatch')
        current = self._reviews(manifest['prepared_id'], payload, [r['id'] for r in manifest['reviews']])
        require(current == manifest['reviews'], 'Review proof changed after approval')
        return payload

    @contextmanager
    def _scope_lock(self, scope):
        """WSL/Linux host lock; retain its inode so competing opens share it."""
        import fcntl

        path = self.store.path
        require(not path.is_symlink() and not path.parent.is_symlink(),
                'Private storage cannot be a symlink')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        lock_path = path.with_name(path.name + '.' + _digest(scope.key()) + '.delivery.lock')
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    @staticmethod
    def _parts(db, approval_id):
        return db.execute('SELECT * FROM delivery_parts WHERE approval_id=? ORDER BY part_index',
                          (approval_id,)).fetchall()

    @staticmethod
    def _state(db, approval_id, state):
        db.execute('UPDATE delivery_outbox SET state=? WHERE approval_id=?', (state, approval_id))

    def _refresh(self, db, approval_id):
        states = {part['state'] for part in self._parts(db, approval_id)}
        previous = db.execute('SELECT state FROM delivery_outbox WHERE approval_id=?',
                              (approval_id,)).fetchone()['state']
        if states == {'sent'}:
            state = 'sent'
        elif 'uncertain' in states or 'sending' in states:
            state = 'uncertain'
        elif previous == 'invalid' or 'invalid' in states:
            state = 'invalid'
        elif 'deferred' in states:
            state = 'deferred'
        else:
            state = 'pending'
        self._state(db, approval_id, state)
        return state

    def _guard(self, db, scope, approval_id):
        try:
            payload = self._approval(db, scope, approval_id)
            self._active(scope, payload['topic_id'], payload['version'])
            return 'ready', payload
        except _ProofUnavailable:
            return 'blocked', None
        except _ControlBlocked as exc:
            if exc.state != 'cancelled':
                return 'blocked', None
        except QueueError:
            pass
        db.execute("UPDATE delivery_parts SET state='invalid' WHERE approval_id=? "
                   "AND state IN ('pending','deferred')", (approval_id,))
        self._state(db, approval_id, 'invalid')
        return 'invalid', None

    def _next(self, db, scope):
        rows = db.execute('SELECT a.id, o.state, '
                          "EXISTS(SELECT 1 FROM delivery_parts p WHERE p.approval_id=a.id "
                          "AND p.state IN ('sent','sending','uncertain')) AS started "
                          'FROM delivery_approvals a JOIN delivery_outbox o ON o.approval_id=a.id '
                          "WHERE a.scope=? AND o.state NOT IN ('sent','invalid') "
                          'ORDER BY started DESC, a.sequence', (scope.key(),)).fetchall()
        blocked = False
        for row in rows:
            status, _ = self._guard(db, scope, row['id'])
            if status == 'invalid':
                continue
            if row['state'] == 'uncertain':
                blocked = True
                # Preserve an unfinished multipart group, not a global barrier
                # for a single/final part whose receipt still needs reconciling.
                if any(part['state'] in ('pending', 'deferred') for part in self._parts(db, row['id'])):
                    return 'blocked', row['id']
                continue
            if status == 'blocked' or row['state'] == 'deferred':
                blocked = True
                if row['started']:
                    return 'blocked', row['id']
                continue
            return 'ready', row['id']
        return ('blocked' if blocked else 'empty'), None

    def _recover(self, db, scope):
        # Only the scope-lock owner may conclude a previous sender has stopped.
        attempts = db.execute("SELECT * FROM delivery_attempts WHERE scope=? AND state='sending'",
                              (scope.key(),)).fetchall()
        for attempt in attempts:
            db.execute("UPDATE delivery_attempts SET state='uncertain' WHERE id=?", (attempt['id'],))
            db.execute("UPDATE delivery_parts SET state='uncertain' WHERE attempt_id=? "
                       "AND state='sending'", (attempt['id'],))
            self._state(db, attempt['approval_id'], 'uncertain')

    def _outcome(self, scope, attempt, receipt_id):
        require(nonempty(receipt_id), 'Transport receipt ID required')
        proof = self._read(self.proofs.outcome, receipt_id)
        expected = dict(id=receipt_id, attempt_id=attempt['id'], scope=scope.key(),
                        text_hash=attempt['text_hash'])
        require(isinstance(proof, dict) and all(proof.get(k) == v for k, v in expected.items()),
                'Transport receipt binding mismatch')
        require(proof.get('status') in ('sent', 'not_sent'), 'Transport outcome is uncertain')
        require(nonempty(proof.get('message_id')) if proof['status'] == 'sent'
                else proof.get('message_id') is None, 'Contradictory transport message ID')
        return proof

    def _record(self, db, scope, attempt, proof, *, retry=False):
        approval_id, index = attempt['approval_id'], attempt['part_index']
        require(attempt['receipt'] is None or attempt['receipt'] == canonical(proof),
                'A confirmed transport outcome cannot change')
        existing = db.execute('SELECT id FROM delivery_attempts WHERE receipt_id=? OR '
                              '(scope=? AND message_id=?)',
                              (proof['id'], scope.key(), proof['message_id'])).fetchall()
        require(all(row['id'] == attempt['id'] for row in existing), 'Receipt already belongs to another part')
        if proof['status'] == 'sent':
            approval = db.execute('SELECT topic_id, version FROM delivery_approvals WHERE id=?',
                                  (approval_id,)).fetchone()
            reference = db.execute('SELECT topic_id, version FROM delivery_references '
                                   'WHERE scope=? AND message_id=?',
                                   (scope.key(), proof['message_id'])).fetchone()
            require(reference is None or dict(reference) == dict(approval), 'Reply reference conflicts')
            db.execute('INSERT OR IGNORE INTO delivery_references VALUES(?,?,?,?)',
                       (scope.key(), proof['message_id'], approval['topic_id'], approval['version']))
            state = 'sent'
        else:
            state = 'pending' if retry else 'deferred'
            if db.execute('SELECT state FROM delivery_outbox WHERE approval_id=?',
                          (approval_id,)).fetchone()['state'] == 'invalid':
                state = 'invalid'
        db.execute('UPDATE delivery_attempts SET state=?, receipt_id=?, receipt=?, message_id=? WHERE id=?',
                   (proof['status'], proof['id'], canonical(proof), proof['message_id'], attempt['id']))
        db.execute('UPDATE delivery_parts SET state=?, receipt_id=?, message_id=? '
                   'WHERE approval_id=? AND part_index=?',
                   (state, proof['id'], proof['message_id'], approval_id, index))
        return self._refresh(db, approval_id)

    def dispatch_next(self, scope, send):
        """Host-only sender(scope, attempt_id, frozen_text) returns a receipt ID.

        The host must bound transport I/O with a timeout and must not retry a
        possibly sent request. It must coordinate control updates with the same
        private transaction lock, and must not write this database from send().
        All parts retain the scope lock; each send holds the revision transaction.
        """
        require(callable(send), 'Trusted bounded transport required')
        with self._scope_lock(scope) as acquired:
            if not acquired:
                return dict(status='busy')
            with self._transaction() as db:
                self._recover(db, scope)
                status, approval_id = self._next(db, scope)
            if status != 'ready':
                return dict(status=status)
            while True:
                with self._transaction() as db:
                    status, payload = self._guard(db, scope, approval_id)
                    if status != 'ready':
                        return dict(status=status, approval_id=approval_id)
                    part = next((p for p in self._parts(db, approval_id) if p['state'] != 'sent'), None)
                    if part is None:
                        self._state(db, approval_id, 'sent')
                        return dict(status='sent', approval_id=approval_id)
                    if part['state'] != 'pending':
                        return dict(status='blocked', approval_id=approval_id)
                    text = payload['parts'][part['part_index']]
                    attempt_id = uuid.uuid4().hex
                    db.execute('INSERT INTO delivery_attempts '
                               '(id, approval_id, part_index, scope, text_hash, state) VALUES(?,?,?,?,?,?)',
                               (attempt_id, approval_id, part['part_index'], scope.key(), _digest(text), 'sending'))
                    db.execute("UPDATE delivery_parts SET state='sending', attempt_id=?, "
                               'receipt_id=NULL, message_id=NULL WHERE approval_id=? AND part_index=?',
                               (attempt_id, approval_id, part['part_index']))
                    self._state(db, approval_id, 'sending')
                # The send intent above is durable before any possible external effect.
                with self._transaction() as db:
                    status, _ = self._guard(db, scope, approval_id)
                    if status != 'ready':
                        db.execute("UPDATE delivery_attempts SET state='aborted' WHERE id=?", (attempt_id,))
                        db.execute('UPDATE delivery_parts SET state=? WHERE attempt_id=?',
                                   ('invalid' if status == 'invalid' else 'pending', attempt_id))
                        self._refresh(db, approval_id)
                        return dict(status=status, approval_id=approval_id)
                    attempt = db.execute('SELECT * FROM delivery_attempts WHERE id=?', (attempt_id,)).fetchone()
                    db.execute('SAVEPOINT delivery_receipt')
                    try:
                        proof = self._outcome(scope, attempt, send(scope, attempt_id, text))
                        state = self._record(db, scope, attempt, proof)
                    except Exception:
                        db.execute('ROLLBACK TO delivery_receipt')
                        db.execute('RELEASE delivery_receipt')
                        db.execute("UPDATE delivery_attempts SET state='uncertain' WHERE id=?", (attempt_id,))
                        db.execute("UPDATE delivery_parts SET state='uncertain' WHERE attempt_id=?", (attempt_id,))
                        self._state(db, approval_id, 'uncertain')
                        return dict(status='uncertain', approval_id=approval_id)
                    db.execute('RELEASE delivery_receipt')
                    if state in ('sent', 'deferred'):
                        return dict(status=state, approval_id=approval_id)

    def _inspect(self, db, scope, approval_id):
        row = db.execute('SELECT o.* FROM delivery_outbox o JOIN delivery_approvals a '
                         'ON a.id=o.approval_id WHERE a.scope=? AND a.id=?',
                         (scope.key(), approval_id)).fetchone()
        require(row is not None, 'Unknown delivery in scope')
        attempts = [dict(item) for item in db.execute('SELECT * FROM delivery_attempts '
                                                     'WHERE approval_id=? ORDER BY rowid', (approval_id,))]
        for attempt in attempts:
            attempt['receipt'] = json.loads(attempt['receipt']) if attempt['receipt'] else None
        return dict(row, parts=[dict(part) for part in self._parts(db, approval_id)], attempts=attempts)

    def inspect(self, scope, approval_id):
        """Read durable local state without treating an active send as a crash."""
        require(nonempty(approval_id), 'Approval ID required')
        with self._transaction() as db:
            return self._inspect(db, scope, approval_id)

    def reconcile(self, scope, approval_id, part_index, receipt_id):
        """Host-only proof lookup; never sends or accepts caller-supplied status."""
        require(nonempty(approval_id) and nonempty(receipt_id), 'Approval and receipt IDs required')
        require(type(part_index) is int and part_index >= 0, 'Invalid part index')
        with self._scope_lock(scope) as acquired:
            if not acquired:
                return dict(status='busy')
            with self._transaction() as db:
                self._inspect(db, scope, approval_id)
                part = db.execute('SELECT * FROM delivery_parts WHERE approval_id=? AND part_index=?',
                                  (approval_id, part_index)).fetchone()
                require(part is not None and part['attempt_id'] is not None, 'Part has no send attempt')
                attempt = db.execute('SELECT * FROM delivery_attempts WHERE id=?',
                                     (part['attempt_id'],)).fetchone()
                require(attempt is not None and attempt['state'] != 'aborted', 'Attempt was never sent')
                proof = self._outcome(scope, attempt, receipt_id)
                self._record(db, scope, attempt, proof, retry=True)
                return self._inspect(db, scope, approval_id)
