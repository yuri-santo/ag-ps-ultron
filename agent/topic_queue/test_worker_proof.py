"""Patch a temporary source file; never invoke a real agent or private store."""
import hashlib
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


RETURN = """        return {'status': 'error' if failed else 'ok', 'profile': profile, 'answer': answer,
                'failed': failed, 'session_id': str(agent.session_id),
                'state_db': str(database.db_path), 'tools': names,
                'parent_session_id': request.get('parent_session_id', '')}
"""
SOURCE = ("import contextlib\nimport json\nimport os\nfrom pathlib import Path\nimport sys\n"
          "\n\ndef execute(request):\n    if True:\n"
          "        failed = result.get('completed') is not True\n" + RETURN)


def patcher():
    spec = importlib.util.find_spec('patch_worker_proof')
    assert spec is not None, 'Worker proof migration has not been implemented'
    return importlib.import_module('patch_worker_proof')


def patched_namespace(tmp_path, monkeypatch):
    module = patcher()
    monkeypatch.setattr(module, 'SOURCE_SHA256', hashlib.sha256(SOURCE.encode()).hexdigest())
    path = tmp_path / 'worker.py'
    path.write_text(SOURCE, encoding='utf-8')
    assert module.patch_file(path)
    namespace = {'__name__': 'test_worker'}
    exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
    return namespace, path, module


def runtime():
    return SimpleNamespace(session_id='session-42', provider='openrouter',
                           model='family/requested', last_served_model='family/actual')


def result():
    answer = 'Approved answer.'
    digest = hashlib.sha256(answer.encode()).hexdigest()
    return dict(completed=True, final_response=answer,
                model_review=dict(status='approved', completed=True, output_sha256=digest,
                                  fingerprint='b' * 64, revision=2, network_calls=3,
                                  reserved_tokens=100, validation={'ok': True},
                                  reviews=[dict(candidate_sha256=digest,
                                                reviewer={'model': 'other/requested',
                                                          'served_model': 'other/actual'},
                                                verdict={'verdict': 'approved', 'issues': [],
                                                         'checks': ['private review note']})]),
                messages=[{'role': 'user', 'content': 'request'},
                          {'role': 'assistant', 'tool_calls': [
                              {'id': 'call-1', 'function': {'name': 'domain_read',
                                                          'arguments': 'private arguments'}}]},
                          {'role': 'tool', 'tool_call_id': 'call-1', 'content': 'secret result'}])


def tool_evidence_stub(monkeypatch):
    # The installed helper owns current-turn extraction; the patch only exports hashes.
    import sys
    import types
    module = types.ModuleType('agent.ultron_review_gate')
    def tool_evidence(messages):
        assert messages[-1]['content'] == 'secret result'
        return [dict(kind='tool_receipt', tool='domain_read', call_id='call-1',
                     result_sha256=hashlib.sha256(b'secret result').hexdigest(),
                     arguments_excerpt='private arguments', result_excerpt='secret result')]
    module.tool_evidence = tool_evidence
    monkeypatch.setitem(sys.modules, 'agent.ultron_review_gate', module)


def test_preserves_runtime_identity_completion_and_hash_only_receipts(tmp_path, monkeypatch):
    ns, _, _ = patched_namespace(tmp_path, monkeypatch)
    tool_evidence_stub(monkeypatch)
    data = result()
    data['producer'] = {'provider': 'forged', 'model': 'forged'}
    data['model_review'].update(visible_text='private candidate', record_path='/private/review.json')
    proof = ns['_worker_proof'](data, runtime(), False)
    assert proof['completed'] is True
    assert proof['producer'] == dict(provider='openrouter', model='family/requested',
                                     served_model='family/actual')
    assert proof['response_sha256'] == hashlib.sha256(b'Approved answer.').hexdigest()
    assert proof['evidence'] == [dict(kind='tool_receipt', tool='domain_read', call_id='call-1',
                                     result_sha256=hashlib.sha256(b'secret result').hexdigest())]
    assert proof['model_review']['output_sha256'] == proof['response_sha256']
    assert proof['model_review']['reviews'][0]['verdict'] == {'verdict': 'approved', 'issue_count': 0,
                                                           'check_count': 1}
    serialized = json.dumps(proof)
    for private in ('secret result', 'private arguments', 'private candidate', 'private review note',
                    '/private/', 'forged'):
        assert private not in serialized


def test_unvalidated_delivery_is_not_discarded_or_marked_approved(tmp_path, monkeypatch):
    ns, _, _ = patched_namespace(tmp_path, monkeypatch)
    tool_evidence_stub(monkeypatch)
    data = result()
    data['model_review'].update(status='unvalidated', approval_completed=False, confidence='limited',
                                delivery_notice='Confianca limitada', reviews=[])
    proof = ns['_worker_proof'](data, runtime(), False)
    assert proof['_proof_rejected'] is False
    assert proof['model_review']['status'] == 'unvalidated'
    assert proof['model_review']['approval_completed'] is False
    assert proof['model_review']['confidence'] == 'limited'


@pytest.mark.parametrize('change', [
    {'completed': False}, {'failed': True}, {'partial': True}, {'interrupted': True},
    {'model_review': {'completed': False, 'status': 'revision_required', 'visible_text': 'reject me'}},
    {'model_review': {'completed': True, 'status': 'revision_required'}},
    {'model_review': 'invalid'},
    {'model_review': {'completed': True, 'status': 'approved', 'output_sha256': 'f' * 64}},
])
def test_failed_or_unbound_candidate_has_no_response_proof(tmp_path, monkeypatch, change):
    ns, _, _ = patched_namespace(tmp_path, monkeypatch)
    tool_evidence_stub(monkeypatch)
    data = result()
    data.update(change)
    proof = ns['_worker_proof'](data, runtime(), False)
    assert proof['_proof_rejected'] is True
    assert proof['response_sha256'] is None
    assert 'reject me' not in json.dumps(proof)


