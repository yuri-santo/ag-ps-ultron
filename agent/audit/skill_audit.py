"""Offline static skill audit. Findings are untrusted evidence, never approval."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import uuid


SENSITIVE = re.compile(r'(?i)(^\.env(?:\.|$)|cookies?|credentials?|tokens?\.json|private.?key|^config\.yaml$)')


def snapshot(source, destination):
    source, destination = Path(source), Path(destination)
    if any(p.is_symlink() for p in (source, *source.parents)) or not source.is_dir():
        raise ValueError('Source must be a real directory without links')
    if not (source / 'SKILL.md').is_file():
        raise ValueError('Expected a skill directory')
    files, total = [], 0
    for path in sorted(source.rglob('*')):
        if any(p in ('.git', '__pycache__') for p in path.relative_to(source).parts):
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError('Source link rejected')
        if SENSITIVE.search(path.name):
            raise ValueError('Potentially sensitive filename rejected')
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode) or path.stat().st_nlink != 1:
            raise ValueError('Special or hardlinked source rejected')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            data = stream.read(20 * 1024 * 1024 + 1)
        total += len(data)
        if total > 20 * 1024 * 1024 or len(files) >= 2000:
            raise ValueError('Skill exceeds explicit audit snapshot budget')
        relative = path.relative_to(source).as_posix()
        files.append((relative, data))
    # No scanner receives the original tree, home, credentials or Docker socket.
    destination.mkdir(mode=0o755)
    destination.chmod(0o755)
    manifest = []
    for relative, data in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        for parent in target.parents:
            if parent == destination:
                break
            parent.chmod(0o755)
        with target.open('xb') as stream:
            stream.write(data)
        target.chmod(0o444)
        manifest.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return {'sha256': digest, 'files': manifest}


def scan_command(image, source):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('An installed immutable image ID is required')
    path = str(Path(source).resolve())
    if ',' in path or '\n' in path:
        raise ValueError('Invalid bind source')
    return ['/usr/bin/docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--user', '65534:65534', '--pids-limit', '128', '--memory', '1g',
            '--cpus', '1', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777',
            '--mount', 'type=bind,src=' + path + ',dst=/scan/input,readonly',
            image, 'scan', '/scan/input', '--no-llm', '--format', 'json',
            '--fail-on-incomplete', '--fail-on-findings']


class SkillAudit:
    def __init__(self, catalog, reports, image, *, runner=subprocess.run):
        self.catalog = dict(catalog)
        self.reports, self.image, self.runner = Path(reports), image, runner

    def scan(self, skill):
        if not isinstance(skill, str) or skill not in self.catalog:
            raise ValueError('Select a skill ID from the trusted installed catalog')
        if any(p.is_symlink() for p in (self.reports, *self.reports.parents)):
            raise ValueError('Report directory cannot be a link')
        self.reports.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.reports.chmod(0o700)
        report = self.reports / (uuid.uuid4().hex + '.json')
        with tempfile.TemporaryDirectory(prefix='ultron-skill-audit-') as temporary:
            root = Path(temporary)
            source = snapshot(self.catalog[skill], root / 'input')
            command = scan_command(self.image, root / 'input')
            name = 'ultron-audit-' + uuid.uuid4().hex
            command[2:2] = ['--name', name]
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8',
                   'DOCKER_HOST': 'unix:///var/run/docker.sock'}
            with (root / 'stdout').open('w+b') as output, (root / 'stderr').open('w+b') as errors:
                try:
                    result = self.runner(command, stdout=output, stderr=errors, env=env,
                                         timeout=120, check=False)
                except subprocess.TimeoutExpired:
                    # Killing the Docker client alone can leave the isolated container alive.
                    subprocess.run(['/usr/bin/docker', 'rm', '-f', name], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    raise ValueError('Audit timed out; no approval granted') from None
                output.seek(0)
                raw = output.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Audit output exceeded explicit report budget')
            try:
                evidence = json.loads(raw)
                if not isinstance(evidence, dict):
                    raise ValueError()
            except ValueError:
                raise ValueError('Scanner did not return a valid report; no approval granted') from None
        findings = evidence.get('issues', evidence.get('findings', []))
        completeness = evidence.get('analysis_completeness', {})
        complete = (isinstance(completeness, dict) and completeness.get('is_complete') is True
                    and evidence.get('execution_successful') is True)
        envelope = {'skill_id': skill, 'source_sha256': source['sha256'], 'source_files': source['files'],
                    'image': self.image, 'coverage': 'offline_static_only', 'approved': False,
                    'status': 'scanned' if result.returncode == 0 and complete and not findings else 'needs_review',
                    'analysis_complete': complete,
                    'finding_count': len(findings) if isinstance(findings, list) else None,
                    'scanner_exit_code': result.returncode, 'scanner_report': evidence}
        fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(envelope, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        return {k: v for k, v in envelope.items() if k not in ('scanner_report', 'source_files')} | {
            'report_path': str(report), 'limitation': 'No LLM, remote dependency or transitive analysis; findings require review.'}
