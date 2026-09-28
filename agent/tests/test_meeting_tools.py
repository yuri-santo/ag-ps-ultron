import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

try:
    from ultron_team.meeting_tools import MeetingTools
except ImportError:
    MeetingTools = None


class MeetingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(MeetingTools, 'Meeting tools have not been implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_missing_database_does_not_create_one(self):
        result = MeetingTools(self.root).context()
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['meeting'])
        self.assertFalse((self.root / 'meeting_copilot/meetings.db').exists())

    def test_only_owner_meeting_and_bounded_events(self):
        directory = self.root / 'meeting_copilot'
        directory.mkdir()
        with sqlite3.connect(directory / 'meetings.db') as db:
            db.executescript('CREATE TABLE sessions(id TEXT,user_id INTEGER,title TEXT,status TEXT,created REAL,state TEXT);'
                             'CREATE TABLE events(seq INTEGER,session TEXT,kind TEXT,channel TEXT,at REAL,text TEXT,extra TEXT);')
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', ('mine', 0, 'Teste', 'paused', 1, '{}'))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', ('other', 5, 'Outro', 'active', 2, '{}'))
            for i in range(100):
                db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)', (i, 'mine', 'transcript', 'mic', i, f'fala {i}', '{}'))
        db.close()
        result = MeetingTools(self.root).context(limit=5)
        self.assertEqual(result['meeting']['id'], 'mine')
        self.assertEqual(len(result['events']), 5)
        self.assertEqual(result['events'][-1]['text'], 'fala 99')
        self.assertTrue(result['truncated'])
        json.dumps(result)

    def test_invalid_dates_are_rejected_without_process(self):
        calls = []
        result = MeetingTools(self.root, runner=lambda *a, **k: calls.append(a)).agenda('2026-09-13;rm')
        self.assertEqual(result['status'], 'error')
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
