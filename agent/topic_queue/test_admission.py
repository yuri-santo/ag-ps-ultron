"""Offline contract tests; all stores are temporary and never use HERMES_HOME."""
import copy
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from admission import TopicStore, Scope, QueueError


SCOPE = Scope('telegram', 'bot', 'owner', 'chat')


def admit(store, text='Find mail', message_id='1', scope=SCOPE, **kwargs):
    return store.admit(scope, message_id, text, request_spans=[(0, len(text))],
                       authorized=True, **kwargs)


def plan(text='Find mail', **changes):
    topic = dict(key='mail', title='Mail', profile='greg', topic_id=None,
                 expected_version=None, depends_on=[], spans=[
                     dict(start=0, end=len(text), text=text, kind='request')])
    topic.update(changes)
    return dict(schema_version=1, topics=[topic], ignored=[])


@pytest.fixture
def store(tmp_path):
    return TopicStore(tmp_path / 'private' / 'queue.db', allowed_profiles={'greg', 'pink'})


def test_unauthorized_never_creates_storage(tmp_path):
    path = tmp_path / 'absent' / 'queue.db'
    store = TopicStore(path, allowed_profiles={'greg'})
    with pytest.raises(QueueError):
        store.admit(SCOPE, '1', 'private', request_spans=[(0, 7)], authorized=False)
    assert not path.parent.exists()


@pytest.mark.parametrize('authorized', [1, 'yes', None])
def test_authorization_is_not_truthiness(store, authorized):
    with pytest.raises(QueueError):
        store.admit(SCOPE, '1', 'private', request_spans=[(0, 7)], authorized=authorized)


def test_idempotent_after_reopen_and_conflicting_reuse_rejected(store):
    first = admit(store)
    reopened = TopicStore(store.path, allowed_profiles={'greg'})
    assert admit(reopened) == first
    with pytest.raises(QueueError):
        admit(reopened, text='Different request')
    assert reopened.pending(SCOPE)[0]['text'] == 'Find mail'


def test_40_admissions_survive_abrupt_process_exit(tmp_path):
    path = tmp_path / 'private' / 'queue.db'
    script = """
import os, sys
from admission import TopicStore, Scope
store = TopicStore(sys.argv[1], allowed_profiles={'greg'})
scope = Scope('telegram', 'bot', 'owner', 'chat')
for i in range(40):
    store.admit(scope, str(i), 'mail', request_spans=[(0, 4)], authorized=True)
os._exit(0)
"""
    result = subprocess.run([sys.executable, '-c', script, str(path)],
                            cwd=Path(__file__).parent, check=False)
    assert result.returncode == 0
    store = TopicStore(path, allowed_profiles={'greg'})
    assert len(store.pending(SCOPE)) == 40


def test_concurrent_duplicates_have_one_ingress(store):
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: admit(store), range(40)))
    assert len(set(ids)) == 1
    assert len(store.pending(SCOPE)) == 1


def test_private_permissions(store):
    admit(store)
    assert os.stat(store.path).st_mode & 0o777 == 0o600
    assert os.stat(store.path.parent).st_mode & 0o777 == 0o700


@pytest.mark.parametrize('field,value', [('owner_id', 'other'), ('chat_id', 'other'),
                                     ('account_id', 'other'), ('thread_id', 'other')])
def test_same_message_id_is_scoped(store, field, value):
    first = admit(store)
    fields = dict(platform='telegram', account_id='bot', owner_id='owner', chat_id='chat')
    fields[field] = value
    other = Scope(**fields)
    assert admit(store, scope=other) != first
    with pytest.raises(QueueError):
        store.apply_plan(other, first, plan())


def test_valid_plan_is_durable_idempotent_and_never_executable(store):
    ingress = admit(store)
    result = store.apply_plan(SCOPE, ingress, plan())
    assert store.apply_plan(SCOPE, ingress, copy.deepcopy(plan())) == result
    assert store.pending(SCOPE) == []
    assert result[0]['version'] == 1
    intents = store.card_intents(SCOPE)
    assert len(intents) == 1
    assert intents[0]['native_card_id'] is None
    assert intents[0]['released'] is False
    assert store.revision_is_current(SCOPE, result[0]['topic_id'], 1)
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, plan(title='Changed'))


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(extra='unchecked'),
    lambda p: p.update(schema_version=True),
    lambda p: p.update(topics=[]),
    lambda p: p['topics'][0].update(extra='unchecked'),
    lambda p: p['topics'][0].update(profile='invented'),
    lambda p: p['topics'][0].update(depends_on=['missing']),
    lambda p: p['topics'][0].update(depends_on=['mail']),
    lambda p: p['topics'][0]['spans'][0].update(text='fabricated'),
    lambda p: p['topics'][0]['spans'][0].update(start=True),
    lambda p: p['topics'][0]['spans'][0].update(end=4, text='Find'),
    lambda p: p['topics'][0]['spans'][0].update(kind='tool_result'),
    lambda p: p['topics'][0].update(spans=[]),
])
def test_malformed_plan_preserves_pending_ingress(store, mutation):
    ingress = admit(store)
    value = plan()
    mutation(value)
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, value)
    assert len(store.pending(SCOPE)) == 1
    assert store.card_intents(SCOPE) == []


