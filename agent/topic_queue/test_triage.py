"""Proposal-only tests; no provider, gateway, tools or user database is used."""
import json
import sys
from types import SimpleNamespace

import pytest

from admission import QueueError, Scope, TopicStore
from test_admission import two_topics
from triage import NativeCompletion, parse_proposal, plan_ingress


SCOPE = Scope('telegram', 'bot', 'owner', 'chat')
ROSTER = {'greg': 'Email pessoal', 'thor': 'SAP', 'dona': 'Agenda'}


def proposal(text, profile='greg', **extra):
    topic = dict(key='one', title='Pedido', profile=profile, topic_id=None,
                 expected_version=None, depends_on=[], spans=[
                     dict(start=0, end=len(text), text=text, kind='request')])
    topic.update(extra)
    return dict(schema_version=1, topics=[topic], ignored=[])


@pytest.fixture
def store(tmp_path):
    return TopicStore(tmp_path / 'private' / 'queue.db', allowed_profiles=ROSTER)


def admit(store, text, message_id='1', scope=SCOPE, spans=None, reply_to=None):
    return store.admit(scope, message_id, text, request_spans=spans or [(0, len(text))],
                       authorized=True, reply_to=reply_to)


def test_entire_email_request_and_quotes_reach_model_without_sap_autorouting(store):
    text = 'Onde estao esses e-mails?\n29/09/2026: Easysapers UID 1729; NOTA SAP 2026'
    end = text.index('\n')
    ingress = admit(store, text, spans=[(0, end)])
    answer = proposal(text[:end])
    answer['ignored'] = [dict(start=end + 1, end=len(text), text=text[end + 1:], reason='untrusted')]
    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        return json.dumps(answer)
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=complete)
    assert result['status'] == 'planned'
    envelope = json.loads(calls[0]['user'])
    assert envelope['message']['text'] == text
    assert envelope['message']['request_spans'] == [[0, end]]
    assert 'UID' in calls[0]['system'] and 'SAP' in calls[0]['system']
    assert store.get_topic(SCOPE, result['topics'][0]['topic_id'])['contract']['profile'] == 'greg'


def test_two_independent_topics_keep_separate_proposals(store):
    text = 'Email. Agenda.'
    ingress = admit(store, text)
    value = proposal('Email.')
    second = proposal('Agenda.', 'dona')['topics'][0]
    second.update(key='two', spans=[dict(start=7, end=14, text='Agenda.', kind='request')])
    value['topics'].append(second)
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER,
                          complete=lambda **_: json.dumps(value))
    assert len(result['topics']) == 2
    assert all(not store.get_topic(SCOPE, x['topic_id'])['contract']['depends_on'] for x in result['topics'])
    assert all(not x['released'] for x in store.card_intents(SCOPE))


@pytest.mark.parametrize('raw', [
    '```json\n{}\n```', '{} trailing', '{"topics":[],"topics":[]}',
    '{"number":NaN}', '{"number":Infinity}', '[]', '', None,
])
def test_non_strict_json_is_rejected(raw):
    with pytest.raises(QueueError):
        parse_proposal(raw)


@pytest.mark.parametrize('kind', ['provider', 'malformed', 'unknown_profile', 'incomplete', 'quote'])
def test_failures_preserve_ingress_without_fallback_tool(store, kind):
    text = 'Email. quoted: publish'
    ingress = admit(store, text, spans=[(0, 6)])
    def complete(**_):
        if kind == 'provider':
            raise RuntimeError('provider private error must not reach result')
        if kind == 'malformed':
            return 'review approved'
        value = proposal('Email.', 'invented' if kind == 'unknown_profile' else 'greg')
        if kind != 'incomplete':
            value['ignored'] = [dict(start=7, end=len(text), text=text[7:], reason='untrusted')]
        if kind == 'quote':
            value = proposal(text)
        return json.dumps(value)
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=complete)
    assert result['status'] == 'pending'
    assert 'private error' not in json.dumps(result)
    assert len(store.pending(SCOPE)) == 1
    assert store.card_intents(SCOPE) == []


