"""Audited local refresh, admission switch and checksum-guarded native rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from install_gateway import atomic, expose_package
from native_patch import patch_sources, SOURCE_SHA256

RUNTIME = Path('/opt/hermes-agent-20260924')
HOME = Path('/root/.hermes')
BACKUP = Path('/root/ultron-local/maintenance/topic-gateway-20261001')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def service():
    return subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'],
                          capture_output=True, text=True, check=False).stdout.strip()


def switch(enabled):
    path = HOME / 'topic-queue/config.json'
    config = json.loads(path.read_text())
    if enabled:
        assert service() == 'active', 'Start the gateway before admitting messages'
        installed = json.loads((BACKUP / 'refresh-manifest.json').read_text())
        assert all(sha((RUNTIME / name).read_bytes()) == value
                   for name, value in installed['installed'].items()), 'Installed code changed'
    config['enabled'] = enabled
    atomic(path, json.dumps(config, ensure_ascii=False, indent=2).encode())
    return {'admission_enabled': enabled, 'service': service()}


def refresh():
    assert service() == 'inactive', 'Stop the gateway before refresh'
    assert not json.loads((HOME / 'topic-queue/config.json').read_text())['enabled']
    originals = {name: (BACKUP / 'backup/native' / name).read_text() for name in SOURCE_SHA256}
    assert all(sha(text.encode()) == SOURCE_SHA256[name] for name, text in originals.items())
    patched = patch_sources(originals)
    for name, content in patched.items():
        assert (RUNTIME / name).read_text() in (originals[name], content), 'Concurrent native edit: ' + name
    updates = {name: content.encode() for name, content in patched.items()}
    for source in Path(__file__).parent.glob('*.py'):
        if not source.name.startswith(('test_', 'install_', 'manage_', 'probe_')):
            content = source.read_bytes()
            compile(content, source.name, 'exec')
            updates['ultron_topic_queue/' + source.name] = content
    previous = {name: (RUNTIME / name).read_bytes() if (RUNTIME / name).exists() else None for name in updates}
    for name, content in previous.items():
        if content is not None:
            atomic(BACKUP / 'before-refresh' / name, content)
    try:
        for name, content in updates.items():
            atomic(RUNTIME / name, content)
        expose_package(RUNTIME)
        atomic(BACKUP / 'refresh-manifest.json', json.dumps({
            'installed': {name: sha(content) for name, content in updates.items()},
            'original_native': SOURCE_SHA256,
        }, indent=2).encode())
    except Exception:
        for name, content in previous.items():
            if content is not None:
                atomic(RUNTIME / name, content)
        raise
    return {'refreshed_files': len(updates), 'admission_enabled': False}


def rollback_native():
    assert service() == 'inactive', 'Stop the gateway before rollback'
    switch(False)
    manifest = json.loads((BACKUP / 'refresh-manifest.json').read_text())
    for name in SOURCE_SHA256:
        assert sha((RUNTIME / name).read_bytes()) == manifest['installed'][name], 'Concurrent edit: ' + name
        assert sha((BACKUP / 'backup/native' / name).read_bytes()) == SOURCE_SHA256[name]
    for name in SOURCE_SHA256:
        atomic(RUNTIME / name, (BACKUP / 'backup/native' / name).read_bytes())
    return {'native_hooks_restored': len(SOURCE_SHA256), 'admission_enabled': False,
            'private_state_preserved': True, 'config_and_review_policy_preserved': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['refresh', 'enable', 'disable', 'rollback-native', 'status'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'refresh':
        result = refresh()
    elif args.action == 'rollback-native':
        result = rollback_native()
    elif args.action == 'status':
        from ultron_topic_queue.runtime import Runtime
        runtime = Runtime.from_home()
        with runtime.connect() as db:
            counts = dict(db.execute('SELECT status,count(*) FROM tasks GROUP BY status'))
        result = dict(service=service(), admission_enabled=runtime.enabled,
                      scopes=len(runtime.configured_scopes), profiles=len(runtime.roster), cards=counts)
    else:
        result = switch(args.action == 'enable')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
