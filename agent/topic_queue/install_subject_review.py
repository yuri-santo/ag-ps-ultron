"""Install subject review only while the local gateway is stopped."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from install_gateway import atomic
from install_profiles import RUNTIME, PRIOR, HOME, digest
from patch_worker_proof import HELPERS


def main():
    state = subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'],
                           capture_output=True, text=True).stdout.strip()
    if state != 'inactive':
        raise RuntimeError('Gateway must be stopped before installation')
    manifest_path = PRIOR / 'refresh-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest['installed'].items():
        if digest((RUNTIME / name).read_bytes()) != expected:
            raise RuntimeError('Concurrent runtime change: ' + name)
    source = Path(__file__).parent
    updates = {RUNTIME / 'ultron_topic_queue' / name: (source / name).read_text().encode()
               for name in ('delivery.py', 'runtime.py', 'reviewer.py', 'review_policy.py',
                            'subject_review.py', 'specialist.py', 'native_delivery.py')}
    updates[RUNTIME / 'agent/ultron_review_gate.py'] = (source.parent / 'review/ultron_review_gate.py').read_text().encode()
    worker_path = HOME / 'plugins/ultron_team/worker.py'
    original_worker = worker_path.read_bytes()
    if digest(original_worker) != 'c3ff263a51cf18728fa5185b768ca1e4b2483c39ea50d2761e39967584f0a49f':
        raise RuntimeError('Concurrent specialist worker change')
    worker = original_worker.decode()
    start, end = worker.index('\n\ndef _worker_proof('), worker.index('\n\ndef execute(request):')
    worker_update = (worker[:start] + HELPERS + worker[end:]).encode()
    compile(worker_update, str(worker_path), 'exec')
    for path, content in updates.items():
        compile(content, str(path), 'exec')
    config_path = HOME / 'topic-queue/config.json'
    config = json.loads(config_path.read_text())
    config['subject_review_v2'] = True
    backup = Path('/root/ultron-local/maintenance') / ('subject-review-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    atomic(backup / 'refresh-manifest.json', manifest_path.read_bytes())
    atomic(backup / 'topic-config.json', config_path.read_bytes())
    atomic(backup / 'specialist-worker.py', original_worker)
    for path, content in updates.items():
        name = str(path.relative_to(RUNTIME))
        if path.exists():
            atomic(backup / name, path.read_bytes())
        atomic(path, content)
        manifest['installed'][name] = digest(content)
    atomic(manifest_path, json.dumps(manifest, indent=2).encode())
    atomic(worker_path, worker_update)
    atomic(config_path, json.dumps(config, indent=2).encode())
    print(json.dumps({'backup': str(backup), 'files': len(updates), 'subject_review_v2': True}))


if __name__ == '__main__':
    main()
