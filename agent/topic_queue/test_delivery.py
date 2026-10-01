"""Offline approval/outbox tests. No native account, gateway or transport is used."""
import copy
import hashlib
import json
import multiprocessing
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from admission import Scope, TopicStore, QueueError
from contract import canonical
from delivery import Delivery
from test_admission import admit, plan, two_topics


SCOPE = Scope('telegram', 'bot', 'owner', 'chat')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Proofs:
    """Trusted-host stand-in; these records never come from a model argument."""

    def __init__(self):
        self.executions = {}
        self.reviews = {}
        self.outcomes = {}
        self.states = {}
        self.rules = dict(id='mail-policy', version='1',
                          required_competencies=['mail', 'audit'],
                          required_reviewers=['tanos'],
                          reviewers={'pink': ['mail'], 'tanos': ['audit']})

    def execution(self, proof_id):
        return copy.deepcopy(self.executions[proof_id])

    def review(self, proof_id):
        return copy.deepcopy(self.reviews[proof_id])

    def outcome(self, proof_id):
        return copy.deepcopy(self.outcomes[proof_id])

    def policy(self, scope, topic_id, version, contract):
        return copy.deepcopy(self.rules)

    def control(self, scope, topic_id, version):
        return self.states.get(topic_id, 'active')


@pytest.fixture
def setup(tmp_path):
    store = TopicStore(tmp_path / 'private' / 'queue.db',
                       allowed_profiles={'greg', 'pink', 'tanos'})
    proofs = Proofs()
    delivery = Delivery(store, proofs=proofs, formatter=lambda text: text.split('\n---\n'))
    return store, proofs, delivery


def candidate(setup, message='1', text='Answer', topic=None, scope=SCOPE):
    store, proofs, delivery = setup
    if topic is None:
        topic = store.apply_plan(scope, admit(store, message_id=message, scope=scope), plan())[0]
    topic_id, version = topic['topic_id'], topic['version']
    card = store.reconcile_card(scope, topic_id, version, 'board',
                                lambda intent, dependencies: 'card-' + topic_id + str(version))
    contract = store.get_topic(scope, topic_id)['contract']
    run_id = 'run-' + topic_id + str(version)
    proofs.executions[run_id] = dict(
        run_id=run_id, scope=scope.key(), topic_id=topic_id, version=version,
        contract_hash=digest(canonical(contract)), native_board='board',
        native_card_id=card['native_card_id'], profile='greg', author='Greg',
        served_identity='provider-a/model-a', completed=True, model_review='approved',
        candidate=text, candidate_hash=digest(text), evidence_hashes=[digest('evidence')])
    return topic, run_id


def prepare(setup, **kwargs):
    topic, run_id = candidate(setup, **kwargs)
    return setup[2].prepare(kwargs.get('scope', SCOPE), **topic, run_id=run_id)


def reviews(setup, prepared):
    ids = []
    for profile, identity in [('pink', 'provider-b/model-b'), ('tanos', 'provider-c/model-c')]:
        proof_id = profile + '-' + prepared['id']
        setup[1].reviews[proof_id] = dict(
            id=proof_id, prepared_id=prepared['id'], binding_hash=prepared['id'],
            run_id=proof_id, profile=profile, served_identity=identity,
            completed=True, verdict='approved')
        ids.append(proof_id)
    return ids


def approve(setup, **kwargs):
    prepared = prepare(setup, **kwargs)
    return setup[2].approve(kwargs.get('scope', SCOPE), prepared['id'], reviews(setup, prepared))


def test_prepare_hashes_exact_preformatted_parts_and_real_author(setup):
    prepared = prepare(setup, text='First\n---\nSecond')
    assert prepared['parts'] == ['Greg: First', 'Second']
    assert prepared['candidate_hash'] == digest('First\n---\nSecond')
    assert prepared['delivery_hash'] == digest(canonical(prepared['parts']))
    assert prepared['id'] == digest(canonical({k: v for k, v in prepared.items() if k != 'id'}))