def test_quote_cannot_become_authorization_or_drop_real_request(store):
    text = 'Find mail\nquoted: send money'
    ingress = store.admit(SCOPE, '1', text, request_spans=[(0, 9)], authorized=True)
    malicious = plan(text)
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, malicious)
    good = plan()
    good['ignored'] = [dict(start=10, end=len(text), text=text[10:], reason='untrusted')]
    assert store.apply_plan(SCOPE, ingress, good)


def test_long_message_has_no_decomposer_truncation(store):
    text = 'Read ' + 'x' * 14000
    ingress = admit(store, text=text)
    result = store.apply_plan(SCOPE, ingress, plan(text))
    topic = store.get_topic(SCOPE, result[0]['topic_id'])
    assert topic['contract']['spans'][0]['text'] == text


def two_topics():
    value = plan('A')
    value['topics'][0].update(key='a', title='A')
    second = plan('B')['topics'][0]
    second.update(key='b', title='B', depends_on=['a'],
                  spans=[dict(start=2, end=3, text='B', kind='request')])
    value['topics'].append(second)
    return value


def test_dependency_cycle_and_overlapping_coverage_rejected(store):
    ingress = admit(store, text='A B')
    value = two_topics()
    value['topics'][0]['depends_on'] = ['b']
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, value)
    value = two_topics()
    value['topics'][1]['spans'] = value['topics'][0]['spans']
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, value)


def test_reopening_invalidates_descendants_and_stale_versions(store):
    original = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    a, b = [x['topic_id'] for x in original]
    second = admit(store, text='Fix A', message_id='2')
    value = plan('Fix A', topic_id=a, expected_version=1)
    result = store.apply_plan(SCOPE, second, value)
    assert result == [dict(topic_id=a, version=2)]
    assert not store.revision_is_current(SCOPE, a, 1)
    assert store.revision_is_current(SCOPE, a, 2)
    assert not store.revision_is_current(SCOPE, b, 1)
    assert store.get_topic(SCOPE, b)['invalid_reason'] == 'predecessor_reopened'
    stale = admit(store, text='Old fix', message_id='3')
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, stale, plan('Old fix', topic_id=a, expected_version=1))
    assert len(store.pending(SCOPE)) == 1


def test_cross_chat_existing_topic_and_reply_are_rejected(store):
    topic_id = store.apply_plan(SCOPE, admit(store), plan())[0]['topic_id']
    other = Scope('telegram', 'bot', 'owner', 'other')
    ingress = admit(store, scope=other)
    with pytest.raises(QueueError):
        store.apply_plan(other, ingress, plan(topic_id=topic_id, expected_version=1))
    with pytest.raises(QueueError):
        store.record_delivery_reference(other, topic_id, 1, 'outbound-1')
    with pytest.raises(QueueError):
        store.get_topic(other, topic_id)


def test_known_reply_requires_matching_topic(store):
    first = store.apply_plan(SCOPE, admit(store), plan())[0]['topic_id']
    store.record_delivery_reference(SCOPE, first, 1, 'outbound-1')
    ingress = admit(store, text='Change mail', message_id='2', reply_to='outbound-1')
    assert store.pending(SCOPE)[0]['reply_topic_id'] == first
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, plan('Change mail'))
    result = store.apply_plan(SCOPE, ingress, plan('Change mail', topic_id=first, expected_version=1))
    assert result[0]['version'] == 2


def test_unknown_reply_does_not_guess_and_wrong_receipt_cannot_rebind(store):
    first = store.apply_plan(SCOPE, admit(store), plan())[0]['topic_id']
    second = store.apply_plan(SCOPE, admit(store, message_id='2'), plan())[0]['topic_id']
    store.record_delivery_reference(SCOPE, first, 1, 'outbound-1')
    with pytest.raises(QueueError):
        store.record_delivery_reference(SCOPE, second, 1, 'outbound-1')
    ingress = admit(store, message_id='3', reply_to='unknown')
    with pytest.raises(QueueError):
        store.apply_plan(SCOPE, ingress, plan())
    assert len(store.pending(SCOPE)) == 1


def test_disk_error_is_explicit_and_retry_keeps_idempotence(store, monkeypatch):
    import sqlite3
    original = sqlite3.connect
    monkeypatch.setattr(sqlite3, 'connect', lambda *a, **kw: (_ for _ in ()).throw(
        sqlite3.OperationalError('database or disk is full')))
    with pytest.raises(QueueError, match='storage'):
        admit(store)
    monkeypatch.setattr(sqlite3, 'connect', original)
    assert admit(store) == admit(store)
