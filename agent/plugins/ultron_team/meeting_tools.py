"""Read the existing professional calendar and private meeting store."""
from datetime import date
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess


class MeetingTools:
    def __init__(self, base='/root/.hermes', *, runner=subprocess.run, owner=0):
        self.base = Path(base)
        self.runner = runner
        self.owner = owner

    def agenda(self, day=''):
        try:
            if day:
                if date.fromisoformat(day).isoformat() != day:
                    raise ValueError('invalid date')
            argv = ['/root/tools/venv/bin/python', str(self.base / 'plugins/meeting_copilot/calendar_bridge.py')]
            if day:
                argv += ['--day', day]
            result = self.runner(argv, capture_output=True, text=True, encoding='utf-8', timeout=40)
            payload = json.loads(result.stdout)
            return {'status': 'error' if result.returncode or payload.get('error') else 'ok', **payload}
        except Exception as exc:
            return {'status': 'error', 'error': type(exc).__name__, 'events': []}

    def context(self, limit=80):
        if type(limit) is not int or not 1 <= limit <= 100:
            return {'status': 'error', 'error': 'invalid_limit'}
        path = self.base / 'meeting_copilot/meetings.db'
        if not path.is_file():
            return {'status': 'ok', 'meeting': None, 'events': []}
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
                db.row_factory = sqlite3.Row
                row = db.execute('SELECT id,title,status,created FROM sessions WHERE user_id=? '
                                 'ORDER BY created DESC LIMIT 1', (self.owner,)).fetchone()
                if row is None:
                    return {'status': 'ok', 'meeting': None, 'events': []}
                events = db.execute('SELECT seq,kind,channel,at,text FROM events WHERE session=? '
                                    'ORDER BY seq DESC LIMIT ?', (row['id'], limit)).fetchall()
                total = db.execute('SELECT count(*) FROM events WHERE session=?', (row['id'],)).fetchone()[0]
                records = [dict(e) for e in reversed(events)]
                trimmed = False
                remaining = 60000
                for item in records:
                    text = item['text'] or ''
                    item['text'] = text[:remaining]
                    trimmed = trimmed or len(text) > remaining
                    remaining = max(0, remaining-len(item['text']))
                return {'status': 'ok', 'meeting': dict(row), 'events': records,
                        'truncated': total > limit or trimmed, 'total_events': total,
                        'notice': 'Recorte de consulta; a transcrição integral permanece no copiloto.'}
        except sqlite3.Error as exc:
            return {'status': 'error', 'error': type(exc).__name__}
