"""A specialist's pending review cannot become a successful committee report."""
import tempfile
import unittest
from pathlib import Path

try:
    from patch_worker_completion import patch_file, ANCHOR
except ImportError:
    patch_file = None
    ANCHOR = ''


class WorkerCompletionTests(unittest.TestCase):
    def test_pending_missing_failed_or_interrupted_is_not_success(self):
        self.assertIsNotNone(patch_file, 'completion patch is missing')
        source = 'def run(result):\n' + ANCHOR + '        return failed, completed, model_review\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'worker.py'
            path.write_text(source)
            self.assertTrue(patch_file(path))
            self.assertFalse(patch_file(path))
            namespace = {}
            exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
            run = namespace['run']
            for result in (
                {'final_response': 'text', 'completed': False},
                {'final_response': 'text'},
                {'final_response': 'text', 'completed': True, 'interrupted': True},
                {'final_response': 'text', 'completed': True, 'partial': True},
                {'final_response': 'text', 'completed': True, 'model_review': {'completed': False}},
                {'final_response': 'text', 'completed': True, 'model_review': 'invalid'},
                {'final_response': '', 'completed': True},
            ):
                with self.subTest(result=result):
                    self.assertTrue(run(result)[0])
            self.assertFalse(run({'final_response': 'text', 'completed': True,
                                  'model_review': {'completed': True}})[0])
            self.assertFalse(run({'final_response': 'text', 'completed': True})[0])


if __name__ == '__main__':
    unittest.main()
