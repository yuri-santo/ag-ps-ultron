import ast
import asyncio
import argparse
import builtins
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE = Path(__file__).with_name('patch_publication.py')


class PublicationPatchTests(unittest.TestCase):
    def migration(self):
        self.assertTrue(MODULE.exists(), 'publication migration is not implemented')
        spec = importlib.util.spec_from_file_location('migration_under_test', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_unknown_source_versions_are_rejected(self):
        migration = self.migration()
        for name in migration.PATCHES:
            with self.assertRaisesRegex(ValueError, 'version'):
                migration.transform(name, 'print("upstream changed")\n')

    def test_all_transformations_are_scoped_and_idempotent(self):
        migration = self.migration()
        for name, pairs in migration.PATCHES.items():
            source = '\n'.join(old for old, new in pairs)
            with self.subTest(name=name), patch.dict(migration.SOURCE_SHA256,
                    {name: hashlib.sha256(source.encode()).hexdigest()}), patch.object(migration.ast, 'parse'):
                output = migration.transform(name, source)
                self.assertEqual(migration.transform(name, output), output)
                for old, new in pairs:
                    self.assertIn(new, output)
                with self.assertRaisesRegex(ValueError, 'version'):
                    migration.transform(name, output + '\n# unrelated change\n')

    def test_legacy_publish_is_rejected_before_any_file_or_browser_access(self):
        migration = self.migration()
        source = ('import json\nimport asyncio\nimport os\n'
                  'async def upload_tiktok():\n    reached_browser.append(True)\n')
        name = 'tiktok/tiktok_uploader.py'
        with patch.dict(migration.SOURCE_SHA256, {name: hashlib.sha256(source.encode()).hexdigest()}):
            output = migration.transform(name, source)
        scope = {'PUBLISH': True, 'reached_browser': []}
        with patch.dict(os.environ, {'TIKTOK_PUBLISH': '0'}):
            exec(output, scope)
        with self.assertRaisesRegex(ValueError, 'affiliate_autonomy'):
            asyncio.run(scope['upload_tiktok']())
        self.assertEqual(scope['reached_browser'], [])

    def test_staging_refuses_source_overlap(self):
        migration = self.migration()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            with self.assertRaisesRegex(ValueError, 'independent'):
                migration.stage(source, source / 'staged')

    def test_staging_refuses_existing_targets_without_writing(self):
        migration = self.migration()
        name = 'tiktok/tiktok_uploader.py'
        source = 'import json\nimport asyncio\nimport os\nasync def upload_tiktok():\n    pass\n'
        with tempfile.TemporaryDirectory() as directory:
            source_root, output_root = Path(directory) / 'source', Path(directory) / 'output'
            source_path, output_path = source_root / name, output_root / name
            source_path.parent.mkdir(parents=True)
            output_path.parent.mkdir(parents=True)
            source_path.write_text(source)
            output_path.write_text('existing target')
            with patch.dict(migration.PATCHES, {name: migration.PATCHES[name]}, clear=True), \
                    patch.dict(migration.SOURCE_SHA256, {name: hashlib.sha256(source.encode()).hexdigest()}):
                with self.assertRaisesRegex(ValueError, 'already exist'):
                    migration.stage(source_root, output_root)
            self.assertEqual(output_path.read_text(), 'existing target')
            self.assertEqual(source_path.read_text(), source)
            self.assertFalse((output_root / 'tiktok/publication_policy.py').exists())
            self.assertFalse((output_root / 'youtube').exists())


@unittest.skipUnless(os.environ.get('ULTRON_NATIVE_PUBLICATION_TEST') == '1',
                     'Requires local private source; publisher dependencies and side effects stay isolated')
class NativePublicationTests(unittest.TestCase):
    def native_source(self, name):
        source = (Path('/root/tools') / name).read_text()
        migration = PublicationPatchTests().migration()
        return migration.transform(name, source)

    def test_legacy_entrypoint_rejects_before_dependency_imports_or_receipt_writes(self):
        source = self.native_source('tiktok/tiktok_uploader.py')
        real_import = builtins.__import__

        def safe_import(name, *args, **kwargs):
            if name == 'product_radar' or name.startswith('playwright'):
                self.fail('Legacy entrypoint reached publisher dependency before rejection: ' + name)
            return real_import(name, *args, **kwargs)

        with patch.dict(os.environ, {'TIKTOK_PUBLISH': '1'}, clear=True), \
                patch('builtins.__import__', side_effect=safe_import), \
                patch('builtins.open', side_effect=AssertionError('Unexpected file access')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('Unexpected directory mutation')), \
                patch.object(Path, 'write_text', side_effect=AssertionError('Unexpected receipt write')):
            with self.assertRaisesRegex(ValueError, 'affiliate_autonomy'):
                exec(compile(source, '<isolated legacy entrypoint>', 'exec'), {'__name__': '__main__'})

    def test_official_main_exempts_only_historical_readback_and_keeps_structure(self):
        source = self.native_source('tiktok/affiliate_autonomy.py')
        tree = ast.parse(source)
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        contract = {}
        exec(self.native_source('tiktok/affiliate_contract.py'), contract)
        cases = [
            ('comment', 'reconcile', 'comment_pending', True),
            ('comment', 'publish', 'commenting', True),
            ('comment', 'prepare', 'commenting', True),
            ('comment', 'publish', 'complete', True),
            ('publish', 'reconcile', 'publishing', True),
            ('comment', 'publish', 'comment_pending', False),
            ('comment', 'prepare', 'comment_pending', False),
            ('publish', 'publish', 'generated', False),
            ('publish', 'prepare', 'generated', False),
            ('reserve', 'reconcile', 'reserved', False),
            ('review', 'reconcile', 'generated', False),
        ]
        for action, mode, stage, historical in cases:
            for valid_structure in (True, False):
                with self.subTest(action=action, mode=mode, stage=stage, valid_structure=valid_structure):
                    brief = {'campaign_id': 'historical-campaign',
                             'locale': 'pt-BR' if valid_structure else 'en-US',
                             'voice': 'pt-BR-AntonioNeural', 'on_screen_text': 'subtitles_only',
                             'voice_mode': 'offscreen_narration',
                             'caption': 'Publicidade. Imagens geradas por IA. \U0001f4aa',
                             'comment_text': 'Link de afiliado: https://meli.la/TestExact',
                             'product': {'affiliate_url': 'https://meli.la/TestExact'},
                             'scenes': [{'narration': 'Confira as condicoes no anuncio.'}] * 4}
                    reached = []
                    registry = SimpleNamespace(get=lambda cid: {'stage': stage})

                    def operation(received, *args):
                        self.assertEqual(received, brief)
                        reached.append(action)
                        return {'status': 'isolated'}

                    scope = {'argparse': argparse, 'json': json,
                             'Path': lambda path: SimpleNamespace(read_text=lambda: json.dumps(brief)),
                             'ProductRegistry': lambda: registry,
                             'validate_brief': contract['validate_brief'],
                             'comment': operation, 'publish': operation,
                             'reserve': operation, 'review': operation}
                    exec(compile(ast.Module(body=[main], type_ignores=[]), '<isolated official main>', 'exec'), scope)
                    with patch.object(sys, 'argv', ['affiliate_autonomy', action, '--brief', 'fixture', '--mode', mode]), \
                            patch('builtins.print'):
                        if historical and valid_structure:
                            scope['main']()
                            self.assertEqual(reached, [action])
                        else:
                            with self.assertRaises(ValueError):
                                scope['main']()
                            self.assertEqual(reached, [])

    def test_native_migrations_parse_and_legacy_emoji_gap_is_reproduced(self):
        migration = PublicationPatchTests().migration()
        sources = {}
        for name in migration.PATCHES:
            source = (Path('/root/tools') / name).read_text()
            transformed = migration.transform(name, source)
            ast.parse(transformed)
            self.assertEqual(migration.transform(name, transformed), transformed)
            sources[name] = (source, transformed)
        brief = {'locale': 'pt-BR', 'voice': 'pt-BR-AntonioNeural',
                 'on_screen_text': 'subtitles_only', 'voice_mode': 'offscreen_narration',
                 'caption': 'Publicidade. Imagens geradas por IA. \U0001f4aa',
                 'comment_text': 'Link de afiliado: https://meli.la/TestExact',
                 'product': {'affiliate_url': 'https://meli.la/TestExact'},
                 'scenes': [{'narration': 'Confira as condi\u00e7\u00f5es no an\u00fancio.'}] * 4}
        name = 'tiktok/affiliate_contract.py'
        before, after = sources[name]
        # The migration already proved either the original hash or its exact installed form.
        for source in dict.fromkeys((before, after)):
            scope = {}
            exec(source, scope)
            if hashlib.sha256(source.encode()).hexdigest() == migration.SOURCE_SHA256[name]:
                self.assertTrue(scope['validate_brief'](brief))
            else:
                with self.assertRaisesRegex(ValueError, 'emoji'):
                    scope['validate_brief'](brief)
        # Extract only the pure text factory, with an injected exact product URL.
        for source in sources['youtube/affiliate_links.py']:
            tree = ast.parse(source)
            factory = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_affiliate_text')
            scope = {'pick_contextual_product': lambda *a: {'label': 'Produto', 'url': 'https://meli.la/ExactOriginal'},
                     'ML_VITRINE': 'https://store.example/Original'}
            exec(compile(ast.Module(body=[factory], type_ignores=[]), '<factory>', 'exec'), scope)
            result = scope['build_affiliate_text']('Produto')
            self.assertIn('https://meli.la/ExactOriginal', result['comment_text'])
            if source == sources['youtube/affiliate_links.py'][1]:
                self.assertNotIn('\U0001f449', result['comment_text'])
                self.assertNotIn('\U0001f6d2', result['comment_text'])


if __name__ == '__main__':
    unittest.main()
