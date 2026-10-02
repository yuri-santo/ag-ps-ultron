"""Small checksum-guarded upgrade, retaining a private rollback copy."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from install_gateway import atomic
from install_profiles import RUNTIME, PRIOR, digest


def main():
    state = subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'],
                           capture_output=True, text=True).stdout.strip()
    if state != 'inactive':
        raise RuntimeError('Stop gateway before upgrade')
    path = PRIOR / 'refresh-manifest.json'
    manifest = json.loads(path.read_text())
    updates = {}
    for name in ('orchestrator_worker.py', 'specialist.py', 'runtime.py', 'speech.py'):
        relative = 'ultron_topic_queue/' + name
        target = RUNTIME / relative
        expected = manifest['installed'].get(relative)
        if target.exists() and digest(target.read_bytes()) != expected:
            raise RuntimeError('Concurrent change: ' + relative)
        content = Path(__file__).with_name(name).read_bytes()
        compile(content, name, 'exec')
        updates[relative] = content
    backup = Path('/root/ultron-local/maintenance') / ('speech-fix-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    atomic(backup / 'refresh-manifest.json', path.read_bytes())
    for relative, content in updates.items():
        target = RUNTIME / relative
        if target.exists():
            atomic(backup / relative, target.read_bytes())
        atomic(target, content)
        manifest['installed'][relative] = digest(content)
    atomic(path, json.dumps(manifest, indent=2).encode())
    print(json.dumps({'backup': str(backup), 'updated': list(updates)}))


if __name__ == '__main__':
    main()