@pytest.mark.parametrize('field,value', [
    ('scope', Scope('telegram', 'bot', 'owner', 'elsewhere').key()),
    ('topic_id', 'other'), ('version', 2), ('version', True),
    ('native_card_id', 'other'), ('native_board', 'other'),
    ('profile', 'pink'), ('run_id', 'other'), ('contract_hash', digest('other')),
    ('candidate_hash', digest('other')), ('completed', False), ('completed', 1),
    ('model_review', 'not_required'), ('model_review', 'pending'),
    ('served_identity', ''), ('author', ''),
])
def test_forged_or_incomplete_execution_is_rejected(setup, field, value):
    topic, run_id = candidate(setup)
    setup[1].executions[run_id][field] = value
    with pytest.raises(QueueError):
        setup[2].prepare(SCOPE, **topic, run_id=run_id)


def test_readers_are_required_and_public_boundary_has_no_approval_boolean(setup):
    with pytest.raises(TypeError):
        Delivery(setup[0])
    prepared = prepare(setup)
    with pytest.raises(TypeError):
        setup[2].approve(SCOPE, prepared['id'], [], approved=True)
    with pytest.raises(QueueError):
        setup[2].approve(SCOPE, prepared['id'], [True])


def test_required_competencies_and_mandatory_reviewer_cannot_be_skipped(setup):
    prepared = prepare(setup)
    ids = reviews(setup, prepared)
    for missing in [[], ids[:1], ids[1:]]:
        with pytest.raises(QueueError):
            setup[2].approve(SCOPE, prepared['id'], missing)
    assert setup[2].approve(SCOPE, prepared['id'], ids)['prepared_id'] == prepared['id']


@pytest.mark.parametrize('mutation', [
    {'verdict': 'not_required'}, {'verdict': 'rejected'}, {'completed': False},
    {'prepared_id': 'other'}, {'binding_hash': 'other'}, {'profile': 'invented'},
    {'served_identity': 'provider-a/model-a'},
])
def test_review_must_cover_exact_candidate_and_be_independent(setup, mutation):
    prepared = prepare(setup)
    ids = reviews(setup, prepared)
    for proof_id in ids:
        setup[1].reviews[proof_id].update(mutation)
    with pytest.raises(QueueError):
        setup[2].approve(SCOPE, prepared['id'], ids)


def test_duplicate_approval_is_idempotent_and_manifest_is_immutable(setup):
    prepared = prepare(setup)
    ids = reviews(setup, prepared)
    first = setup[2].approve(SCOPE, prepared['id'], ids)
    assert setup[2].approve(SCOPE, prepared['id'], list(reversed(ids))) == first
    with sqlite3.connect(setup[0].path) as db:
        assert db.execute('SELECT count(*) FROM delivery_approvals').fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            db.execute('UPDATE delivery_approvals SET manifest=?', ('{}',))


def test_approval_rechecks_execution_and_policy_after_review(setup):
    prepared = prepare(setup)
    ids = reviews(setup, prepared)
    setup[1].executions[prepared['execution']['run_id']]['candidate'] = 'Changed'
    with pytest.raises(QueueError):
        setup[2].approve(SCOPE, prepared['id'], ids)


def test_revision_change_revokes_prepared_result(setup):
    prepared = prepare(setup)
    store, _, delivery = setup
    store.apply_plan(SCOPE, admit(store, text='Fix', message_id='2'),
                     plan('Fix', topic_id=prepared['topic_id'], expected_version=1))
    with pytest.raises(QueueError):
        delivery.approve(SCOPE, prepared['id'], reviews(setup, prepared))


def test_dependency_requires_current_approval_and_reopen_invalidates_child(setup):
    store, _, delivery = setup
    topics = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    parent_topic, parent_run = candidate(setup, topic=topics[0])
    child_topic, child_run = candidate(setup, topic=topics[1])
    with pytest.raises(QueueError, match='Dependency'):
        delivery.prepare(SCOPE, **child_topic, run_id=child_run)
    parent = delivery.prepare(SCOPE, **parent_topic, run_id=parent_run)
    delivery.approve(SCOPE, parent['id'], reviews(setup, parent))
    child = delivery.prepare(SCOPE, **child_topic, run_id=child_run)
    store.apply_plan(SCOPE, admit(store, text='Fix A', message_id='2'),
                     plan('Fix A', topic_id=topics[0]['topic_id'], expected_version=1))
    with pytest.raises(QueueError):
        delivery.approve(SCOPE, child['id'], reviews(setup, child))


