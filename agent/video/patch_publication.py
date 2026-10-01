"""Stage version-pinned publication fixes; never install, authenticate or publish."""
import argparse
import ast
import hashlib
from pathlib import Path


SOURCE_SHA256 = {
    'tiktok/affiliate_contract.py': 'ba9d2348793f3f421443cc6be607da56545186a24e977ea9b321cfae9e6c9cd6',
    'tiktok/tiktok_uploader.py': '70fe6503221f5464cd81097a1a8bf27900041364587a1588fef6a16c97462f15',
    'tiktok/affiliate_dispatch.py': 'ba73242818e24641e026b2ee585aeeb87cb30c48eacde56e83653c6628809ba7',
    'tiktok/affiliate_comment.py': '8a2f22af62359159f62c7ce709d0bbf39233c334141a540c9879906c93092b39',
    'tiktok/affiliate_autonomy.py': '786ac1d805045a712469e79447eb79b4c30ebd75f514ff39675468c6d071c124',
    'youtube/affiliate_links.py': 'af334f6f692b43f411f6533399f9e3d68541a44a21b8f98d50cad37e860b9aeb',
    'youtube/official_api_uploader.py': 'b19999d3a9c7a49f3ccdb768ede4cc4505a665dd5be25e67460c21619145c65e',
}

PATCHES = {
    'tiktok/affiliate_contract.py': [
        ('from pathlib import Path',
         'from pathlib import Path\nfrom publication_policy import require_brief_text, require_plain_text'),
        ('def validate_brief(brief):',
         'def validate_brief(brief, *, enforce_publication_text=True):\n'
         '    if enforce_publication_text:require_brief_text(brief)'),
        ('def validate_subtitles(ass,script):',
         "def validate_subtitles(ass,script):\n    require_plain_text(ass, 'subtitles')"),
    ],
    'tiktok/tiktok_uploader.py': [
        ('import json\nimport asyncio\nimport os\n',
         'import os\nif os.environ.get("TIKTOK_PUBLISH") == "1":\n'
         "    raise ValueError('Legacy publication disabled; use affiliate_autonomy.py with campaign and review receipts')\n\n"
         'import json\nimport asyncio\n'),
        ('async def upload_tiktok():',
         "async def upload_tiktok():\n    if PUBLISH:\n"
         "        raise ValueError('Legacy publication disabled; use affiliate_autonomy.py with campaign and review receipts')"),
    ],
    'tiktok/affiliate_dispatch.py': [
        ("COMMON+='Leia /root/tools/tiktok/VIDEO-QUALITY.md antes de roteiro, montagem e revisao. '",
         "COMMON+='Leia /root/tools/tiktok/VIDEO-QUALITY.md antes de roteiro, montagem e revisao. '\n"
         "COMMON+='Toda nova entrega, roteiro, legenda e comentario deve ser sem emojis. Promessas de frete gratis, laudo aprovado, desconto exclusivo, rendimento em doses, resultado garantido ou comentario fixado exigem validacao especifica de evidencia ainda indisponivel; reformular e revisar antes de enviar. Nunca usar tiktok_uploader.py para publicar. '"),
    ],
    'tiktok/affiliate_comment.py': [
        ('    validate_brief(brief)',
         "    validate_brief(brief,enforce_publication_text=mode!='reconcile' and campaign['stage']!='commenting')"),
    ],
    'tiktok/affiliate_autonomy.py': [
        ('        brief=json.loads(Path(args.brief).read_text());validate_brief(brief)',
         '        brief=json.loads(Path(args.brief).read_text())\n'
         "        read_only = (args.action in ('comment', 'publish') and args.mode == 'reconcile')\n"
         "        if args.action == 'comment' and not read_only:\n"
         "            read_only = reg.get(brief['campaign_id'])['stage'] in ('commenting', 'complete')\n"
         '        validate_brief(brief, enforce_publication_text=not read_only)'),
    ],
    'youtube/affiliate_links.py': [
        ('f"\U0001f449 {product[\'label\']}: {product[\'url\']}\\n\\n"',
         'f"{product[\'label\']}: {product[\'url\']}\\n\\n"'),
        ('f"\U0001f6d2 Vitrine com todos os achadinhos recomendados: {ML_VITRINE}"',
         'f"Vitrine com todos os achadinhos recomendados: {ML_VITRINE}"'),
        ('f"\U0001f449 {product[\'url\']}"', 'f"{product[\'url\']}"'),
    ],
    'youtube/official_api_uploader.py': [
        ('from affiliate_links import build_affiliate_text',
         'from affiliate_links import build_affiliate_text\nfrom publication_policy import require_publication_text'),
        ('    youtube = get_authenticated_service()',
         '    # Authenticate only after publication text passes validation.'),
        ("    comment_text = affiliate['comment_text']",
         "    comment_text = affiliate['comment_text']\n"
         "    try:\n"
         "        for label, text in [('title', title_text), ('description', desc_text), ('comment', comment_text)]:\n"
         "            require_publication_text(text, label)\n"
         "    except ValueError:\n"
         "        conn.close()\n"
         "        raise\n"
         "    youtube = get_authenticated_service()"),
    ],
}


def _digest(source):
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def transform(name, source):
    if name not in PATCHES:
        raise ValueError('Unknown publication source: ' + name)
    expected = SOURCE_SHA256[name]
    if _digest(source) != expected:
        original = source
        # Reverse the full known patch to recognize only its exact installed form.
        for old, new in reversed(PATCHES[name]):
            if not new or original.count(new) != 1:
                break
            original = original.replace(new, old, 1)
        else:
            if _digest(original) == expected:
                ast.parse(source)
                return source
        raise ValueError('Unknown source version; inspect before migrating: ' + name)
    for old, new in PATCHES[name]:
        if source.count(old) != 1:
            raise ValueError('Unknown or ambiguous publication anchor: ' + name)
        source = source.replace(old, new, 1)
    ast.parse(source)
    return source


def stage(source_root, output_root):
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    if (output_root == source_root or output_root.is_relative_to(source_root)
            or source_root.is_relative_to(output_root)):
        raise ValueError('Use an independent staging directory')
    outputs = {}
    for name in PATCHES:
        path = source_root / name
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Refusing symlink source')
        outputs[name] = transform(name, path.read_bytes().decode('utf-8'))
    policy = Path(__file__).with_name('publication_policy.py').read_text(encoding='utf-8')
    for root in ('tiktok', 'youtube'):
        outputs[root + '/publication_policy.py'] = policy
    if any((output_root / name).exists() or (output_root / name).is_symlink() for name in outputs):
        raise ValueError('Staging files already exist')
    for name in outputs:
        if (output_root / name).parent.is_symlink():
            raise ValueError('Refusing symlink staging directory')
    for name, source in outputs.items():
        target = output_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', help='Existing /root/tools tree')
    parser.add_argument('output_root', help='Independent private staging directory')
    arguments = parser.parse_args()
    stage(arguments.source_root, arguments.output_root)
