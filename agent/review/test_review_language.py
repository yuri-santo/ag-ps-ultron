"""The actual review transport carries the assistant's trusted language context."""
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_review as review


class ReviewerLanguageTests(unittest.TestCase):
    def test_transport_prompt_uses_pt_br_without_overriding_explicit_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'router.sqlite'
            with sqlite3.connect(database) as conn:
                conn.executescript('''
                    CREATE TABLE providerConnections (provider TEXT, isActive INTEGER);
                    INSERT INTO providerConnections VALUES ('antigravity', 1);
                    CREATE TABLE kv (scope TEXT, key TEXT, value TEXT);
                ''')
            response = {'model': 'test-reviewer', 'choices': [{'message': {'content': '{}'}}]}
            with patch.object(review, 'DB', database), \
                 patch.object(review.Path, 'read_text', return_value='model:\n  api_key: fixture'), \
                 patch.object(review.urllib.request, 'urlopen',
                              return_value=io.BytesIO(json.dumps(response).encode())) as send:
                review.router_transport({'model': 'ag/test-reviewer'}, {'task': 'ta ai ?'}, 100, 2)
                body = json.loads(send.call_args.args[0].data)
            prompt = body['messages'][0]['content']
            self.assertIn('Brazilian Portuguese (pt-BR)', prompt)
            self.assertIn('explicit request for another language', prompt)
            self.assertIn('informal', prompt)


if __name__ == '__main__':
    unittest.main()