@pytest.mark.parametrize('state', ['paused', 'cancelled', 'unknown'])
def test_host_control_blocks_approval(setup, state):
    prepared = prepare(setup)
    setup[1].states[prepared['topic_id']] = state
    with pytest.raises(QueueError):
        setup[2].approve(SCOPE, prepared['id'], reviews(setup, prepared))


def sender(setup, calls, *, outcome='sent'):
    def send(scope, attempt_id, text):
        calls.append((scope, attempt_id, text))
        proof_id = 'receipt-' + attempt_id
        setup[1].outcomes[proof_id] = dict(
            id=proof_id, attempt_id=attempt_id, scope=scope.key(), text_hash=digest(text),
            status=outcome, message_id='message-' + attempt_id if outcome == 'sent' else None)
        return proof_id
    return send


def test_fast_approved_topic_does_not_wait_for_slow_unapproved_topic(setup):
    prepare(setup, message='slow', text='Slow')
    fast = approve(setup, message='fast', text='Fast')
    calls = []
    result = setup[2].dispatch_next(SCOPE, sender(setup, calls))
    assert result == dict(status='sent', approval_id=fast['id'])
    assert [call[2] for call in calls] == ['Greg: Fast']
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'empty'


def test_distinct_topics_follow_approval_order_and_only_exact_parts_are_sent(setup):
    first = prepare(setup, message='first', text='First\n---\nEnd')
    second = approve(setup, message='second', text='Second')
    setup[2].approve(SCOPE, first['id'], reviews(setup, first))
    setup[2].formatter = lambda _: (_ for _ in ()).throw(AssertionError('Cannot reformat after review'))
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['approval_id'] == second['id']
    setup[2].dispatch_next(SCOPE, sender(setup, calls))
    assert [call[2] for call in calls] == ['Greg: Second', 'Greg: First', 'End']


def test_reply_mapping_exists_only_after_each_verified_receipt(setup):
    approval = approve(setup, text='One\n---\nTwo')
    calls = []
    real_send = sender(setup, calls)

    def send(scope, attempt_id, text):
        with sqlite3.connect(setup[0].path) as db:
            assert db.execute('SELECT count(*) FROM delivery_references').fetchone()[0] == len(calls)
            assert db.execute('SELECT state FROM delivery_parts WHERE attempt_id=?',
                              (attempt_id,)).fetchone()[0] == 'sending'
        return real_send(scope, attempt_id, text)

    setup[2].dispatch_next(SCOPE, send)
    with sqlite3.connect(setup[0].path) as db:
        rows = db.execute('SELECT topic_id, version FROM delivery_references').fetchall()
    assert rows == [(approval['topic_id'], 1), (approval['topic_id'], 1)]


def test_unknown_send_is_durable_and_never_automatically_repeated(setup):
    approval = approve(setup)
    calls = []

    def timeout(scope, attempt_id, text):
        calls.append(attempt_id)
        raise TimeoutError('May already have sent')

    assert setup[2].dispatch_next(SCOPE, timeout)['status'] == 'uncertain'
    reopened = Delivery(setup[0], proofs=setup[1], formatter=lambda text: [text])
    assert reopened.dispatch_next(SCOPE, timeout)['status'] == 'blocked'
    assert len(calls) == 1
    state = reopened.inspect(SCOPE, approval['id'])
    assert state['state'] == 'uncertain'
    assert state['parts'][0]['state'] == 'uncertain'
    with sqlite3.connect(setup[0].path) as db:
        assert db.execute('SELECT count(*) FROM delivery_references').fetchone()[0] == 0


def test_single_uncertain_topic_does_not_block_independent_delivery(setup):
    first = approve(setup, message='first', text='First')
    second = approve(setup, message='second', text='Second')
    def timeout(*args):
        raise TimeoutError('May have sent')
    assert setup[2].dispatch_next(SCOPE, timeout)['status'] == 'uncertain'
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['approval_id'] == second['id']
    assert [c[2] for c in calls] == ['Greg: Second']
    assert setup[2].inspect(SCOPE, first['id'])['state'] == 'uncertain'
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'blocked'


