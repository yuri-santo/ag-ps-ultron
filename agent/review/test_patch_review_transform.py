import tempfile
import unittest
from pathlib import Path

from patch_review_transform import patch_file, ANCHOR, REPLACEMENT


class ReviewTransformPatchTests(unittest.TestCase):
    def test_marks_replacements_as_transformed_and_preserves_other_bytes(self):
        for eol in ('\n', '\r\n'):
            with self.subTest(eol=repr(eol)), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'turn_finalizer.py'
                before = ('prefix\n' + ANCHOR + 'suffix\n').replace('\n', eol).encode()
                path.write_bytes(before)
                self.assertTrue(patch_file(path))
                self.assertEqual(path.read_bytes(), before.replace(
                    ANCHOR.replace('\n', eol).encode(), REPLACEMENT.replace('\n', eol).encode()))
                self.assertFalse(patch_file(path))
                backups = list(path.parent.glob('*.bak-ultron-transform-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), before)

    def test_unknown_or_duplicated_anchor_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'turn_finalizer.py'
            for text in ('upstream changed', ANCHOR + ANCHOR):
                path.write_text(text)
                with self.assertRaises(RuntimeError):
                    patch_file(path)
                self.assertEqual(path.read_text(), text)


if __name__ == '__main__':
    unittest.main()
