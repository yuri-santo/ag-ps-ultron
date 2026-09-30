import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).with_name('product_identity.py')
NOW = dt.datetime(2026, 9, 30, 12, tzinfo=dt.timezone.utc)
CHECKS = ('item', 'packaging', 'labels', 'colors', 'shape', 'accessories', 'scale')


class ProductIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def fixture(self):
        reference = self.write('reference.png', b'official image bytes')
        source = self.write('reference-source.json', {
            'canonical_product_id': 'catalog:123', 'variant': 'black-500ml',
            'source_url': 'https://manufacturer.example/products/123',
            'image_sha256': reference['sha256'], 'authority': 'manufacturer',
            'checked_at': NOW.isoformat(),
            'observation': 'Official model 123, black body, 500 ml, red lid and printed box.'})
        reference.update(source_url='https://manufacturer.example/products/123', source_receipt=source)
        scene = self.write('scene.mp4', b'generated scene bytes')
        receipt = self.write('scene-receipt.json', {
            **scene, 'project_url': 'https://labs.google/fx/project/123', 'job_id': 'job123',
            'reference_attached': True, 'visual_identity_checked': True})
        self.brief = {
            'campaign_id': 'campaign-123',
            'product': {'canonical_product_id': 'catalog:123', 'variant': 'black-500ml',
                        'packaging_required': True},
            'facts': {'identity_references': [reference]},
            'scenes': [{**scene, 'start': 0, 'end': 4, 'narration': 'Produto preto.',
                        'generation_receipt': receipt['path']}],
        }
        self.brief_binding = self.write('brief.json', self.brief)
        self.video = self.write('video.mp4', b'final mp4 bytes')
        self.render = {
            'brief_sha256': self.brief_binding['sha256'], 'video_sha256': self.video['sha256'],
            'path': self.video['path'], 'duration': 4,
            'segments': [{'start': 0, 'duration': 4, 'scene': self.brief['scenes'][0]}],
        }
        self.render_binding = self.write('render-receipt.json', self.render)
        self.manifest = {
            'version': 1, 'campaign_id': 'campaign-123',
            'canonical_product_id': 'catalog:123', 'variant': 'black-500ml',
            'checked_at': NOW.isoformat(), 'reviewer': 'visual-reviewer-1',
            'method': 'visual_comparison', 'brief': self.brief_binding, 'video': self.video,
            'render_receipt': self.render_binding, 'references': [reference],
            'scenes': [{
                'scene_id': 1, 'source': scene, 'generation_receipt': receipt,
                'frames': [{'timestamp': t, **self.write(f'frame-{i}.png', f'frame {i}'.encode())}
                           for i, t in enumerate([0.1, 2, 3.9])],
                'checks': {key: {'status': 'match',
                                'notes': f'Compared {key} with model 123 reference: black body and red lid.'}
                           for key in CHECKS},
            }],
        }
        self.quality = {'video_sha256': self.video['sha256']}
        self.sync()

    def sync(self):
        self.quality['product_identity'] = self.write('product-identity.json', self.manifest)

    def check(self, brief=None):
        self.assertTrue(MODULE.exists(), 'product_identity validator has not been implemented')
        spec = importlib.util.spec_from_file_location('product_identity_under_test', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.require_product_identity(
            brief or self.brief_binding['path'], self.quality, self.video['path'], now=NOW)

    def test_evidence_validates_without_claiming_visual_truth(self):
        self.fixture()
        result = self.check()
        self.assertEqual(result['status'], 'evidence_validated')
        self.assertIs(result['visual_truth_verified'], False)
        self.assertEqual(result['manifest'], self.manifest)
        paths = {a['path'] for a in result['artifacts']}
        self.assertIn(str(self.root / 'reference-source.json'), paths)
        self.assertIn(str(self.root / 'scene-receipt.json'), paths)
        self.assertIn(str(self.root / 'frame-2.png'), paths)
        self.assertIn(str(self.root / 'product-identity.json'), paths)

    def test_boolean_fidelity_does_not_satisfy_contract(self):
        self.fixture()
        self.quality = {'visual_review': {'product_fidelity': True}}
        with self.assertRaises(ValueError):
            self.check()

    def test_mutation_of_every_bound_file_is_refused(self):
        for filename in ('brief.json', 'video.mp4', 'scene.mp4', 'scene-receipt.json',
                         'reference.png', 'reference-source.json', 'frame-1.png',
                         'render-receipt.json', 'product-identity.json'):
            with self.subTest(filename=filename):
                self.fixture()
                (self.root / filename).write_bytes(b'mutated')
                with self.assertRaises(ValueError):
                    self.check()

    def test_missing_file_is_refused(self):
        self.fixture()
        (self.root / 'reference-source.json').unlink()
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_unknown_or_mismatch_checks_are_refused(self):
        for key in CHECKS:
            for status in (None, 'unknown', 'mismatch', True, 'not_visible'):
                with self.subTest(key=key, status=status):
                    self.fixture()
                    if status is None:
                        del self.manifest['scenes'][0]['checks'][key]
                    else:
                        self.manifest['scenes'][0]['checks'][key]['status'] = status
                    self.sync()
                    with self.assertRaises(ValueError):
                        self.check()

    def test_packaging_may_be_not_visible_only_with_explicit_brief_policy(self):
        self.fixture()
        self.brief['product']['packaging_required'] = False
        self.brief_binding = self.write('brief.json', self.brief)
        self.manifest['brief'] = self.brief_binding
        self.render['brief_sha256'] = self.brief_binding['sha256']
        self.manifest['render_receipt'] = self.write('render-receipt.json', self.render)
        self.manifest['scenes'][0]['checks']['packaging'] = {
            'status': 'not_visible', 'notes': 'Inspected all three frames; no box or packaging appears.'}
        self.sync()
        self.check()

    def test_placeholder_notes_and_missing_reviewer_are_refused(self):
        for notes in ('', 'match', 'looks good', 'PREENCHER observacao da cena', 'same as reference'):
            self.fixture()
            self.manifest['scenes'][0]['checks']['item']['notes'] = notes
            self.sync()
            with self.assertRaises(ValueError):
                self.check()
        self.fixture()
        del self.manifest['reviewer']
        self.sync()
        with self.assertRaises(ValueError):
            self.check()

    def test_stale_future_naive_or_invalid_review_dates_are_refused(self):
        for timestamp in ('2026-09-28T12:00:00+00:00', '2026-10-01T12:00:00+00:00',
                          '2026-09-30T12:00:00', '', None):
            self.fixture()
            self.manifest['checked_at'] = timestamp
            self.sync()
            with self.assertRaises(ValueError):
                self.check()

    def test_product_variant_campaign_and_reference_substitution_are_refused(self):
        for key in ('canonical_product_id', 'variant', 'campaign_id', 'references'):
            self.fixture()
            self.manifest[key] = [] if key == 'references' else 'different'
            self.sync()
            with self.assertRaises(ValueError):
                self.check()

    def test_source_receipt_must_bind_observed_official_identity(self):
        for key, value in [('canonical_product_id', 'other'), ('variant', 'red'),
                           ('source_url', 'https://other.example'), ('image_sha256', '0' * 64),
                           ('authority', 'search_result'), ('checked_at', '2025-01-01T00:00:00+00:00'),
                           ('observation', 'verified')]:
            self.fixture()
            reference = self.brief['facts']['identity_references'][0]
            source = json.loads((self.root / 'reference-source.json').read_text())
            source[key] = value
            reference['source_receipt'] = self.write('reference-source.json', source)
            self.brief_binding = self.write('brief.json', self.brief)
            self.manifest['brief'] = self.brief_binding
            self.render['brief_sha256'] = self.brief_binding['sha256']
            self.manifest['render_receipt'] = self.write('render-receipt.json', self.render)
            self.sync()
            with self.assertRaises(ValueError):
                self.check()

    def test_invalid_frame_coverage_and_scene_count_are_refused(self):
        for timestamps in ([], [2], [1, 2, 3], [0.1, 0.1, 3.9], [0.1, float('nan'), 3.9],
                           [0.1, True, 3.9], [0.1, 2, 4.1]):
            self.fixture()
            frames = self.manifest['scenes'][0]['frames']
            self.manifest['scenes'][0]['frames'] = [dict(frames[i % 3], timestamp=t)
                                                   for i, t in enumerate(timestamps)]
            self.sync()
            with self.assertRaises(ValueError):
                self.check()
        self.fixture()
        self.manifest['scenes'] = []
        self.sync()
        with self.assertRaises(ValueError):
            self.check()

    def test_generation_receipt_and_render_scene_cannot_be_forged(self):
        self.fixture()
        receipt = json.loads((self.root / 'scene-receipt.json').read_text())
        receipt['sha256'] = '0' * 64
        self.manifest['scenes'][0]['generation_receipt'] = self.write('scene-receipt.json', receipt)
        self.sync()
        with self.assertRaises(ValueError):
            self.check()
        self.fixture()
        self.render['segments'][0]['scene']['narration'] = 'Different scene'
        self.manifest['render_receipt'] = self.write('render-receipt.json', self.render)
        self.sync()
        with self.assertRaises(ValueError):
            self.check()

    def test_relative_traversal_and_outside_paths_are_refused(self):
        for path in ('reference.png', str(self.root / '..' / self.root.name / 'reference.png')):
            self.fixture()
            self.manifest['scenes'][0]['frames'][0]['path'] = path
            self.sync()
            with self.assertRaises(ValueError):
                self.check()
        self.fixture()
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / 'frame.png'
            outside.write_bytes(b'outside')
            self.manifest['scenes'][0]['frames'][0].update(
                path=str(outside), sha256=hashlib.sha256(outside.read_bytes()).hexdigest())
            self.sync()
            with self.assertRaises(ValueError):
                self.check()

    def test_dict_brief_must_match_exact_bound_file(self):
        self.fixture()
        self.check(copy.deepcopy(self.brief))
        altered = copy.deepcopy(self.brief)
        altered['product']['variant'] = 'red'
        with self.assertRaises(ValueError):
            self.check(altered)

    def test_missing_policy_variant_and_quality_hash_are_refused(self):
        for key in ('variant', 'packaging_required'):
            self.fixture()
            del self.brief['product'][key]
            self.brief_binding = self.write('brief.json', self.brief)
            self.manifest['brief'] = self.brief_binding
            self.sync()
            with self.assertRaises(ValueError):
                self.check()
        self.fixture()
        self.quality['video_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.check()

    def test_brief_must_pin_generation_receipt_path(self):
        self.fixture()
        del self.brief['scenes'][0]['generation_receipt']
        self.brief_binding = self.write('brief.json', self.brief)
        self.manifest['brief'] = self.brief_binding
        self.render['brief_sha256'] = self.brief_binding['sha256']
        self.manifest['render_receipt'] = self.write('render-receipt.json', self.render)
        self.sync()
        with self.assertRaises(ValueError):
            self.check()

    def test_reference_cannot_be_reused_as_a_generated_video_frame(self):
        self.fixture()
        self.manifest['scenes'][0]['frames'][0].update(
            {k: self.manifest['references'][0][k] for k in ('path', 'sha256')})
        self.sync()
        with self.assertRaises(ValueError):
            self.check()

    def test_symlink_frame_is_refused(self):
        self.fixture()
        link = self.root / 'linked-frame.png'
        try:
            link.symlink_to(self.root / 'frame-0.png')
        except OSError:
            self.skipTest('Creating symlinks is unavailable on this host')
        self.manifest['scenes'][0]['frames'][0]['path'] = str(link)
        self.sync()
        with self.assertRaises(ValueError):
            self.check()

    def test_invalid_urls_malformed_objects_and_timeline_are_refused(self):
        for value in (None, [], True, ''):
            self.fixture()
            self.quality['product_identity'] = value
            with self.assertRaises(ValueError):
                self.check()
        for url in ('file:///tmp/image', 'https://', 'https://user:pass@example.com/image',
                    'https://example.com/ image'):
            self.fixture()
            self.manifest['references'][0]['source_url'] = url
            self.brief_binding = self.write('brief.json', self.brief)
            self.manifest['brief'] = self.brief_binding
            self.sync()
            with self.assertRaises(ValueError):
                self.check()
        for start, duration in ((1, 3), (0, 2), (0, float('inf')), (True, 4)):
            self.fixture()
            self.render['segments'][0].update(start=start, duration=duration)
            self.manifest['render_receipt'] = self.write('render-receipt.json', self.render)
            self.sync()
            with self.assertRaises(ValueError):
                self.check()

    def test_duplicate_json_keys_are_refused(self):
        self.fixture()
        raw = json.dumps(self.manifest)
        raw = raw[:-1] + ', "version": 1}'
        self.quality['product_identity'] = self.write('product-identity.json', raw.encode())
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
