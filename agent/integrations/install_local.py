"""Install native adapters at idle, with a private backup; never changes SOULs/jobs."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import yaml

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE.parent / 'topic_queue'))
from patch_worker_proof import ANCHOR, ENTRY, HELPERS, REPLACEMENT, SOURCE_SHA256

WORKER_ANCHOR = "    model = cfg['model']['default']\n"
WORKER_EXTRA = """    from ultron_adoption import register_worker_tools
    adoption_set, adoption_prompt = register_worker_tools(registry.register, profile, home, base)
    if adoption_set:
        toolsets.append(adoption_set)
        extra_prompt += adoption_prompt
"""


def worker_source(source):
    original = source.replace(WORKER_EXTRA, '', 1)
    if HELPERS + ENTRY in original:
        original = original.replace(HELPERS + ENTRY, ENTRY, 1).replace(REPLACEMENT, ANCHOR, 1)
    if hashlib.sha256(original.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unknown native worker revision; inspect before installing')
    changed = original.replace(ENTRY, HELPERS + ENTRY, 1).replace(ANCHOR, REPLACEMENT, 1)
    if changed.count(WORKER_ANCHOR) != 1:
        raise ValueError('Unexpected worker model anchor')
    changed = changed.replace(WORKER_ANCHOR, WORKER_EXTRA + WORKER_ANCHOR, 1)
    compile(changed, '<worker>', 'exec')
    return changed


def configure(config):
    result = copy.deepcopy(config)
    enabled = result.setdefault('plugins', {}).setdefault('enabled', [])
    if not isinstance(enabled, list):
        raise ValueError('Unexpected plugin configuration')
    if 'ultron_adoption' not in enabled:
        enabled.append('ultron_adoption')
    for platform in ('cli', 'telegram', 'cron'):
        tools = result['platform_toolsets'][platform]
        if not isinstance(tools, list):
            raise ValueError('Unexpected native toolsets')
        if 'ultron_adoption' not in tools:
            tools.append('ultron_adoption')
    return result


def stage_plugin(destination):
    destination = Path(destination)
    destination.mkdir(mode=0o700)
    files = {name: SOURCE / name for name in ('__init__.py', 'tools_adapter.py', 'plugin.yaml')}
    files.update({'skill_audit.py': SOURCE.parent / 'audit/skill_audit.py',
                  'import_transcriptonic.py': SOURCE.parent / 'meeting/import_transcriptonic.py'})
    for name, source in files.items():
        content = source.read_bytes()
        if name.endswith('.py'):
            compile(content, name, 'exec')
        (destination / name).write_bytes(content)
        (destination / name).chmod(0o600)
    return destination


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix='.adoption-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def install(home, image, backup):
    home, backup = Path(home), Path(backup)
    if not home.is_absolute() or any(p.is_symlink() for p in (home, *home.parents)):
        raise ValueError('Expected a real absolute Hermes home')
    if backup.exists() or not backup.is_absolute() or any(p.is_symlink() for p in backup.parents):
        raise ValueError('Expected a new private backup directory')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Expected immutable installed Docker image ID')
    found = subprocess.run(['/usr/bin/docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                           capture_output=True, text=True, check=True, timeout=15,
                           env={'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent',
                                'DOCKER_HOST': 'unix:///var/run/docker.sock',
                                'DOCKER_CONFIG': '/nonexistent'}).stdout.strip()
    if found != image:
        raise ValueError('Image identity mismatch')
    config_path = home / 'config.yaml'
    worker_path = home / 'plugins/ultron_team/worker.py'
    initial = {path: path.read_bytes() for path in (config_path, worker_path)}
    config = configure(yaml.safe_load(initial[config_path]))
    changed_worker = worker_source(initial[worker_path].decode())
    skills = {str(p.parent.relative_to(home / 'profiles/money/skills')).replace('/', ':'): str(p.parent)
              for p in sorted((home / 'profiles/money/skills/marketing').glob('*/SKILL.md'))}
    settings = {'schema_version': 1, 'image': image, 'skills': skills,
                'tiktok_shop': 'blocked_by_owner'}
    with tempfile.TemporaryDirectory(prefix='ultron-adoption-stage-') as temp:
        stage = stage_plugin(Path(temp) / 'ultron_adoption')
        changes = {home / 'plugins/ultron_adoption' / p.name: p.read_bytes() for p in stage.iterdir()}
        changes.update({config_path: yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode(),
                        worker_path: changed_worker.encode(),
                        home / 'integrations/adoption/runtime.json': json.dumps(settings, indent=2).encode()})
        originals = {}
        for path in changes:
            if any(p.is_symlink() for p in (path, *path.parents)) or (path.exists() and not path.is_file()):
                raise ValueError('Unexpected deployment destination')
            originals[path] = initial[path] if path in initial else path.read_bytes() if path.exists() else None
        backup.mkdir(mode=0o700, parents=True)
        backup.chmod(0o700)
        for path, content in originals.items():
            if content is not None:
                atomic_write(backup / path.relative_to(home), content)
        applied = []
        try:
            for path, content in changes.items():
                if (path.read_bytes() if path.exists() else None) != originals[path]:
                    raise RuntimeError('Deployment destination changed; aborting')
                applied.append(path)
                atomic_write(path, content)
            manifest = {str(p.relative_to(home)): hashlib.sha256(v).hexdigest() for p, v in changes.items()}
            atomic_write(backup / 'installed-hashes.json', json.dumps(manifest, indent=2).encode())
        except BaseException:
            for path in reversed(applied):
                if originals[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, originals[path])
            raise
    return {'installed': list(manifest), 'catalog_count': len(skills), 'backup': str(backup)}


def require_stopped(runner=subprocess.run):
    state = runner(['systemctl', 'show', 'hermes-gateway.service', '--property=ActiveState', '--value'],
                   capture_output=True, text=True, timeout=15)
    if state.returncode != 0 or state.stdout.strip() not in ('inactive', 'failed'):
        raise RuntimeError('Gateway must be confirmed stopped at idle before installation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path('/root/.hermes'))
    parser.add_argument('--image', required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Back up at idle, stop the gateway, then pass --apply')
    if args.home != Path('/root/.hermes'):
        parser.error('This migration targets the audited local /root/.hermes installation only')
    require_stopped()
    print(json.dumps(install(args.home, args.image, args.backup)))


if __name__ == '__main__':
    main()