def test_known_reply_loads_same_scope_context_and_exact_version(store):
    old = store.apply_plan(SCOPE, admit(store, 'Email.'), proposal('Email.'))[0]
    store.record_delivery_reference(SCOPE, old['topic_id'], 1, 'sent-1')
    ingress = admit(store, 'Corrigir.', '2', reply_to='sent-1')
    def complete(**kwargs):
        context = json.loads(kwargs['user'])['topics']
        assert context[0]['topic_id'] == old['topic_id']
        assert context[0]['version'] == 1
        return json.dumps(proposal('Corrigir.', topic_id=old['topic_id'], expected_version=1))
    assert plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=complete)['status'] == 'planned'


def test_other_chat_context_refused_before_model(store):
    other = Scope('telegram', 'bot', 'owner', 'other')
    old = store.apply_plan(other, admit(store, 'Private.', scope=other), proposal('Private.'))[0]
    ingress = admit(store, 'Email.')
    calls = []
    with pytest.raises(QueueError):
        plan_ingress(store, SCOPE, ingress, roster=ROSTER,
                     context_ids=[old['topic_id']], complete=lambda **kw: calls.append(kw))
    assert not calls


def test_unknown_reply_waits_for_clarification_without_model(store):
    ingress = admit(store, 'Corrigir.', reply_to='unknown')
    calls = []
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=lambda **kw: calls.append(kw))
    assert result == {'status': 'pending', 'reason': 'reply_context_required'}
    assert not calls


def test_no_silent_truncation_or_paid_retry_on_configured_budget(store):
    text = 'Texto ' + 'x' * 16000
    ingress = admit(store, text)
    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        assert json.loads(kwargs['user'])['message']['text'] == text
        return json.dumps(proposal(text))
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=complete,
                          max_request_bytes=100)
    assert result == {'status': 'pending', 'reason': 'context_budget_exceeded'}
    assert not calls
    assert plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=complete)['status'] == 'planned'
    assert len(calls) == 1


def test_already_planned_ingress_does_not_call_model_again(store):
    ingress = admit(store, 'Email.')
    store.apply_plan(SCOPE, ingress, proposal('Email.'))
    assert plan_ingress(store, SCOPE, ingress, roster=ROSTER,
                       complete=lambda **_: pytest.fail('repeated call'))['status'] == 'not_pending'


def test_roster_must_be_trusted_and_match_allowlist(store):
    ingress = admit(store, 'Email.')
    with pytest.raises(QueueError):
        plan_ingress(store, SCOPE, ingress, roster={'evil': 'Invented profile'}, complete=None)


def test_model_cannot_reopen_topic_not_in_provided_context(store):
    old = store.apply_plan(SCOPE, admit(store, 'Email.'), proposal('Email.'))[0]
    ingress = admit(store, 'Nova agenda.', '2')
    value = proposal('Nova agenda.', 'dona', topic_id=old['topic_id'], expected_version=1)
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER,
                          complete=lambda **_: json.dumps(value))
    assert result['status'] == 'pending'
    assert store.revision_is_current(SCOPE, old['topic_id'], 1)


def test_model_cannot_substitute_a_newer_context_version(store):
    old = store.apply_plan(SCOPE, admit(store, 'Email.'), proposal('Email.'))[0]
    ingress = admit(store, 'Corrigir.', '2')
    def complete(**_):
        competing = admit(store, 'Outra correcao.', '3')
        store.apply_plan(SCOPE, competing, proposal('Outra correcao.', topic_id=old['topic_id'], expected_version=1))
        return json.dumps(proposal('Corrigir.', topic_id=old['topic_id'], expected_version=2))
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER, complete=complete,
                          context_ids=[old['topic_id']])
    assert result['status'] == 'pending'
    assert store.revision_is_current(SCOPE, old['topic_id'], 2)