def test_no_review_is_reported_as_absent_without_inventing_approval(tmp_path, monkeypatch):
    ns, _, _ = patched_namespace(tmp_path, monkeypatch)
    tool_evidence_stub(monkeypatch)
    data = result()
    data['model_review'] = None
    proof = ns['_worker_proof'](data, runtime(), False)
    assert proof['model_review'] is None
    assert proof['_proof_rejected'] is False
    assert proof['completed'] is True


def test_current_turn_receipts_from_installed_helper_are_hash_only(tmp_path, monkeypatch):
    pytest.importorskip('agent.ultron_review_gate')
    ns, _, _ = patched_namespace(tmp_path, monkeypatch)
    data = result()
    data['messages'] = [
        {'role': 'user', 'content': 'old request'},
        {'role': 'tool', 'tool_call_id': 'old-call', 'content': 'old tool result'},
        *data['messages'],
    ]
    proof = ns['_worker_proof'](data, runtime(), False)
    assert proof['evidence'] == [dict(kind='tool_receipt', tool='domain_read', call_id='call-1',
                                     result_sha256=hashlib.sha256(b'secret result').hexdigest())]
    assert 'old tool result' not in json.dumps(proof)
    assert 'secret result' not in json.dumps(proof)


def test_invalid_receipt_never_creates_usable_response_proof(tmp_path, monkeypatch):
    ns, _, _ = patched_namespace(tmp_path, monkeypatch)
    tool_evidence_stub(monkeypatch)
    import sys
    monkeypatch.setattr(sys.modules['agent.ultron_review_gate'], 'tool_evidence',
                        lambda messages: [dict(kind='tool_receipt', tool='domain_read',
                                               call_id='call-1', result_sha256='not-a-hash')])
    proof = ns['_worker_proof'](result(), runtime(), False)
    assert proof['_proof_rejected'] is True
    assert proof['response_sha256'] is None and proof['evidence'] == []


def test_patch_return_discards_failed_answer_and_preserves_original_guard(tmp_path, monkeypatch):
    ns, path, module = patched_namespace(tmp_path, monkeypatch)
    tool_evidence_stub(monkeypatch)
    data = result()
    data['model_review']['completed'] = False
    ns.update(result=data, agent=runtime(), failed=True, profile='pink', answer='private rejected answer',
              database=SimpleNamespace(db_path='/temporary/state.db'), names=['memory'])
    payload = ns['execute']({'parent_session_id': 'parent'})
    assert payload['answer'] == '' and payload['status'] == 'error'
    assert payload['completed'] is True and payload['model_review']['completed'] is False
    assert 'private rejected answer' not in json.dumps(payload)
    assert not module.patch_file(path)
    backups = list(tmp_path.glob('worker.py.bak-ultron-proof-*'))
    assert len(backups) == 1 and backups[0].read_bytes() == SOURCE.encode()
    assert path.read_bytes().startswith(SOURCE.split('\n\ndef execute')[0].encode())


def test_refuses_unknown_source_before_backup_or_write(tmp_path):
    module = patcher()
    path = tmp_path / 'worker.py'
    path.write_text(SOURCE, encoding='utf-8')
    with pytest.raises(RuntimeError, match='upstream_worker_changed'):
        module.patch_file(path)
    assert path.read_bytes() == SOURCE.encode()
    assert list(tmp_path.iterdir()) == [path]


def test_refuses_changed_already_patched_source(tmp_path, monkeypatch):
    _, path, module = patched_namespace(tmp_path, monkeypatch)
    path.write_bytes(path.read_bytes() + b'\n# unreviewed change\n')
    with pytest.raises(RuntimeError, match='upstream_worker_changed'):
        module.patch_file(path)


def test_refuses_unknown_anchor_even_with_expected_digest(tmp_path, monkeypatch):
    module = patcher()
    source = SOURCE.replace("'state_db'", "'changed'")
    monkeypatch.setattr(module, 'SOURCE_SHA256', hashlib.sha256(source.encode()).hexdigest())
    path = tmp_path / 'worker.py'
    path.write_text(source, encoding='utf-8')
    with pytest.raises(RuntimeError, match='upstream_worker_changed'):
        module.patch_file(path)


def test_refuses_symlink_without_changing_target(tmp_path):
    module = patcher()
    target = tmp_path / 'original.py'
    target.write_text(SOURCE, encoding='utf-8')
    path = tmp_path / 'worker.py'
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip('Symlink creation unavailable')
    with pytest.raises(ValueError, match='unexpected_target'):
        module.patch_file(path)
    assert target.read_bytes() == SOURCE.encode()


def test_live_worker_source_in_temporary_copy_only(tmp_path):
    source = os.environ.get('ULTRON_WORKER_SOURCE')
    if not source:
        pytest.skip('Set ULTRON_WORKER_SOURCE to opt in to source-only installed-worker check')
    module = patcher()
    path = tmp_path / 'worker.py'
    original = Path(source).read_bytes()
    path.write_bytes(original)
    assert module.patch_file(path)
    assert not module.patch_file(path)
    assert Path(source).read_bytes() == original
    updated = path.read_bytes()
    for preserved in (b"'terminal', 'execute_code', 'send_message', 'delegate_task'",
                      b'enabled_toolsets=toolsets', b'register_legal_tools', b'register_agent_tools',
                      b'max_iterations=12', b'run_budget_seconds=150'):
        assert preserved in updated
