"""Persist the validated replacement, not a rejected model candidate."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import tempfile


ANCHOR = '''    final_response = reviewed
    # First hook to return a string wins; None/empty leaves the text unchanged.
'''
REPLACEMENT = '''    # Ultron: the durable transcript must match the validated replacement.
    transformed = reviewed != final_response
    final_response = reviewed
    # First hook to return a string wins; None/empty leaves the text unchanged.
'''


def patch_file(path: Path) -> bool:
    path = Path(path)
    if path.name != 'turn_finalizer.py' or path.is_symlink():
        raise ValueError('unexpected_target')
    original = path.read_bytes()
    eol = '\r\n' if b'\r\n' in original else '\n'
    anchor = ANCHOR.replace('\n', eol).encode()
    replacement = REPLACEMENT.replace('\n', eol).encode()
    if original.count(replacement) == 1 and original.count(anchor) == 1:
        return False
    if original.count(anchor) != 1 or b'    transformed = reviewed != final_response' in original:
        raise RuntimeError('upstream_finalizer_changed')
    updated = original.replace(anchor, replacement, 1)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = path.with_name(path.name + '.bak-ultron-transform-' + stamp)
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
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
