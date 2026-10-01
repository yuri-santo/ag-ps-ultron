"""Offline migration for the inspected live worker; no runtime installation.

Preserve runtime completion and hash-only proof. These fields are observations,
not topic approval: the importing host must verify the policy, version and run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile


SOURCE_SHA256 = 'be0538ceb701c60e2f86bea7de1ff2d002d590cf6add36361f671ac05ad8cbc0'
ENTRY = '\n\ndef execute(request):\n'
ANCHOR = """        return {'status': 'error' if failed else 'ok', 'profile': profile, 'answer': answer,
                'failed': failed, 'session_id': str(agent.session_id),
                'state_db': str(database.db_path), 'tools': names,
                'parent_session_id': request.get('parent_session_id', '')}
"""
REPLACEMENT = """        proof = _worker_proof(result, agent, failed)
        failed = failed or proof.pop('_proof_rejected')
        return {'status': 'error' if failed else 'ok', 'profile': profile,
                'answer': '' if failed else answer,
                'failed': failed, 'session_id': str(agent.session_id),
                'state_db': str(database.db_path), 'tools': names,
                'parent_session_id': request.get('parent_session_id', ''), **proof}
"""
HELPERS = '''

def _worker_proof(result, agent, failed):
    """Export runtime metadata without tool text, reviewer prose or candidates."""
    import hashlib
    import re
    from agent.ultron_review_gate import tool_evidence

    def digest(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def identifier(value):
        return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/+\\-]{1,200}', value) else None

    def sha256(value):
        return value if isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) else None

    completed = result.get('completed') is True
    answer = result.get('final_response')
    rejected = bool(failed or not completed or result.get('failed') or result.get('partial')
                    or result.get('interrupted') or not isinstance(answer, str) or not answer.strip())
    response_hash = digest(answer) if isinstance(answer, str) else None
    raw = result.get('model_review')
    review = None
    if raw is not None:
        if not isinstance(raw, dict):
            rejected = True
            review = {'status': 'invalid', 'completed': False}
        else:
            status = raw.get('status')
            statuses = {'approved', 'not_required', 'pending_review', 'revision_required', 'validation_failed'}
            status = status if isinstance(status, str) and status in statuses else 'invalid'
            review = {'status': status, 'completed': raw.get('completed') is True,
                      'output_sha256': sha256(raw.get('output_sha256')),
                      'fingerprint': sha256(raw.get('fingerprint')),
                      'record_sha256': digest(json.dumps(raw, sort_keys=True, ensure_ascii=False,
                                                         allow_nan=False, separators=(',', ':'))),
                      'reviews': []}
            for field in ('revision', 'network_calls', 'reserved_tokens', 'policy_version'):
                value = raw.get(field)
                if type(value) is int and value >= 0:
                    review[field] = value
            validation = raw.get('validation')
            if isinstance(validation, dict):
                review['validation'] = {'ok': validation.get('ok') is True}
            for item in raw.get('reviews') or []:
                if not isinstance(item, dict):
                    rejected = True
                    continue
                reviewer, verdict = item.get('reviewer'), item.get('verdict')
                if not isinstance(reviewer, dict) or not isinstance(verdict, dict):
                    rejected = True
                    continue
                vote = verdict.get('verdict')
                vote = vote if isinstance(vote, str) and vote in {'approved', 'revise', 'blocked'} else 'invalid'
                issues, checks = verdict.get('issues'), verdict.get('checks')
                review['reviews'].append({
                    'candidate_sha256': sha256(item.get('candidate_sha256')),
                    'reviewer': {'model': identifier(reviewer.get('model')),
                                 'served_model': identifier(reviewer.get('served_model'))},
                    'verdict': {'verdict': vote, 'issue_count': len(issues) if isinstance(issues, list) else None,
                                'check_count': len(checks) if isinstance(checks, list) else None}})
            rejected = bool(rejected or not review['completed'] or status not in {'approved', 'not_required'}
                            or review['output_sha256'] != response_hash)
    evidence = []
    for item in tool_evidence(result.get('messages') or []):
        if isinstance(item, dict) and item.get('kind') == 'tool_receipt':
            receipt = {'kind': 'tool_receipt', 'tool': identifier(item.get('tool')),
                       'call_id': identifier(item.get('call_id')),
                       'result_sha256': sha256(item.get('result_sha256'))}
            if any(value is None for value in receipt.values()):
                rejected = True
            else:
                evidence.append(receipt)
    return {'proof_schema_version': 1, 'completed': completed, 'model_review': review,
            'producer': {'provider': identifier(getattr(agent, 'provider', None)),
                         'model': identifier(getattr(agent, 'model', None)),
                         'served_model': identifier(getattr(agent, 'last_served_model', None))},
            'turn_id': identifier(getattr(agent, '_current_turn_id', None)),
            'response_sha256': None if rejected else response_hash,
            'evidence': evidence, '_proof_rejected': rejected}
'''


def patch_file(path):
    """Validate exact input, back up privately, then atomically replace one worker."""
    path = Path(path)
    if path.name != 'worker.py' or path.is_symlink() or not path.is_file():
        raise ValueError('unexpected_target')
    original = path.read_bytes()
    source = original.decode('utf-8')
    # Idempotence is checked by reconstructing the pinned source, never by a marker alone.
    if source.count(HELPERS + ENTRY) == 1 and source.count(REPLACEMENT) == 1:
        restored = source.replace(HELPERS + ENTRY, ENTRY, 1).replace(REPLACEMENT, ANCHOR, 1)
        if hashlib.sha256(restored.encode()).hexdigest() == SOURCE_SHA256:
            return False
    if (hashlib.sha256(original).hexdigest() != SOURCE_SHA256
            or source.count(ENTRY) != 1 or source.count(ANCHOR) != 1
            or '_worker_proof' in source):
        raise RuntimeError('upstream_worker_changed')
    updated = source.replace(ENTRY, HELPERS + ENTRY, 1).replace(ANCHOR, REPLACEMENT, 1).encode()
    compile(updated, str(path), 'exec')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = path.with_name(path.name + '.bak-ultron-proof-' + stamp)
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.worker-proof-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        if path.is_symlink() or path.read_bytes() != original:
            raise RuntimeError('target_changed_during_patch')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    print('patched' if patch_file(parser.parse_args().path) else 'already patched')