@pytest.mark.parametrize('invalidate', ['cancel', 'reopen'])
def test_invalidated_uncertain_multipart_releases_other_topics_without_resending(setup, invalidate):
    first = approve(setup, message='first', text='One\n---\nTwo')
    second = approve(setup, message='second', text='Independent')
    def timeout(*args):
        raise TimeoutError('May have sent')
    assert setup[2].dispatch_next(SCOPE, timeout)['status'] == 'uncertain'
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'blocked'
    if invalidate == 'cancel':
        setup[1].states[first['topic_id']] = 'cancelled'
    else:
        setup[0].apply_plan(SCOPE, admit(setup[0], text='Fix', message_id='edit'),
            plan('Fix', topic_id=first['topic_id'], expected_version=1))
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['approval_id'] == second['id']
    assert [c[2] for c in calls] == ['Greg: Independent']
    parts = setup[2].inspect(SCOPE, first['id'])['parts']
    assert [p['state'] for p in parts] == ['uncertain', 'invalid']


def test_process_exit_after_send_intent_recovers_as_uncertain(setup):
    approval = approve(setup)

    def die():
        setup[2].dispatch_next(SCOPE, lambda *args: os._exit(17))

    child = multiprocessing.get_context('fork').Process(target=die)
    child.start()
    child.join(10)
    assert child.exitcode == 17
    assert setup[2].inspect(SCOPE, approval['id'])['parts'][0]['state'] == 'sending'
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'blocked'
    assert calls == []
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'uncertain'


@pytest.mark.parametrize('field,value', [
    ('status', 'unknown'), ('attempt_id', 'other'), ('scope', 'other'),
    ('text_hash', digest('changed')), ('message_id', ''),
])
def test_malformed_or_wrong_receipt_never_confirms_delivery(setup, field, value):
    approval = approve(setup)
    send = sender(setup, [])

    def bad_receipt(*args):
        proof_id = send(*args)
        setup[1].outcomes[proof_id][field] = value
        return proof_id

    assert setup[2].dispatch_next(SCOPE, bad_receipt)['status'] == 'uncertain'
    assert setup[2].inspect(SCOPE, approval['id'])['parts'][0]['message_id'] is None


def test_no_send_evidence_can_retry_but_failed_topic_does_not_block_independent(setup):
    first = approve(setup, message='first', text='First')
    second = approve(setup, message='second', text='Second')
    failed = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, failed, outcome='not_sent'))['status'] == 'deferred'
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['approval_id'] == second['id']
    assert [c[2] for c in calls] == ['Greg: Second']
    proof_id = 'receipt-' + failed[0][1]
    setup[2].reconcile(SCOPE, first['id'], 0, proof_id)
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['approval_id'] == first['id']
    assert calls[-1][2] == 'Greg: First'


def test_uncertain_can_reconcile_real_receipt_without_resending(setup):
    approval = approve(setup)
    attempts = []
    real_send = sender(setup, attempts)

    def lost_response(*args):
        real_send(*args)
        raise TimeoutError('Response lost')

    setup[2].dispatch_next(SCOPE, lost_response)
    setup[2].reconcile(SCOPE, approval['id'], 0, 'receipt-' + attempts[0][1])
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'sent'
    assert setup[2].dispatch_next(SCOPE, real_send)['status'] == 'empty'
    assert len(attempts) == 1


def test_partial_multipart_delivery_cannot_interleave_other_topic(setup):
    first = approve(setup, message='first', text='One\n---\nTwo')
    approve(setup, message='second', text='Other')
    calls = []
    send = sender(setup, calls)

    def partial(scope, attempt_id, text):
        proof_id = send(scope, attempt_id, text)
        if len(calls) == 2:
            setup[1].outcomes[proof_id].update(status='not_sent', message_id=None)
        return proof_id

    assert setup[2].dispatch_next(SCOPE, partial)['status'] == 'deferred'
    assert setup[2].dispatch_next(SCOPE, send)['status'] == 'blocked'
    assert len(calls) == 2
    setup[2].reconcile(SCOPE, first['id'], 1, 'receipt-' + calls[-1][1])
    setup[2].dispatch_next(SCOPE, send)
    setup[2].dispatch_next(SCOPE, send)
    assert [c[2] for c in calls] == ['Greg: One', 'Two', 'Two', 'Greg: Other']


