"""Stage identity evidence enforcement without performing any publication."""
import argparse
import ast
from pathlib import Path

PATCHES = {
    'affiliate_guard.py': [
        ('from affiliate_quality import require_preflight',
         'from affiliate_quality import require_preflight\nfrom product_identity import require_product_identity'),
        ("    asr=json.loads((out/'asr.json').read_text())",
         "    require_product_identity(brief_path,quality,artifact['path'])\n    asr=json.loads((out/'asr.json').read_text())"),
        ('    return brief\n',
         "    identity=require_product_identity(brief_path,quality,video_path)\n    require_review_artifacts(review_info,[a['path'] for a in identity['artifacts']])\n    return brief\n"),
    ],
    'affiliate_autonomy.py': [
        ('    result=model_review.review_output(',
         "    from product_identity import require_product_identity\n    identity=require_product_identity(brief,quality,current['artifact']['path'])\n    evidence += [{'kind':'artifact','ok':True,**a} for a in identity['artifacts']]\n    evidence.append({'kind':'identity_evidence_binding','ok':True,'visual_truth_verified':False,'manifest':identity['manifest']})\n    result=model_review.review_output("),
    ],
    'affiliate_dispatch.py': [
        ("COMMON+='Leia /root/tools/tiktok/VIDEO-QUALITY.md",
         "COMMON+='Leia /root/tools/tiktok/PRODUCT-IDENTITY.md; registre referencias oficiais e inspecao visual real de cada cena antes de publicar. '\nCOMMON+='Leia /root/tools/tiktok/VIDEO-QUALITY.md"),
    ],
}


def transform(name, source):
    for old, new in PATCHES[name]:
        if new in source:
            continue
        if source.count(old) != 1:
            raise ValueError('Unknown or ambiguous anchor: ' + name)
        source = source.replace(old, new, 1)
    ast.parse(source)
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('staging')
    args = parser.parse_args()
    src, dst = Path(args.source).resolve(), Path(args.staging).resolve()
    if dst == src or dst.is_relative_to(src):
        raise ValueError('Use independent staging directory')
    outputs = {name: transform(name, (src / name).read_text()) for name in PATCHES}
    if any((dst / name).exists() for name in outputs):
        raise ValueError('Staging files already exist')
    dst.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        (dst / name).write_text(text)


if __name__ == '__main__':
    main()
