"""Install native-delivery recovery with exact source checks and private backups."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from install_gateway import atomic
from install_profiles import RUNTIME, PRIOR, digest
from native_patch import SOURCE_SHA256, patch_sources

OLD_PRODUCER = "    return {'provider':str(getattr(agent,'provider','')),'model':str(getattr(agent,'model','')),'served_model':getattr(agent,'last_served_model',None)}"
NEW_PRODUCER = """    requested = str(getattr(agent, 'model', ''))
    served = getattr(agent, 'last_served_model', None)
    return {'provider': str(getattr(agent, 'provider', '')), 'model': served or requested,
            'requested_model': requested, 'served_model': served}"""


def main():
    if subprocess.run(['systemctl', 'is-active', 'hermes-gateway.service'],
                      capture_output=True, text=True).stdout.strip() != 'inactive':
        raise RuntimeError('Gateway must be stopped')
    manifest_path = PRIOR / 'refresh-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest['installed'].items():
        if digest((RUNTIME/name).read_bytes()) != expected:
            raise RuntimeError('Concurrent change: ' + name)
    originals = {}
    for name, expected in SOURCE_SHA256.items():
        old = PRIOR / 'backup/native' / name
        raw = old.read_bytes() if old.exists() else (RUNTIME/name).read_bytes()
        if digest(raw) != expected:
            raise RuntimeError('Unrecognized upstream: ' + name)
        originals[name] = raw.decode()
    updates = {RUNTIME/name: text.encode() for name, text in patch_sources(originals).items()}
    for name in ('runtime.py', 'gateway_adapter.py', 'native_delivery.py', 'model_identity.py'):
        updates[RUNTIME/'ultron_topic_queue'/name] = Path(__file__).with_name(name).read_bytes()
    gate = RUNTIME/'agent/ultron_review_gate.py'
    text = gate.read_text()
    if text.count(OLD_PRODUCER) != 1 and text.count(NEW_PRODUCER) != 1:
        raise RuntimeError('Review gate changed')
    updates[gate] = text.replace(OLD_PRODUCER, NEW_PRODUCER).encode()
    for target, content in updates.items():
        compile(content, str(target), 'exec')
    backup = Path('/root/ultron-local/maintenance') / ('native-delivery-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    atomic(backup/'refresh-manifest.json', manifest_path.read_bytes())
    for name in SOURCE_SHA256:
        old = PRIOR/'backup/native'/name
        if not old.exists():
            atomic(old, originals[name].encode())
    for target, content in updates.items():
        name = str(target.relative_to(RUNTIME))
        if target.exists():
            atomic(backup/name, target.read_bytes())
        atomic(target, content)
        manifest['installed'][name] = digest(content)
    atomic(manifest_path, json.dumps(manifest, indent=2).encode())
    print(json.dumps({'backup': str(backup), 'files': len(updates)}))


if __name__ == '__main__':
    main()
