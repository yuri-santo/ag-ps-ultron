"""Pre-commit guards for managed native cards; no upstream schema extension."""
from functools import wraps
import json
from pathlib import Path

try:
    from .contract import require, QueueError
except ImportError:
    from contract import require, QueueError


def _runtime(conn):
    try:
        from .runtime import Runtime, BOARD
    except ImportError:
        from runtime import Runtime, BOARD
    path = Path(next(row[2] for row in conn.execute('PRAGMA database_list') if row[1] == 'main')).resolve()
    require(path.name == 'kanban.db' and path.parent.name == BOARD, 'Unexpected managed board')
    return Runtime.from_home(path.parents[3])


def guard_mutation(function):
    @wraps(function)
    def checked(conn, task_id, *args, **kwargs):
        row = conn.execute('SELECT created_by FROM tasks WHERE id=?', (task_id,)).fetchone()
        require(row is None or row[0] != 'topic_queue', 'Use topic cancellation/revision, not a native card rewrite')
        return function(conn, task_id, *args, **kwargs)
    return checked


def guard_completion(function):
    @wraps(function)
    def checked(conn, task_id, *args, **kwargs):
        row = conn.execute('SELECT created_by FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None or row[0] != 'topic_queue':
            return function(conn, task_id, *args, **kwargs)
        require(not conn.in_transaction, 'Managed completion must acquire private revision lock first')
        runtime = _runtime(conn)
        task = runtime.kb.get_task(conn, task_id)
        scope, data = runtime._binding(task)
        # Hold revision/control lock until native commit: --force cannot reuse
        # an old approval and a concurrent correction cannot slip past the gate.
        with runtime.delivery._transaction() as private:
            require(task.current_run_id is not None and kwargs.get('expected_run_id') == task.current_run_id,
                    'Managed completion requires native run ownership')
            if data['kind'] == 'ingress':
                ingress = private.execute('SELECT plan,result FROM ingress WHERE id=? AND scope=?',
                                          (data['ingress_id'], scope.key())).fetchone()
                require(ingress and ingress[0] and not json.loads(ingress[0]).get('cancelled')
                        and ingress[1], 'Triage is not durably committed')
                require(kwargs.get('result') == 'Triagem persistida; entregas no outbox aprovado.',
                        'Triage result is not a delivery')
            else:
                row = private.execute('SELECT id FROM delivery_approvals WHERE scope=? AND topic_id=? AND version=?',
                                      (scope.key(), data['topic_id'], data['version'])).fetchone()
                require(row is not None, 'Topic approval manifest required')
                payload = runtime.delivery._approval(private, scope, row[0])
                require(kwargs.get('result') == '\n'.join(payload['parts']), 'Final result changed after approval')
                runtime.delivery._active(scope, data['topic_id'], data['version'])
            kwargs['fire_lifecycle_hook'] = False
            return function(conn, task_id, *args, **kwargs)
    return checked
