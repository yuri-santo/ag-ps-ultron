"""Patch only completion classification, preserving the installed profile roster."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path


ANCHOR = '''        answer = result.get('final_response') or ''
        failed = bool(result.get('failed') or result.get('partial') or not answer)
'''
REPLACEMENT = '''        answer = result.get('final_response') or ''
        completed = result.get('completed') is True
        model_review = result.get('model_review')
        review_pending = model_review is not None and (
            not isinstance(model_review, dict) or model_review.get('completed') is not True)
        failed = bool(result.get('failed') or result.get('partial') or result.get('interrupted')
                      or not completed or review_pending or not answer)
'''


def patch_file(path):
    path = Path(path)
    if path.name != 'worker.py' or path.is_symlink():
        raise ValueError('unexpected_target')
    original = path.read_bytes()
    eol = '\r\n' if b'\r\n' in original else '\n'
    anchor = ANCHOR.replace('\n', eol).encode()
    replacement = REPLACEMENT.replace('\n', eol).encode()
    if original.count(replacement) == 1 and anchor not in original:
        return False
    if original.count(anchor) != 1 or b'review_pending = model_review' in original:
        raise RuntimeError('upstream_worker_changed')
    updated = original.replace(anchor, replacement, 1)
    compile(updated, str(path), 'exec')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = path.with_name(path.name + '.bak-ultron-completion-' + stamp)
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(original)
    if path.read_bytes() != original:
        raise RuntimeError('target_changed_during_patch')
    path.write_bytes(updated)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    print('patched' if patch_file(parser.parse_args().path) else 'already patched')