@pytest.mark.parametrize('state', ['paused', 'cancelled'])
def test_pause_and_cancel_checked_before_send_and_between_parts(setup, state):
    approval = approve(setup, text='One\n---\nTwo')
    calls = []
    send = sender(setup, calls)
    setup[1].states[approval['topic_id']] = state
    setup[2].dispatch_next(SCOPE, send)
    assert calls == []
    if state == 'cancelled':
        assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'invalid'
        return
    setup[1].states[approval['topic_id']] = 'active'

    def pause_after_first(*args):
        result = send(*args)
        setup[1].states[approval['topic_id']] = 'paused'
        return result

    assert setup[2].dispatch_next(SCOPE, pause_after_first)['status'] == 'blocked'
    assert [c[2] for c in calls] == ['Greg: One']
    setup[1].states[approval['topic_id']] = 'active'
    assert setup[2].dispatch_next(SCOPE, send)['status'] == 'sent'
    assert [c[2] for c in calls] == ['Greg: One', 'Two']


def test_reopened_revision_and_descendant_are_never_sent(setup):
    approval = approve(setup)
    store = setup[0]
    store.apply_plan(SCOPE, admit(store, text='Fix', message_id='2'),
                     plan('Fix', topic_id=approval['topic_id'], expected_version=1))
    calls = []
    setup[2].dispatch_next(SCOPE, sender(setup, calls))
    assert calls == []
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'invalid'


def test_concurrent_dispatchers_send_each_part_once_without_interleaving(setup):
    approve(setup, message='first', text='One\n---\nTwo')
    approve(setup, message='second', text='Other')
    calls = []
    entered, release = threading.Event(), threading.Event()
    send = sender(setup, calls)

    def slow_send(*args):
        entered.set()
        assert release.wait(5)
        return send(*args)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(setup[2].dispatch_next, SCOPE, slow_send)
        assert entered.wait(5)
        second = pool.submit(setup[2].dispatch_next, SCOPE, send)
        try:
            assert second.result(timeout=3)['status'] == 'busy'
        finally:
            release.set()
        assert first.result(timeout=5)['status'] == 'sent'
    setup[2].dispatch_next(SCOPE, send)
    assert [c[2] for c in calls] == ['Greg: One', 'Two', 'Greg: Other']


def test_revision_lock_covers_bounded_send(setup):
    approval = approve(setup)
    send = sender(setup, [])

    def transport(*args):
        with sqlite3.connect(setup[0].path, timeout=0) as other:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                other.execute('UPDATE topics SET current_version=2 WHERE id=?', (approval['topic_id'],))
        return send(*args)

    assert setup[2].dispatch_next(SCOPE, transport)['status'] == 'sent'


def test_scope_lock_is_nonblocking_across_processes(setup):
    approve(setup, text='One\n---\nTwo')
    context = multiprocessing.get_context('fork')
    entered, release = context.Event(), context.Event()

    def dispatch():
        send = sender(setup, [])

        def held(*args):
            entered.set()
            assert release.wait(10)
            return send(*args)

        assert setup[2].dispatch_next(SCOPE, held)['status'] == 'sent'

    process = context.Process(target=dispatch)
    process.start()
    try:
        assert entered.wait(5)
        calls = []
        assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'busy'
        assert calls == []
    finally:
        release.set()
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0


@pytest.mark.parametrize('changed', ['execution', 'policy', 'review'])
def test_dispatch_revalidates_all_approval_proofs(setup, changed):
    approval = approve(setup)
    if changed == 'execution':
        next(iter(setup[1].executions.values()))['candidate'] = 'Changed'
    elif changed == 'policy':
        setup[1].rules['version'] = '2'
    else:
        next(iter(setup[1].reviews.values()))['verdict'] = 'rejected'
    calls = []
    setup[2].dispatch_next(SCOPE, sender(setup, calls))
    assert calls == []
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'invalid'


