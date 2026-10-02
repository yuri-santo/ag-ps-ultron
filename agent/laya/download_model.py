"""Download public ONNX data only, pinned and verified; never executes model code."""
import hashlib
import json
from pathlib import Path
import urllib.request

REVISION = '68f27dfe5a27a54fb2b1fefc432f43f972e90868'
ROOT = Path('/root/ultron-local/integrations/laya-eval/model')
FILES = ('laya.onnx', 'laya.onnx.data', 'laya_config.json',
         'tokenizer/tokenizer.json', 'tokenizer/tokenizer_config.json')


def main():
    with urllib.request.urlopen('https://huggingface.co/api/models/receptron/laya-onnx/revision/' + REVISION + '?blobs=true', timeout=30) as response:
        metadata = json.load(response)
    assert metadata['sha'] == REVISION
    siblings = {item['rfilename']: item for item in metadata['siblings']}
    manifest = {'revision': REVISION, 'files': {}}
    for name in FILES:
        target = ROOT/name
        target.parent.mkdir(parents=True, exist_ok=True)
        entry = siblings[name]
        expected = (entry.get('lfs') or {}).get('sha256')
        if not target.exists():
            url = 'https://huggingface.co/receptron/laya-onnx/resolve/' + REVISION + '/' + name
            temporary = target.with_suffix(target.suffix + '.part')
            with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as stream:
                while chunk := response.read(1024*1024):
                    stream.write(chunk)
            temporary.replace(target)
        digest = hashlib.sha256()
        with target.open('rb') as stream:
            while chunk := stream.read(1024*1024):
                digest.update(chunk)
        actual = digest.hexdigest()
        if target.stat().st_size != entry['size'] or expected and actual != expected:
            raise ValueError('Model integrity mismatch: ' + name)
        if not expected:
            raw = target.read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if blob != entry['blobId']:
                raise ValueError('Git blob mismatch: ' + name)
        manifest['files'][name] = {'bytes': target.stat().st_size, 'sha256': actual}
        print(json.dumps({'verified': name, 'bytes': target.stat().st_size}), flush=True)
    (ROOT/'verified-manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
