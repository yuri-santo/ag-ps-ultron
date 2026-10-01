"""Native integration checks use explicit temporary boards and HERMES_HOME."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from admission import QueueError, Scope, TopicStore
from test_admission import admit, plan, two_topics


SCOPE = Scope('telegram', 'bot', 'owner', 'chat')


@pytest.fixture
def native(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'hermes'))
    monkeypatch.delenv('HERMES_KANBAN_DB', raising=False)
    monkeypatch.delenv('HERMES_KANBAN_BOARD', raising=False)
    kb = pytest.importorskip('hermes_cli.kanban_db')
    connection = importlib.import_module('hermes_cli.kanban_db_connect')
    db_path = tmp_path / 'native' / 'kanban.db'
    with connection.connect_closing(db_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0
    return SimpleNamespace(kb=kb, connection=connection, path=db_path)


@pytest.fixture
def store(tmp_path):
    return TopicStore(tmp_path / 'private' / 'queue.db', allowed_profiles={'greg', 'pink'})


def adapter(store, native, **kwargs):
    # Import inside tests so the first TDD run reports the missing feature.
    spec = importlib.util.find_spec('native_cards')
    assert spec is not None, 'Native card reconciliation has not been implemented'
    module = importlib.import_module('native_cards')
    return module.NativeCards(
        store, connect=lambda: native.connection.connect_closing(native.path),
        create_task=kwargs.get('create_task', native.kb.create_task),
        write_txn=kwargs.get('write_txn', native.connection.write_txn),
    )


def topic(store):
    return store.apply_plan(SCOPE, admit(store), plan())[0]


def cards(native):
    with native.connection.connect_closing(native.path) as conn:
        return native.kb.list_tasks(conn, include_archived=True)


def assert_parked(native, count):
    with native.connection.connect_closing(native.path) as conn:
        tasks = native.kb.list_tasks(conn, include_archived=True)
        assert len(tasks) == count
        assert all(t.status == 'blocked' and t.assignee is None for t in tasks)
        assert all(t.session_id is None and t.claim_lock is None for t in tasks)
        assert conn.execute('SELECT COUNT(*) FROM kanban_notify_subs').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM task_runs').fetchone()[0] == 0


def test_create_is_parked_and_restart_reuses_durable_link(store, native):
    revision = topic(store)
    first = adapter(store, native).reconcile(SCOPE, **revision)
    reopened = TopicStore(store.path, allowed_profiles={'greg', 'pink'})
    assert adapter(reopened, native).reconcile(SCOPE, **revision) == first
    assert first['native_card_id'] == cards(native)[0].id
    assert first['released'] is False
    assert reopened.card_intents(SCOPE)[0]['native_card_id'] == first['native_card_id']
    assert_parked(native, 1)


def test_native_commit_before_private_link_is_recovered(store, native, tmp_path):
    revision = topic(store)
    calls = []

    @contextmanager
    def crash_after_native_commit(conn):
        with native.connection.write_txn(conn):
            calls.append(True)
            yield conn
        raise RuntimeError('simulated process loss after native commit')

    with pytest.raises(RuntimeError, match='simulated process loss'):
        adapter(store, native, write_txn=crash_after_native_commit).reconcile(SCOPE, **revision)
    assert calls == [True]
    assert store.card_intents(SCOPE)[0]['native_card_id'] is None
    committed_id = cards(native)[0].id
    other = SimpleNamespace(**vars(native))
    other.path = tmp_path / 'other' / 'kanban.db'
    with pytest.raises(QueueError, match='board'):
        adapter(store, other).reconcile(SCOPE, **revision)
    assert cards(other) == []
    reopened = TopicStore(store.path, allowed_profiles={'greg', 'pink'})
    result = adapter(reopened, native).reconcile(SCOPE, **revision)
    assert result['native_card_id'] == committed_id
    assert_parked(native, 1)


def test_abrupt_exit_after_native_commit_recovers_same_card(store, native):
    revision = topic(store)
    script = '''
from contextlib import contextmanager
from pathlib import Path
import os, sys
from admission import Scope, TopicStore
from native_cards import NativeCards
from hermes_cli.kanban_db import create_task
from hermes_cli.kanban_db_connect import connect_closing, write_txn

@contextmanager
def crash_after_commit(conn):
    with write_txn(conn):
        yield conn
    os._exit(73)

store = TopicStore(sys.argv[1], allowed_profiles={'greg', 'pink'})
adapter = NativeCards(store, connect=lambda: connect_closing(Path(sys.argv[2])),
                      create_task=create_task, write_txn=crash_after_commit)
adapter.reconcile(Scope('telegram', 'bot', 'owner', 'chat'), sys.argv[3], 1)
'''
    child = subprocess.run([sys.executable, '-c', script, str(store.path),
                            str(native.path), revision['topic_id']],
                           cwd=Path(__file__).parent, check=False, capture_output=True)
    assert child.returncode == 73, child.stderr.decode()
    assert store.card_intents(SCOPE)[0]['native_card_id'] is None
    committed_id = cards(native)[0].id
    assert adapter(store, native).reconcile(SCOPE, **revision)['native_card_id'] == committed_id
    assert_parked(native, 1)


def test_concurrent_calls_reuse_one_native_card(store, native):
    revision = topic(store)

    def reconcile(_):
        reopened = TopicStore(store.path, allowed_profiles={'greg', 'pink'})
        return adapter(reopened, native).reconcile(SCOPE, **revision)['native_card_id']

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reconcile, range(24)))
    assert len(set(results)) == 1
    assert_parked(native, 1)


def test_native_lookup_and_create_hold_outer_write_lock(store, native):
    revision = topic(store)

    def create(conn, **kwargs):
        assert conn.in_transaction
        rival = sqlite3.connect(native.path, timeout=0, isolation_level=None)
        try:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                rival.execute('BEGIN IMMEDIATE')
        finally:
            rival.close()
        return native.kb.create_task(conn, **kwargs)

    adapter(store, native, create_task=create).reconcile(SCOPE, **revision)
    assert_parked(native, 1)


@pytest.mark.parametrize('field', ['platform', 'account_id', 'owner_id', 'chat_id', 'thread_id'])
def test_wrong_origin_cannot_create_or_read_binding(store, native, field):
    revision = topic(store)
    values = vars(SCOPE).copy()
    values[field] = 'other'
    with pytest.raises(QueueError, match='scope'):
        adapter(store, native).reconcile(Scope(**values), **revision)
    assert cards(native) == []


def test_stale_revision_and_invalidated_descendant_cannot_create(store, native):
    a, b = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    ingress = admit(store, text='Fix A', message_id='2')
    store.apply_plan(SCOPE, ingress, plan('Fix A', topic_id=a['topic_id'], expected_version=1))
    for revision in (a, b):
        with pytest.raises(QueueError, match='current|valid|Stale'):
            adapter(store, native).reconcile(SCOPE, **revision)
    assert cards(native) == []


@pytest.mark.parametrize('version', [True, 0, '1', -1])
def test_invalid_version_cannot_resolve_card(store, native, version):
    revision = topic(store)
    with pytest.raises(QueueError, match='version'):
        adapter(store, native).reconcile(SCOPE, revision['topic_id'], version)
    assert cards(native) == []


def test_version_write_is_locked_through_native_commit(store, native):
    revision = topic(store)

    def create(conn, **kwargs):
        rival = sqlite3.connect(store.path, timeout=0, isolation_level=None)
        try:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                rival.execute('BEGIN IMMEDIATE')
        finally:
            rival.close()
        return native.kb.create_task(conn, **kwargs)

    adapter(store, native, create_task=create).reconcile(SCOPE, **revision)
    assert_parked(native, 1)


@pytest.mark.parametrize('linked', [False, True])
def test_archived_native_card_is_never_recreated(store, native, linked):
    revision = topic(store)
    card_id = adapter(store, native).reconcile(SCOPE, **revision)['native_card_id']
    if not linked:
        with store._transaction() as db:
            db.execute('DELETE FROM card_links')
    with native.connection.connect_closing(native.path) as conn:
        assert native.kb.archive_task(conn, card_id)
    with pytest.raises(QueueError, match='archived|parked'):
        adapter(store, native).reconcile(SCOPE, **revision)
    assert len(cards(native)) == 1
    assert cards(native)[0].status == 'archived'


@pytest.mark.parametrize('column,value', [
    ('body', 'unrelated intent'), ('title', 'Changed title'),
    ('created_by', 'someone_else'), ('tenant', 'another-scope'),
    ('status', 'ready'), ('assignee', 'greg'), ('session_id', 'unexpected-origin'),
    ('model_override', 'unapproved-model'), ('claim_lock', 'claimed'),
])
def test_conflicting_native_card_fails_closed(store, native, column, value):
    revision = topic(store)
    result = adapter(store, native).reconcile(SCOPE, **revision)
    with native.connection.connect_closing(native.path) as conn:
        with native.connection.write_txn(conn):
            conn.execute(f'UPDATE tasks SET {column}=? WHERE id=?',
                         (value, result['native_card_id']))
    with pytest.raises(QueueError):
        adapter(store, native).reconcile(SCOPE, **revision)
    assert len(cards(native)) == 1


def test_duplicate_correlation_is_rejected_including_archived(store, native):
    revision = topic(store)
    card_id = adapter(store, native).reconcile(SCOPE, **revision)['native_card_id']
    with native.connection.connect_closing(native.path) as conn:
        original = native.kb.get_task(conn, card_id)
        duplicate = native.kb.create_task(conn, title='collision', initial_status='blocked')
        with native.connection.write_txn(conn):
            conn.execute('UPDATE tasks SET idempotency_key=?, status=? WHERE id=?',
                         (original.idempotency_key, 'archived', duplicate))
    with pytest.raises(QueueError, match='multiple|Duplicate|ambiguous'):
        adapter(store, native).reconcile(SCOPE, **revision)
    assert len(cards(native)) == 2


def test_linked_card_missing_cannot_be_silently_replaced(store, native):
    revision = topic(store)
    adapter(store, native).reconcile(SCOPE, **revision)
    with native.connection.connect_closing(native.path) as conn:
        with native.connection.write_txn(conn):
            conn.execute('DELETE FROM tasks')
    with pytest.raises(QueueError, match='missing|Missing'):
        adapter(store, native).reconcile(SCOPE, **revision)
    assert cards(native) == []


def test_existing_binding_rejects_another_board(store, native, tmp_path):
    revision = topic(store)
    adapter(store, native).reconcile(SCOPE, **revision)
    other = SimpleNamespace(**vars(native))
    other.path = tmp_path / 'other' / 'kanban.db'
    with pytest.raises(QueueError, match='board'):
        adapter(store, other).reconcile(SCOPE, **revision)
    assert cards(other) == []


def test_dependency_requires_current_link_then_maps_native_parent(store, native):
    a, b = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    reconciler = adapter(store, native)
    with pytest.raises(QueueError, match='dependency|Dependency'):
        reconciler.reconcile(SCOPE, **b)
    assert cards(native) == []
    parent = reconciler.reconcile(SCOPE, **a)['native_card_id']
    child = reconciler.reconcile(SCOPE, **b)['native_card_id']
    with native.connection.connect_closing(native.path) as conn:
        rows = conn.execute('SELECT parent_id, child_id FROM task_links').fetchall()
        assert [tuple(row) for row in rows] == [(parent, child)]
    assert_parked(native, 2)


def test_subscribed_parent_cannot_leak_origin_to_new_child(store, native):
    a, b = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    reconciler = adapter(store, native)
    parent = reconciler.reconcile(SCOPE, **a)['native_card_id']
    notify = importlib.import_module('hermes_cli.kanban_db_notify')
    with native.connection.connect_closing(native.path) as conn:
        notify.add_notify_sub(conn, task_id=parent, platform='telegram', chat_id='test-only')
    with pytest.raises(QueueError, match='subscription'):
        reconciler.reconcile(SCOPE, **b)
    assert len(cards(native)) == 1


def test_tampered_dependency_edges_are_rejected(store, native):
    a, b = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    reconciler = adapter(store, native)
    reconciler.reconcile(SCOPE, **a)
    reconciler.reconcile(SCOPE, **b)
    with native.connection.connect_closing(native.path) as conn:
        with native.connection.write_txn(conn):
            conn.execute('DELETE FROM task_links')
    with pytest.raises(QueueError, match='dependenc'):
        reconciler.reconcile(SCOPE, **b)
    assert len(cards(native)) == 2


def test_conflicting_create_rolls_back_native_task_and_preserves_intent(store, native):
    revision = topic(store)

    def create(conn, **kwargs):
        kwargs['initial_status'] = 'running'
        return native.kb.create_task(conn, **kwargs)

    with pytest.raises(QueueError, match='parked'):
        adapter(store, native, create_task=create).reconcile(SCOPE, **revision)
    assert cards(native) == []
    assert store.card_intents(SCOPE)[0]['native_card_id'] is None
    adapter(store, native).reconcile(SCOPE, **revision)
    assert_parked(native, 1)