def test_dispatch_rejects_descendant_after_predecessor_revision(setup):
    store, _, delivery = setup
    topics = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    approve(setup, topic=topics[0])
    child = approve(setup, topic=topics[1])
    store.apply_plan(SCOPE, admit(store, text='Fix A', message_id='2'),
                     plan('Fix A', topic_id=topics[0]['topic_id'], expected_version=1))
    calls = []
    delivery.dispatch_next(SCOPE, sender(setup, calls))
    assert calls == []
    assert delivery.inspect(SCOPE, child['id'])['state'] == 'invalid'


def test_unavailable_host_proof_does_not_permanently_invalidate_delivery(setup):
    approval = approve(setup)
    read = setup[1].execution
    setup[1].execution = lambda _: (_ for _ in ()).throw(TimeoutError('Unavailable'))
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'blocked'
    assert calls == []
    setup[1].execution = read
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'sent'
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'sent'


def test_reconcile_cannot_accept_other_attempt_or_model_supplied_status(setup):
    approval = approve(setup)
    attempts = []
    send = sender(setup, attempts)

    def lost(*args):
        send(*args)
        raise TimeoutError('Response lost')

    setup[2].dispatch_next(SCOPE, lost)
    receipt_id = 'receipt-' + attempts[0][1]
    with pytest.raises(QueueError):
        setup[2].reconcile(SCOPE, approval['id'], 0, {'status': 'sent'})
    setup[1].outcomes[receipt_id]['attempt_id'] = 'other'
    with pytest.raises(QueueError):
        setup[2].reconcile(SCOPE, approval['id'], 0, receipt_id)
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'uncertain'


def test_receipt_is_durable_and_duplicate_reconciliation_is_idempotent(setup):
    approval = approve(setup)
    calls = []
    setup[2].dispatch_next(SCOPE, sender(setup, calls))
    receipt_id = 'receipt-' + calls[0][1]
    before = setup[2].inspect(SCOPE, approval['id'])
    setup[2].reconcile(SCOPE, approval['id'], 0, receipt_id)
    assert setup[2].inspect(SCOPE, approval['id']) == before
    setup[1].outcomes.clear()
    assert setup[2].inspect(SCOPE, approval['id']) == before
    with sqlite3.connect(setup[0].path) as db:
        assert db.execute('SELECT count(*) FROM delivery_references').fetchone()[0] == 1


def test_reconcile_preserves_real_receipt_after_topic_is_reopened(setup):
    approval = approve(setup, text='One\n---\nTwo')
    calls = []
    send = sender(setup, calls)

    def lost(*args):
        send(*args)
        raise TimeoutError('Response lost')

    setup[2].dispatch_next(SCOPE, lost)
    setup[0].apply_plan(SCOPE, admit(setup[0], text='Fix', message_id='2'),
                        plan('Fix', topic_id=approval['topic_id'], expected_version=1))
    setup[2].reconcile(SCOPE, approval['id'], 0, 'receipt-' + calls[0][1])
    setup[2].dispatch_next(SCOPE, send)
    assert len(calls) == 1
    state = setup[2].inspect(SCOPE, approval['id'])
    assert state['state'] == 'invalid'
    assert state['parts'][0]['state'] == 'sent'
    assert state['parts'][0]['message_id'] == 'message-' + calls[0][1]


def test_other_scope_cannot_inspect_reconcile_or_dispatch_delivery(setup):
    approval = approve(setup)
    other = Scope('telegram', 'bot', 'other-owner', 'chat')
    calls = []
    assert setup[2].dispatch_next(other, sender(setup, calls))['status'] == 'empty'
    with pytest.raises(QueueError):
        setup[2].inspect(other, approval['id'])
    with pytest.raises(QueueError):
        setup[2].reconcile(other, approval['id'], 0, 'invented')
    assert calls == []


