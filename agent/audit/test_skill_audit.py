import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from skill_audit import SkillAudit, scan_command, snapshot


def test_command_is_offline_readonly_unprivileged_and_pinned(tmp_path):
    command = scan_command('sha256:' + 'a' * 64, tmp_path)
    for item in ('none', '--read-only', 'ALL', 'no-new-privileges', '65534:65534', '--no-llm', '--fail-on-incomplete'):
        assert item in command
    assert '--privileged' not in command and '/var/run/docker.sock' not in ' '.join(command)
    assert not any('API_KEY' in x for x in command)
    assert 'readonly' in command[command.index('--mount') + 1]
    assert command[command.index('--pull') + 1] == 'never'
    with pytest.raises(ValueError):
        scan_command('skillspector:latest', tmp_path)


def test_restrictive_umask_keeps_snapshot_readable_by_scanner(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'SKILL.md').write_text('A skill')
    (source / 'references').mkdir()
    (source / 'references/example.md').write_text('A reference')
    old = os.umask(0o077)
    try:
        snapshot(source, tmp_path / 'copy')
    finally:
        os.umask(old)
    for path in (tmp_path / 'copy', tmp_path / 'copy/references'):
        assert path.stat().st_mode & 0o777 == 0o755
    assert (tmp_path / 'copy/SKILL.md').stat().st_mode & 0o777 == 0o444


def test_snapshot_preserves_content_and_rejects_links_secrets_specials(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'SKILL.md').write_text('A skill')
    (source / 'run.py').write_text('print(1)')
    first = snapshot(source, tmp_path / 'copy')
    assert len(first['files']) == 2
    assert (tmp_path / 'copy' / 'run.py').read_text() == 'print(1)'
    (source / 'secret-link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='link'):
        snapshot(source, tmp_path / 'bad')
    (source / 'secret-link').unlink()
    (source / '.env').write_text('PRIVATE')
    with pytest.raises(ValueError, match='sensitive'):
        snapshot(source, tmp_path / 'bad2')


def test_unknown_skill_never_executes(tmp_path):
    calls = []
    audit = SkillAudit({}, tmp_path / 'reports', 'sha256:' + 'a' * 64,
                       runner=lambda *a, **k: calls.append(a))
    with pytest.raises(ValueError):
        audit.scan('/etc/passwd')
    assert not calls


def test_no_credentials_or_extra_mounts_and_no_safety_claim(tmp_path, monkeypatch):
    skill = tmp_path / 'skill'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('Example')
    monkeypatch.setenv('MY_SECRET', 'never-inherit')
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert 'MY_SECRET' not in kwargs['env']
        kwargs['stdout'].write(json.dumps({'findings': [], 'risk_score': 0}).encode())
        return SimpleNamespace(returncode=0)
    audit = SkillAudit({'example': skill}, tmp_path / 'reports', 'sha256:' + 'a' * 64, runner=run)
    result = audit.scan('example')
    assert result['approved'] is False and result['coverage'] == 'offline_static_only'
    assert result['finding_count'] == 0 and result['source_sha256']
    assert len(calls) == 1
    assert Path(result['report_path']).stat().st_mode & 0o777 == 0o600


def test_incomplete_scans_cannot_be_reported_complete(tmp_path):
    skill = tmp_path / 'skill'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('Example')
    def run(command, **kwargs):
        kwargs['stdout'].write(b'{"findings":[],"execution_successful":false}')
        return SimpleNamespace(returncode=1)
    audit = SkillAudit({'example': skill}, tmp_path / 'reports', 'sha256:' + 'a' * 64, runner=run)
    result = audit.scan('example')
    assert result['status'] == 'needs_review' and result['approved'] is False


def test_upstream_issues_and_partial_analysis_are_preserved(tmp_path):
    skill = tmp_path / 'skill'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('Example')
    def run(command, **kwargs):
        kwargs['stdout'].write(json.dumps({'issues': [{'id': 'finding'}],
            'execution_successful': True, 'analysis_completeness': {'is_complete': False,
                'status': 'partial', 'ledger_exceptions': [{'reason_code': 'reference_missing'}]}}).encode())
        return SimpleNamespace(returncode=0)
    result = SkillAudit({'example': skill}, tmp_path / 'reports', 'sha256:'+'a'*64, runner=run).scan('example')
    assert result['finding_count'] == 1
    assert result['status'] == 'needs_review'
    assert result['analysis_complete'] is False
