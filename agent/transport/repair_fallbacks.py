"""Append explicitly verified local routes, with dry-run and private backups."""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit

from ultron_router_compat import _is_local_router


def _identity(name, base_url):
    endpoint = 'local-9router' if _is_local_router(base_url) else str(base_url or '').rstrip('/')
    return name, endpoint


def repaired_config(config, models, drop_hosts):
    model = config.get('model') or {}
    if not _is_local_router(model.get('base_url')) or not model.get('api_key'):
        raise ValueError('primary_must_use_authenticated_local_router')
    updated = copy.deepcopy(config)
    routes = []
    seen = {_identity(model.get('default'), model['base_url'])}
    for route in updated.get('fallback_providers') or []:
        if urlsplit(str(route.get('base_url') or '')).hostname in drop_hosts:
            continue
        if _is_local_router(route.get('base_url')) and route.get('model') in models:
            continue
        identity = _identity(route.get('model'), route.get('base_url'))
        if identity in seen:
            continue
        seen.add(identity)
        routes.append(route)
    for name in models:
        identity = _identity(name, model['base_url'])
        if identity in seen:
            continue
        seen.add(identity)
        routes.append({'provider': 'custom', 'model': name,
                       'base_url': model['base_url'], 'api_key': model['api_key']})
    updated['fallback_providers'] = routes
    return updated


def update_file(path, models, drop_hosts, *, apply=False):
    import yaml

    path = Path(path)
    original = path.read_bytes()
    config = yaml.safe_load(original) or {}
    updated = repaired_config(config, models, drop_hosts)
    changed = updated != config
    result = {'profile': path.parent.name, 'changed': changed, 'applied': False,
              'fallback_models': [r['model'] for r in updated['fallback_providers']]}
    if not apply or not changed:
        return result
    backup = path.with_name(path.name + '.bak-ultron-fallback-' +
                            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    shutil.copy2(path, backup)
    os.chmod(backup, 0o600)
    rendered = yaml.safe_dump(updated, sort_keys=False, allow_unicode=True).encode('utf-8')
    if yaml.safe_load(rendered) != updated:
        raise RuntimeError('configuration_roundtrip_failed')
    fd, temporary = tempfile.mkstemp(prefix='.fallback-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        if path.read_bytes() != original:
            raise RuntimeError('configuration_changed_concurrently')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return dict(result, applied=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--models', nargs='+', required=True,
                        help='Routes verified by live tests; this script does not assert availability.')
    parser.add_argument('--drop-host', action='append', default=[])
    parser.add_argument('--profiles', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    paths = [args.root / 'config.yaml']
    if args.profiles:
        paths += sorted((args.root / 'profiles').glob('*/config.yaml'))
    for path in paths:
        import yaml
        config = yaml.safe_load(path.read_bytes()) or {}
        # Domains without a private route/key inherit their original configuration.
        if path != paths[0] and not _is_local_router((config.get('model') or {}).get('base_url')):
            continue
        print(json.dumps(update_file(path, args.models, args.drop_host, apply=args.apply)), flush=True)
