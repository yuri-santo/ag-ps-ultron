"""Gateway bridge tests against isolated native boards, never real accounts."""
import hashlib
import importlib
import json
import sqlite3

import pytest

from admission import Scope, QueueError
from contract import canonical

SCOPE = Scope('telegram', 'bot', 'owner', 'chat')


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    home = tmp_path / 'hermes'
    monkeypatch.setenv('HERMES_HOME', str(home))
    monkeypatch.delenv('HERMES_KANBAN_DB', raising=False)
    monkeypatch.delenv('HERMES_KANBAN_BOARD', raising=False)
    pytest.importorskip('hermes_cli.kanban_db')
    from runtime import Runtime
    result = Runtime(home, {'enabled': True, 'scopes': [json.loads(SCOPE.key())],
                         'roster': {'greg': 'Email pessoal', 'cerebro': 'Triagem e conversa'},
                         'authors': {'greg': 'Greg', 'cerebro': 'Cerebro'}})
    import native_guard
    monkeypatch.setattr(native_guard, '_runtime', lambda conn: result)
    original = result.kb.complete_task
    while hasattr(original, '__wrapped__'):
        original = original.__wrapped__
    monkeypatch.setattr(result.kb, 'complete_task', native_guard.guard_completion(original))
    return result


def proposal(text, split=False):
    spans = [(0, len(text))] if not split else [(0, 5), (6, len(text))]
    return canonical({'schema_version': 1, 'topics': [
        dict(key=str(i), title='Assunto ' + str(i), profile='greg', topic_id=None,
             expected_version=None, depends_on=[], spans=[dict(start=a, end=b, text=text[a:b], kind='request')])
        for i, (a, b) in enumerate(spans)], 'ignored': []})


def claim(runtime, card):
    with runtime.connect() as conn:
        result = runtime.kb.claim_task(conn, card)
    assert result is not None
    return result


def plan(runtime, text='emails', split=False):
    receipt = runtime.admit(SCOPE, text, 'm1')
    task = claim(runtime, receipt['card_id'])
    runtime.run(task.id, task.current_run_id, complete=lambda **kw: proposal(text, split))
    return runtime.store.card_intents(SCOPE)


def candidate(profile, task, **kwargs):
    answer = 'Consulta concluida com limites declarados.'
    return dict(status='ok', profile=profile, answer=answer, completed=True,
                model_review={'status': 'approved', 'completed': True, 'output_sha256': digest(answer)},
                producer={'provider': 'test', 'model': 'alias', 'served_model': 'actual-a'},
                response_sha256=digest(answer), evidence=[], session_id='s1')


def review(prepared, request, **kwargs):
    return dict(completed=True, verdict='approved', served_identity='actual-b',
                checks=['request and exact final text checked'], issues=[])


def finish(runtime, card):
    task = claim(runtime, card)
    runtime.run(task.id, task.current_run_id, worker=candidate, reviewer=review)


def test_admission_is_durable_idempotent_and_scope_bound(runtime):
    first = runtime.admit(SCOPE, 'emails', 'm1')
    assert runtime.admit(SCOPE, 'emails', 'm1') == first
    with runtime.connect() as conn:
        assert conn.execute('SELECT count(*) FROM tasks').fetchone()[0] == 1
    with pytest.raises(QueueError):
        runtime.admit(Scope('telegram', 'other-bot', 'owner', 'chat'), 'emails', 'm1')


def test_native_claimed_ingress_creates_ready_restricted_final_cards(runtime):
    rows = plan(runtime)
    assert len(rows) == 1
    with runtime.connect() as conn:
        task = runtime.kb.get_task(conn, rows[0]['native_card_id'])
        assert task.status == 'ready' and task.assignee == 'greg'
        assert conn.execute('SELECT count(*) FROM kanban_notify_subs').fetchone()[0] == 0


def test_completion_is_precommit_guarded_even_force(runtime):
    rows = plan(runtime)
    task = claim(runtime, rows[0]['native_card_id'])
    with runtime.connect() as conn:
        with pytest.raises(QueueError):
            runtime.kb.complete_task(conn, task.id, result='fake', force=True)
        with pytest.raises(QueueError):
            runtime.kb.complete_task(conn, task.id, result='fake', expected_run_id=task.current_run_id)
        assert runtime.kb.get_task(conn, task.id).status == 'running'


