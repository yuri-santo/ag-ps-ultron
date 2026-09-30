import unittest
from patch_affiliate import PATCHES, transform


class PatchTests(unittest.TestCase):
    def test_each_patch_is_scoped_and_idempotent(self):
        for name, pairs in PATCHES.items():
            before = '\n'.join(old for old, new in pairs)
            after = transform(name, before)
            for old, new in pairs:
                self.assertIn(new, after)
            self.assertEqual(transform(name, after), after)

    def test_unknown_source_is_rejected(self):
        for name in PATCHES:
            with self.assertRaises(ValueError):
                transform(name, 'unknown upstream')

    def test_duplicate_anchor_is_rejected(self):
        name = 'affiliate_render.py'
        source = '\n'.join(old for old, new in PATCHES[name])
        with self.assertRaises(ValueError):
            transform(name, source + '\n' + PATCHES[name][0][0])

    def test_publication_requires_broker_to_have_seen_preflight(self):
        source = ("from affiliate_registry import ProductRegistry,identity_aliases\n"
                  "    render=json.loads((out/'render-receipt.json').read_text())")
        required = "    require_review_artifacts(review_info,[brief_path,out/'caption.txt',out/'comment.txt',out/'quality.json',out/'asr.json',video_path])"
        source += '\n' + required
        self.assertIn("out/'asr.json',out/'media-preflight.json',video_path]",
                      transform('affiliate_guard.py', source))


if __name__ == '__main__':
    unittest.main()
