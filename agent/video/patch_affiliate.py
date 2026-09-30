"""Stage narrowly anchored changes; never installs or invokes a publisher."""
import argparse
import ast
from pathlib import Path


PATCHES = {
    'affiliate_render.py': [
        ('from affiliate_contract import validate_brief, validate_subtitles',
         'from affiliate_contract import validate_brief, validate_subtitles\nfrom affiliate_quality import check_render, voice_filter, require_preflight'),
        ("            print(json.dumps({'status':'existing_render'",
         "            require_preflight(out/'video.mp4', existing)\n            print(json.dumps({'status':'existing_render'"),
        ('aresample=48000,adelay={round(s["voice_start"]*1000)}',
         '{voice_filter(voices[i]["duration"])},adelay={round(s["voice_start"]*1000)}'),
        ("    receipt={'version':2,", "    preflight=check_render(out/'video.mp4',total)\n    receipt={'preflight':preflight,'version':2,"),
    ],
    'affiliate_guard.py': [
        ('from affiliate_registry import ProductRegistry,identity_aliases',
         'from affiliate_registry import ProductRegistry,identity_aliases\nfrom affiliate_quality import require_preflight'),
        ("    render=json.loads((out/'render-receipt.json').read_text())",
         "    render=json.loads((out/'render-receipt.json').read_text())\n    require_preflight(artifact['path'],render)"),
        ("out/'quality.json',out/'asr.json',video_path])",
         "out/'quality.json',out/'asr.json',out/'media-preflight.json',video_path])"),
    ],
    'affiliate_autonomy.py': [
        ("out/'quality.json',out/'asr.json']]",
         "out/'quality.json',out/'asr.json',out/'media-preflight.json']]"),
    ],
    'affiliate_dispatch.py': [
        ("COMMON+='Antes de cada envio", "COMMON+='Leia /root/tools/tiktok/VIDEO-QUALITY.md antes de roteiro, montagem e revisao. '\nCOMMON+='Antes de cada envio"),
    ],
}


def transform(name, source):
    for old, new in PATCHES[name]:
        if source.count(new) == 1 and source.count(old) <= 1:
            continue
        if source.count(old) != 1 or new in source:
            raise ValueError('Unknown or ambiguous anchor in ' + name)
        source = source.replace(old, new, 1)
    return source


def stage(source_root, output_root):
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    if output_root == source_root or output_root.is_relative_to(source_root):
        raise ValueError('Use an independent staging directory')
    transformed = {}
    for name in PATCHES:
        path = source_root / name
        if path.is_symlink():
            raise ValueError('Refusing symlink source')
        transformed[name] = transform(name, path.read_text())
        ast.parse(transformed[name])
    output_root.mkdir(parents=True, exist_ok=True)
    for name, content in transformed.items():
        target = output_root / name
        if target.exists():
            raise ValueError('Staging target already exists: ' + name)
        target.write_text(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root')
    parser.add_argument('output_root')
    args = parser.parse_args()
    stage(args.source_root, args.output_root)
