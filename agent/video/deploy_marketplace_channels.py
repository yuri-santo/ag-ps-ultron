"""Apply reviewed channel separation to the local installation after backup."""
import ast
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
from marketplace_channels import annotate_pool
from patch_marketplace_channels import transform, transform_guard


def apply():
    root = Path('/root/tools/tiktok')
    source = Path(__file__).resolve().parent
    pool = Path('/root/tools/youtube/affiliate_link_pool.json')
    edits = {}
    for name, fn in [('affiliate_autonomy.py', transform), ('affiliate_guard.py', transform_guard)]:
        edits[name] = fn((root / name).read_text())
    dispatcher = (root / 'affiliate_dispatch.py').read_text()
    anchor = "COMMON+='Leia /root/tools/tiktok/PRODUCT-IDENTITY.md"
    addition = "COMMON+='Leia /root/tools/tiktok/MARKETPLACE-CHANNELS.md; nao misture afiliacao externa e vitrine Shop. '\n"
    if addition not in dispatcher:
        if dispatcher.count(anchor) != 1:
            raise ValueError('Unknown dispatcher version')
        dispatcher = dispatcher.replace(anchor, addition + anchor, 1)
    edits['affiliate_dispatch.py'] = dispatcher
    for content in edits.values():
        ast.parse(content)
    with open(str(pool) + '.lock', 'a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = json.loads(pool.read_text())
        result = annotate_pool(before)
        assert [x['url'] for x in result['links']] == [x['url'] for x in before['links']]
        fd, temporary = tempfile.mkstemp(prefix='.affiliate-pool-', dir=pool.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, pool)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    for name in ['marketplace_channels.py', 'MARKETPLACE-CHANNELS.md']:
        shutil.copy2(source / name, root / name)
    for name, content in edits.items():
        (root / name).write_text(content)
    print(json.dumps({'catalog_entries':len(result['links']), 'original_urls_preserved':True,
                      'shop_items_added':0,'published':False}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    if not parser.parse_args().apply:
        parser.error('Take an encrypted backup, inspect runtime anchors, then use --apply')
    apply()