@pytest.mark.parametrize('change', ['version', 'validity', 'contract'])
@pytest.mark.parametrize('continuation', [False, True])
def test_context_change_at_commit_preserves_pending(store, monkeypatch, change, continuation):
    parent, child = store.apply_plan(SCOPE, admit(store, 'A B'), two_topics())
    ingress = admit(store, 'Corrigir.', '2')
    competing = admit(store, 'Outra correcao.', '3')
    value = proposal('Corrigir.')
    if continuation:
        value['topics'][0].update(topic_id=child['topic_id'], expected_version=1)
    apply = store.apply_plan

    def change_before_commit(scope, ingress_id, plan, **kwargs):
        if change in ('version', 'validity'):
            target = child if change == 'version' else parent
            apply(SCOPE, competing, proposal('Outra correcao.',
                  topic_id=target['topic_id'], expected_version=1))
        else:
            with store._transaction() as db:
                contract = store._topic(db, SCOPE.key(), child['topic_id'])['contract']
                contract = json.loads(contract)
                contract['title'] = 'Changed context'
                db.execute('UPDATE versions SET contract=? WHERE topic_id=? AND version=1',
                           (json.dumps(contract), child['topic_id']))
        return apply(scope, ingress_id, plan, **kwargs)

    monkeypatch.setattr(store, 'apply_plan', change_before_commit)
    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER,
                          context_ids=[child['topic_id']], complete=lambda **_: json.dumps(value))
    assert result == {'status': 'pending', 'reason': 'proposal_not_accepted'}
    assert ingress in {item['id'] for item in store.pending(SCOPE)}
    assert len(store.card_intents(SCOPE)) == (2 if change == 'contract' else 3)


def test_stable_invalid_context_can_be_explicitly_replanned(store):
    parent, child = store.apply_plan(SCOPE, admit(store, 'A B'), two_topics())
    correction = admit(store, 'Outra correcao.', '2')
    store.apply_plan(SCOPE, correction, proposal('Outra correcao.',
                     topic_id=parent['topic_id'], expected_version=1))
    assert not store.revision_is_current(SCOPE, child['topic_id'], 1)
    ingress = admit(store, 'Pedido independente.', '3')

    def complete(**kwargs):
        context = json.loads(kwargs['user'])['topics'][0]
        assert context['valid'] is False
        return json.dumps(proposal('Pedido independente.',
                          topic_id=child['topic_id'], expected_version=1))

    result = plan_ingress(store, SCOPE, ingress, roster=ROSTER,
                          context_ids=[child['topic_id']], complete=complete)
    assert result['status'] == 'planned'
    assert store.revision_is_current(SCOPE, child['topic_id'], 2)


def native_modules(monkeypatch, *, finish='stop', tool_calls=None, failure=False, affinity=None):
    calls, affinity_events = [], []
    def call(**kwargs):
        calls.append(kwargs)
        if failure:
            raise RuntimeError('private upstream detail')
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
            message=SimpleNamespace(content='{}', tool_calls=tool_calls))])
    monkeypatch.setitem(sys.modules, 'agent.auxiliary_client', SimpleNamespace(call_llm=call))
    monkeypatch.setitem(sys.modules, 'agent.portal_tags', SimpleNamespace(
        get_affinity_scope=lambda: affinity,
        set_affinity_scope=lambda value: affinity_events.append(value) or 'token',
        reset_affinity_scope=lambda token: affinity_events.append(('reset', token))))
    return calls, affinity_events


def test_native_completion_uses_configured_auxiliary_route_without_tools(monkeypatch):
    calls, events = native_modules(monkeypatch)
    complete = NativeCompletion(timeout=45, max_tokens=2048)
    assert complete(system='s', user='u', request_id='id') == '{}'
    assert calls[0]['task'] == 'kanban_decomposer'
    assert calls[0]['tools'] == []
    assert calls[0]['timeout'] == 45 and calls[0]['max_tokens'] == 2048
    assert not {'api_key', 'provider', 'model', 'base_url'} & calls[0].keys()
    assert events == ['ultron-topic:id', ('reset', 'token')]


@pytest.mark.parametrize('params', [dict(finish='length'), dict(finish='tool_calls'),
                                 dict(tool_calls=[{}]), dict(failure=True)])
def test_native_completion_refuses_partial_or_tool_response_and_resets(monkeypatch, params):
    _, events = native_modules(monkeypatch, **params)
    with pytest.raises(QueueError):
        NativeCompletion()(system='s', user='u', request_id='id')
    assert events[-1] == ('reset', 'token')


def test_native_completion_preserves_existing_affinity(monkeypatch):
    _, events = native_modules(monkeypatch, affinity='existing')
    NativeCompletion()(system='s', user='u', request_id='id')
    assert not events
