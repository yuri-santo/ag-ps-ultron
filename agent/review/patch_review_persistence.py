"""Keep Ultron review candidates and nudges out of Hermes' durable transcript."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import tempfile
import time


MARKER = b'_review_stop_synthetic'
ANCHOR = b'''_EPHEMERAL_SCAFFOLDING_FLAGS = (
    "_empty_recovery_synthetic",
    "_empty_terminal_sentinel",
    "_thinking_prefill",
    "_verification_stop_synthetic",  # verify-on-stop nudge; the assistant candidate itself is NOT synthetic
    "_pre_verify_synthetic",
    "_kanban_stop_synthetic",  # kanban worker stop-guard
    "_dropped_toolcall_nudge",  # internal retry instruction; must not replay as user context
)
'''
ADDITION = b'    "_review_stop_synthetic",  # Ultron: rejected candidate and internal reviewer nudge\n'
GUARD = b'''def _is_ephemeral_scaffolding(msg: Any) -> bool:
    """True when ``msg`` is internal recovery scaffolding that must never reach the durable transcript."""
    return isinstance(msg, dict) and any(msg.get(flag) for flag in _EPHEMERAL_SCAFFOLDING_FLAGS)
'''
COLLECT_GUARD = b'        if not isinstance(msg, dict) or _is_ephemeral_scaffolding(msg) or msg.get(_DB_PERSISTED_MARKER):\n'


def patch_file(path: Path) -> bool:
    path = Path(path)
    if path.name != 'session_persistence.py' or path.is_symlink():
        raise ValueError('unexpected_target')
    original = path.read_bytes()
    eol = b'\r\n' if b'\r\n' in original else b'\n'
    anchor = ANCHOR.replace(b'\n', eol)
    replacement = (ANCHOR[:-2] + ADDITION + b')\n').replace(b'\n', eol)
    guards = (GUARD.replace(b'\n', eol), COLLECT_GUARD.replace(b'\n', eol))
    if any(original.count(guard) != 1 for guard in guards):
        raise RuntimeError('upstream_persistence_changed')
    if MARKER in original:
        if original.count(MARKER) == 1 and original.count(replacement) == 1:
            return False
        raise RuntimeError('upstream_persistence_changed')
    if original.count(anchor) != 1:
        raise RuntimeError('upstream_persistence_changed')
    updated = original.replace(anchor, replacement, 1)
    compile(updated, str(path), 'exec')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = path.with_name(f'{path.name}.bak-ultron-review-{stamp}-{time.time_ns()}')
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.chmod(backup, 0o600)
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())

    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.ultron-', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.chmod(temporary, mode)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or path.read_bytes() != original:
            raise RuntimeError('target_changed_during_patch')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    print('patched' if patch_file(args.path) else 'already patched')