def test_independent_later_topic_can_finish_and_deliver_first(runtime):
    rows = plan(runtime, text='email agenda', split=True)
    finish(runtime, rows[1]['native_card_id'])
    sent = []
    def send(scope, attempt_id, text):
        kw = dict(scope=scope, attempt_id=attempt_id, text=text)
        sent.append(kw)
        return runtime.record_outcome(kw, '101')
    result = runtime.delivery.dispatch_next(SCOPE, send)
    assert len(sent) == 1 and sent[0]['text'].startswith('Greg: ')
    assert result['status'] == 'sent'
    assert runtime.delivery.dispatch_next(SCOPE, send)['status'] == 'empty'


def test_review_failure_retries_review_only_and_persists_candidate(runtime):
    row = plan(runtime)[0]
    task = claim(runtime, row['native_card_id'])
    calls = []
    def worker(*args, **kw):
        calls.append(1)
        return candidate(*args, **kw)
    runtime.run(task.id, task.current_run_id, worker=worker,
                reviewer=lambda *a, **kw: (_ for _ in ()).throw(TimeoutError()))
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, task.id).status == 'scheduled'
    runtime.maintain(now=10**12)
    retried = claim(runtime, task.id)
    runtime.run(task.id, retried.current_run_id, worker=worker, reviewer=review)
    assert calls == [1]
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, task.id).status == 'done'


def test_lost_execution_never_repeats_tools(runtime):
    row = plan(runtime)[0]
    task = claim(runtime, row['native_card_id'])
    runtime.mark_started(task.id, task.current_run_id)
    calls = []
    runtime.run(task.id, task.current_run_id, worker=lambda *a, **kw: calls.append(1))
    assert calls == []
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, task.id).status == 'blocked'


def test_formatter_no_emoji_keeps_utf16_parts_bounded():
    from runtime import format_parts
    result = format_parts('Greg: texto\n\n' + '\U0001f600' + 'a' * 9000)
    assert len(result) > 1 and all(len(p.encode('utf-16-le')) // 2 <= 3900 for p in result)
    assert '\U0001f600' not in ''.join(result)


def test_uncertain_transport_never_retries(runtime):
    finish(runtime, plan(runtime)[0]['native_card_id'])
    calls = []
    def lost(*args):
        calls.append(1)
        raise TimeoutError()
    runtime.delivery.dispatch_next(SCOPE, lost)
    runtime.delivery.dispatch_next(SCOPE, lost)
    assert calls == [1]


def test_reverse_order_dependencies_reconcile_without_stalling(runtime):
    receipt = runtime.admit(SCOPE, 'email agenda', 'm1')
    task = claim(runtime, receipt['card_id'])
    value = json.loads(proposal('email agenda', True))
    value['topics'][0]['depends_on'] = ['1']
    runtime.run(task.id, task.current_run_id, complete=lambda **kw: canonical(value))
    rows = runtime.store.card_intents(SCOPE)
    assert len(rows) == 2 and all(r['native_card_id'] for r in rows)
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, rows[0]['native_card_id']).status == 'blocked'
        assert runtime.kb.get_task(conn, rows[1]['native_card_id']).status == 'ready'
    finish(runtime, rows[1]['native_card_id'])
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, rows[0]['native_card_id']).status == 'ready'


def test_invalidated_card_is_parked_without_executing(runtime):
    row = plan(runtime)[0]
    task = claim(runtime, row['native_card_id'])
    runtime.control_scope(SCOPE, 'cancelled')
    calls = []
    runtime.run(task.id, task.current_run_id, worker=lambda *a, **kw: calls.append(1))
    assert calls == []
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, task.id).status == 'blocked'


def test_unknown_reply_stays_native_not_silently_lost(runtime):
    assert runtime.knows_reply(SCOPE, 'unknown') is False


