"""Reconcile durable intents with parked Kanban cards; no runtime registration.

Native connections and create/write APIs are injected by a trusted host. This
module never opens a default board, invokes a model, or releases native work.
"""
import hashlib
from pathlib import Path

try:
    from .contract import canonical, require
except ImportError:
    from contract import canonical, require


def _digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class NativeCards:
    def __init__(self, store, *, connect, create_task, write_txn):
        self.store = store
        self.connect = connect
        self.create_task = create_task
        self.write_txn = write_txn

    @staticmethod
    def _identity(intent, scope_key):
        return dict(
            title=intent['contract']['title'].strip(),
            body=canonical(dict(adapter='topic_queue', schema_version=1,
                                correlation=intent['correlation'], topic_id=intent['topic_id'],
                                version=intent['version'], scope_hash=_digest(scope_key),
                                contract_hash=_digest(intent['contract']), released=False)),
            created_by='topic_queue', tenant='topic-queue:' + _digest(scope_key),
            idempotency_key='topic-queue:' + intent['correlation'],
        )

    def _find(self, conn, intent, scope_key):
        expected = self._identity(intent, scope_key)
        # Native create_task ignores archived matches and performs this lookup
        # before its own transaction. Our caller holds an outer write lock.
        rows = conn.execute('SELECT * FROM tasks WHERE idempotency_key=?',
                            (expected['idempotency_key'],)).fetchall()
        require(len(rows) <= 1, 'Duplicate native correlation is ambiguous')
        if not rows:
            require(intent['native_card_id'] is None, 'Linked native card is missing')
            return None
        card = dict(rows[0])
        require(intent['native_card_id'] in (None, card['id']), 'Conflicting native card binding')
        require(all(card[name] == value for name, value in expected.items()),
                'Native card does not match durable intent')
        require(card['status'] == 'blocked', 'Native card is not parked or was archived')
        require(all(card[name] is None for name in (
            'assignee', 'session_id', 'claim_lock', 'claim_expires', 'worker_pid',
            'current_run_id', 'started_at', 'completed_at', 'model_override',
            'provider_override', 'workflow_template_id', 'current_step_key',
            'workspace_path', 'branch_name', 'project_id',
        )) and card['workspace_kind'] == 'scratch' and not card['goal_mode'],
            'Native card has execution or origin state')
        require(conn.execute('SELECT 1 FROM kanban_notify_subs WHERE task_id=? LIMIT 1',
                             (card['id'],)).fetchone() is None,
                'Managed card has a notification subscription')
        require(conn.execute('SELECT 1 FROM task_runs WHERE task_id=? LIMIT 1',
                             (card['id'],)).fetchone() is None, 'Managed card has execution history')
        return card['id']

    def reconcile(self, scope, topic_id, version):
        scope_key = scope.key()
        with self.connect() as conn:
            require(not conn.in_transaction, 'Native adapter needs an independent connection')
            boards = [row[2] for row in conn.execute('PRAGMA database_list') if row[1] == 'main']
            require(len(boards) == 1 and bool(boards[0]), 'Native board must be durable')
            board = str(Path(boards[0]).resolve())

            def resolve(intent, dependencies):
                with self.write_txn(conn):
                    parents = []
                    for parent in dependencies:
                        parent_id = self._find(conn, parent, scope_key)
                        require(parent_id is not None, 'Dependency native card is missing')
                        parents.append(parent_id)
                    card_id = self._find(conn, intent, scope_key)
                    if card_id is None:
                        card_id = self.create_task(
                            conn, **self._identity(intent, scope_key), parents=parents,
                            assignee=None, initial_status='blocked', workspace_kind='scratch',
                            session_id=None, creator_task_id=None,
                        )
                        require(self._find(conn, intent, scope_key) == card_id,
                                'Native creation returned a conflicting card')
                    actual_parents = [row[0] for row in conn.execute(
                        'SELECT parent_id FROM task_links WHERE child_id=? ORDER BY parent_id', (card_id,))]
                    require(actual_parents == sorted(parents), 'Native dependency mapping conflicts with intent')
                return card_id

            return self.store.reconcile_card(scope, topic_id, version, board, resolve)
