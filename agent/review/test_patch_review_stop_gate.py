import tempfile
import unittest
from pathlib import Path

from patch_review_stop_gate import patch_file


class PatchTests(unittest.TestCase):
    def test_adds_single_review_continuation_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'turn_stop_gates.py'
            source.write_text('def apply_stop_gates():\n    return StopGateVerdict(\n'
                              '        continue_turn=False, final_response=final_response,\n')
            self.assertTrue(patch_file(source))
            content = source.read_text()
            self.assertIn('review_stop_feedback', content)
            self.assertIn('_review_stop_synthetic', content)
            self.assertFalse(patch_file(source))
            self.assertEqual(source.read_text(), content)


if __name__ == '__main__':
    unittest.main()
