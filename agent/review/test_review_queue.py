"""The shared review slot orders interactive work ahead of queued jobs."""
import json
import tempfile
import unittest
from pathlib import Path

from model_review import next_review_ticket


class QueueTests(unittest.TestCase):
    def test_interactive_precedes_scheduled_and_fifo_within_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp)
            for name, mode, when in (
                    ('job-old', 'scheduled', 1), ('chat-old', 'interactive', 2),
                    ('chat-new', 'interactive', 3)):
                (queue / f'{name}.json').write_text(json.dumps({
                    'pid': 999999, 'delivery_mode': mode, 'created_at': when}))
            self.assertEqual(next_review_ticket(queue, check_liveness=False), 'chat-old')

    def test_stale_tickets_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp)
            (queue / 'stale.json').write_text(json.dumps({
                'pid': 999999, 'delivery_mode': 'interactive', 'created_at': 1}))
            (queue / 'live.json').write_text(json.dumps({
                'pid': 1, 'delivery_mode': 'scheduled', 'created_at': 2}))
            self.assertEqual(next_review_ticket(queue), 'live')


if __name__ == '__main__':
    unittest.main()