def test_old_not_sent_receipt_does_not_poison_later_success(runtime):
    finish(runtime, plan(runtime)[0]['native_card_id'])
    def deferred(scope, attempt_id, text):
        return runtime.proofs.put('outcome', 'deferred', dict(id='deferred',
            scope=scope.key(), attempt_id=attempt_id, text_hash=digest(text),
            status='not_sent', message_id=None, retry_after=1))
    assert runtime.delivery.dispatch_next(SCOPE, deferred)['status'] == 'deferred'
    runtime.maintain(now=2)
    def sent(scope, attempt_id, text):
        return runtime.record_outcome(dict(scope=scope, attempt_id=attempt_id, text=text), '102')
    assert runtime.delivery.dispatch_next(SCOPE, sent)['status'] == 'sent'
    runtime.maintain(now=3)
    assert runtime.delivery.dispatch_next(SCOPE, sent)['status'] == 'empty'


def test_followup_context_contains_previous_approved_answer(runtime):
    row = plan(runtime)[0]
    finish(runtime, row['native_card_id'])
    topic = runtime.store.get_topic(SCOPE, row['topic_id'])
    request, context = runtime._request_context(SCOPE, dict(topic_id=row['topic_id'],
        version=2, contract=topic['contract']))
    assert candidate('greg', '')['answer'] in context


def test_initial_candidate_exemption_is_not_faked_as_review(runtime):
    row = plan(runtime)[0]
    task = claim(runtime, row['native_card_id'])
    def exempt(*args, **kwargs):
        result = candidate(*args, **kwargs)
        result['model_review']['status'] = 'not_required'
        return result
    runtime.run(task.id, task.current_run_id, worker=exempt,
                reviewer=lambda *a, **kw: dict(completed=False, verdict='blocked'))
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, task.id).status == 'scheduled'
    with runtime.delivery._transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM delivery_approvals').fetchone()[0] == 0


def test_revise_corrects_text_without_repeating_worker(runtime):
    row = plan(runtime)[0]
    task = claim(runtime, row['native_card_id'])
    calls = []
    def worker(*args, **kw):
        calls.append(1)
        return candidate(*args, **kw)
    runtime.run(task.id, task.current_run_id, worker=worker,
                reviewer=lambda *a, **kw: dict(completed=True, verdict='revise',
                    checks=['original request'], issues=['Missing limitation'], served_identity='actual-b'))
    runtime.maintain(now=10**12)
    task = claim(runtime, task.id)
    runtime.run(task.id, task.current_run_id, worker=worker, reviewer=review,
                rewriter=lambda *a, **kw: dict(answer='Resposta corrigida, com limitacao.', served_identity='actual-a'))
    assert calls == [1]
    with runtime.connect() as conn:
        assert runtime.kb.get_task(conn, task.id).status == 'done'
        assert 'corrigida' in runtime.kb.get_task(conn, task.id).result


def test_cancel_includes_untriaged_ingress_and_does_not_cancel_future_input(runtime):
    entry = runtime.admit(SCOPE, 'emails', 'm1')
    runtime.control_scope(SCOPE, 'cancelled')
    task = claim(runtime, entry['card_id'])
    calls = []
    runtime.run(task.id, task.current_run_id, complete=lambda **kw: calls.append(1))
    assert calls == [] and runtime.store.pending(SCOPE) == []
    later = runtime.admit(SCOPE, 'novo pedido', 'm2')
    assert later['ingress_id'] != entry['ingress_id']
    assert len(runtime.store.pending(SCOPE)) == 1


def test_old_approval_cannot_complete_reopened_cancelled_card(runtime):
    row = plan(runtime)[0]
    finish(runtime, row['native_card_id'])
    with runtime.connect() as db:
        old = runtime.kb.get_task(db, row['native_card_id'])
        db.execute("UPDATE tasks SET status='ready' WHERE id=?", (old.id,))
        db.commit()
    runtime.control_scope(SCOPE, 'cancelled')
    task = claim(runtime, old.id)
    with runtime.connect() as db:
        with pytest.raises(QueueError):
            runtime.kb.complete_task(db, task.id, result=old.result, expected_run_id=task.current_run_id, force=True)
        assert runtime.kb.get_task(db, task.id).status == 'running'