def test_not_sent_receipt_cannot_contain_a_message_id(setup):
    approval = approve(setup)
    send = sender(setup, [])

    def contradictory(*args):
        proof_id = send(*args)
        setup[1].outcomes[proof_id]['status'] = 'not_sent'
        return proof_id

    assert setup[2].dispatch_next(SCOPE, contradictory)['status'] == 'uncertain'
    assert setup[2].inspect(SCOPE, approval['id'])['parts'][0]['message_id'] is None


def test_receipt_storage_failure_cannot_commit_partial_reply_mapping(setup):
    approval = approve(setup)
    with sqlite3.connect(setup[0].path) as db:
        db.execute("CREATE TRIGGER fail_part_receipt BEFORE UPDATE ON delivery_parts "
                   "WHEN NEW.state='sent' BEGIN SELECT RAISE(ABORT, 'storage failure'); END")
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'uncertain'
    with sqlite3.connect(setup[0].path) as db:
        assert db.execute('SELECT count(*) FROM delivery_references').fetchone()[0] == 0
        db.execute('DROP TRIGGER fail_part_receipt')
    setup[2].reconcile(SCOPE, approval['id'], 0, 'receipt-' + calls[0][1])
    assert setup[2].inspect(SCOPE, approval['id'])['state'] == 'sent'
    assert len(calls) == 1


def test_cancellation_between_committed_intent_and_send_aborts_without_effect(setup):
    approval = approve(setup)

    def control(*args):
        with sqlite3.connect(setup[0].path) as db:
            sending = db.execute("SELECT 1 FROM delivery_parts WHERE state='sending'").fetchone()
        return 'cancelled' if sending else 'active'

    setup[1].control = control
    calls = []
    assert setup[2].dispatch_next(SCOPE, sender(setup, calls))['status'] == 'invalid'
    assert calls == []
    state = setup[2].inspect(SCOPE, approval['id'])
    assert state['state'] == 'invalid'
    assert state['attempts'][0]['state'] == 'aborted'


def test_cancelled_predecessor_invalidates_approved_child_delivery(setup):
    store, proofs, delivery = setup
    topics = store.apply_plan(SCOPE, admit(store, text='A B'), two_topics())
    parent = approve(setup, topic=topics[0])
    child = approve(setup, topic=topics[1])
    calls = []
    assert delivery.dispatch_next(SCOPE, sender(setup, calls))['approval_id'] == parent['id']
    proofs.states[parent['topic_id']] = 'cancelled'
    delivery.dispatch_next(SCOPE, sender(setup, calls))
    assert len(calls) == 1
    assert delivery.inspect(SCOPE, child['id'])['state'] == 'invalid'


def test_retry_keeps_no_send_evidence_and_rejects_previous_attempt_receipt(setup):
    approval = approve(setup)
    calls = []
    setup[2].dispatch_next(SCOPE, sender(setup, calls, outcome='not_sent'))
    old_receipt = 'receipt-' + calls[0][1]
    setup[2].reconcile(SCOPE, approval['id'], 0, old_receipt)
    setup[2].dispatch_next(SCOPE, sender(setup, calls))
    state = setup[2].inspect(SCOPE, approval['id'])
    assert [attempt['state'] for attempt in state['attempts']] == ['not_sent', 'sent']
    assert len({attempt['id'] for attempt in state['attempts']}) == 2
    with pytest.raises(QueueError):
        setup[2].reconcile(SCOPE, approval['id'], 0, old_receipt)
    assert setup[2].inspect(SCOPE, approval['id']) == state


def test_same_message_id_cannot_confirm_two_parts(setup):
    approval = approve(setup, text='One\n---\nTwo')
    calls = []
    send = sender(setup, calls)

    def duplicate(*args):
        receipt_id = send(*args)
        setup[1].outcomes[receipt_id]['message_id'] = 'same-message'
        return receipt_id

    assert setup[2].dispatch_next(SCOPE, duplicate)['status'] == 'uncertain'
    state = setup[2].inspect(SCOPE, approval['id'])
    assert [part['state'] for part in state['parts']] == ['sent', 'uncertain']
    with sqlite3.connect(setup[0].path) as db:
        assert db.execute('SELECT count(*) FROM delivery_references').fetchone()[0] == 1
