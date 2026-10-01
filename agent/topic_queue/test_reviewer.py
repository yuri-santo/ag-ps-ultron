"""No provider or profile files are consulted by these deterministic tests."""
import json
from types import SimpleNamespace

import pytest
from contract import QueueError


def test_disabled_reviewer_model_or_inactive_provider_is_rejected():
    import sqlite3
    from reviewer import require_enabled_route
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE providerConnections(provider TEXT,isActive INTEGER)')
        db.execute('CREATE TABLE kv(scope TEXT,key TEXT,value TEXT)')
        db.execute("INSERT INTO providerConnections VALUES('nvidia',1)")
        require_enabled_route(db, 'nvidia/model-a')
        db.execute("INSERT INTO kv VALUES('disabledModels','nvidia','[\"model-a\"]')")
        with pytest.raises(QueueError, match='disabled'):
            require_enabled_route(db, 'nvidia/model-a')
        db.execute('UPDATE providerConnections SET isActive=0')
        with pytest.raises(QueueError, match='enabled'):
            require_enabled_route(db, 'nvidia/model-b')


def test_reviewer_requires_exact_final_binding_and_actual_identity():
    from reviewer import validate_vote
    payload = {'verdict': 'approved', 'checks': ['fact checked'], 'issues': [], 'binding_hash': 'hash'}
    result = validate_vote(json.dumps(payload), binding='hash', served='provider/real', excluded='provider/producer')
    assert result['verdict'] == 'approved' and result['served_identity'] == 'provider/real'
    for patch in ({'binding_hash': 'other'}, {'issues': ['unresolved']}, {'checks': []}):
        with pytest.raises(QueueError):
            validate_vote(json.dumps(dict(payload, **patch)), binding='hash', served='provider/real', excluded='producer')
    with pytest.raises(QueueError):
        validate_vote(json.dumps(payload), binding='hash', served='producer', excluded='producer')


def test_revise_is_structured_feedback_not_approval():
    from reviewer import validate_vote
    payload = {'verdict': 'revise', 'checks': ['request'], 'issues': ['Missing answer'], 'binding_hash': 'hash'}
    result = validate_vote(json.dumps(payload), binding='hash', served='real', excluded='other')
    assert result['verdict'] == 'revise' and result['issues'] == ['Missing answer']


def test_worker_host_resets_profile_and_kanban_control_before_worker(monkeypatch, tmp_path):
    from worker_host import execute
    monkeypatch.setenv('HERMES_HOME', '/wrong/profile')
    monkeypatch.setenv('HERMES_KANBAN_TASK', 't_restricted')
    monkeypatch.setenv('HERMES_KANBAN_RUN_ID', '42')
    calls = []
    def factory(home):
        import os
        assert os.environ['HERMES_HOME'] == str(tmp_path)
        assert 'HERMES_KANBAN_TASK' not in os.environ
        assert 'HERMES_KANBAN_RUN_ID' not in os.environ
        return SimpleNamespace(run=lambda task, run: calls.append((task, run)))
    execute(str(tmp_path), 't_restricted', 42, factory=factory)
    assert calls == [('t_restricted', 42)]
