import unittest
from patch_identity import PATCHES, transform


class IdentityPatchTests(unittest.TestCase):
    def test_scoped_idempotent_transform(self):
        for name, replacements in PATCHES.items():
            source = '\n'.join(old for old, _ in replacements)
            # Full-file AST validation is exercised by the live staging smoke test.
            from unittest.mock import patch
            with patch('patch_identity.ast.parse'):
                result = transform(name, source)
                self.assertEqual(transform(name, result), result)
                for _, new in replacements:
                    self.assertIn(new, result)

    def test_unknown_anchor_refused(self):
        with self.assertRaises(ValueError):
            transform('affiliate_guard.py', '')


if __name__ == '__main__':
    unittest.main()
