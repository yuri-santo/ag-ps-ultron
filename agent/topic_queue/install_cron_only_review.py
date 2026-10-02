"""Restore native conversations; retain the final review of native cron jobs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from install_gateway import atomic
from install_profiles import RUNTIME, PRIOR, HOME, digest


def main():
    if subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'],
                      capture_output=True, text=True).stdout.strip() != 'inactive':
        raise RuntimeError('Stop gateway before installation')
    manifest_path = PRIOR / 'refresh-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    relative = 'agent/ultron_review_gate.py'
    target = RUNTIME / relative
    if digest(target.read_bytes()) != manifest['installed'][relative]:
        raise RuntimeError('Review gate changed since last installation')
    config_path = HOME / 'topic-queue/config.json'
    config = json.loads(config_path.read_text())
    backup = Path('/root/ultron-local/maintenance') / ('cron-only-review-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    content = (Path(__file__).parent.parent / 'review/ultron_review_gate.py').read_text().encode()
    compile(content, str(target), 'exec')
    atomic(backup / 'review-gate.py', target.read_bytes())
    atomic(backup / 'topic-config.json', config_path.read_bytes())
    atomic(backup / 'refresh-manifest.json', manifest_path.read_bytes())
    config.update(enabled=False, subject_review_v2=True, review_scope='cron_only')
    atomic(target, content)
    manifest['installed'][relative] = digest(content)
    atomic(manifest_path, json.dumps(manifest, indent=2).encode())
    atomic(config_path, json.dumps(config, indent=2).encode())
    print(json.dumps(dict(backup=str(backup), topic_queue=False, review_scope='cron_only')))


if __name__ == '__main__':
    main()
