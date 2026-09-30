"""Private, explicit, expiring interests for inexpensive native cron wake gates."""
import argparse
from contextlib import contextmanager
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import tempfile

TOPICS = {'shopping', 'travel', 'property', 'trading'}
DEFAULT_STORE = '/root/ultron-local/active-interests.json'


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _positive(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def _price(criteria):
    return (criteria.get('price_mode') == 'lowest_verified' or
            (_positive(criteria.get('budget_max')) and
             bool(re.fullmatch('[A-Z]{3}', str(criteria.get('currency', ''))))))


def eligible(value, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        if not isinstance(value, dict) or value.get('status') != 'active':
            return False
        if not _text(value.get('source_quote')):
            return False
        expiry = dt.datetime.fromisoformat(value['expires_at'])
        if expiry.tzinfo is None or expiry <= now:
            return False
        c = value['criteria']
        if not isinstance(c, dict):
            return False
        topic = value.get('topic')
        if topic == 'shopping':
            return bool(_text(c.get('query')) and _price(c))
        if topic == 'travel':
            departure = dt.date.fromisoformat(c['departure'])
            arrival = dt.date.fromisoformat(c.get('return', c['departure']))
            travelers = c.get('travelers')
            return bool(_text(c.get('origin')) and _text(c.get('destination'))
                        and departure >= now.date() and arrival >= departure
                        and isinstance(travelers, int) and not isinstance(travelers, bool)
                        and travelers > 0 and _price(c))
        if topic == 'property':
            locations = c.get('locations')
            return bool(isinstance(locations, list) and locations
                        and all(_text(x) for x in locations)
                        and c.get('purpose') == 'research'
                        and (_price(c) or c.get('budget_status') == 'unknown'))
        if topic == 'trading':
            instruments = c.get('instruments')
            return bool(_text(c.get('goal')) and isinstance(instruments, list)
                        and instruments and all(_text(x) for x in instruments)
                        and _positive(c.get('risk_budget'))
                        and re.fullmatch('[A-Z]{3}', str(c.get('currency', '')))
                        and c.get('information_only') is True)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return False


def gate(values, topic, now=None):
    if topic not in TOPICS:
        raise ValueError('Unknown interest topic')
    active = [v for v in values if v.get('topic') == topic and eligible(v, now)]
    return {'wakeAgent': bool(active), 'topic': topic, 'interests': active,
            'reason': 'active_explicit_interest' if active else 'no_actionable_interest'}


class InterestStore:
    def __init__(self, path=DEFAULT_STORE):
        self.path = Path(path)

    def list(self):
        if not self.path.exists():
            return []
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(value, dict) or value.get('version') != 1
                    or not isinstance(value.get('interests'), list)
                    or not all(isinstance(x, dict) for x in value['interests'])):
                raise ValueError('Invalid interests schema')
            return value['interests']
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('Corrupt interests store; refusing overwrite') from exc

    @contextmanager
    def _lock(self):
        # The deployed Hermes service is Linux; lock covers read-modify-write.
        import fcntl
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.path) + '.lock', 'a', encoding='utf-8') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _write(self, values):
        fd, temporary = tempfile.mkstemp(prefix='.interests-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'version': 1, 'interests': values}, stream,
                          ensure_ascii=False, allow_nan=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def upsert(self, value):
        if (not isinstance(value, dict)
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', str(value.get('id', '')))
                or value.get('topic') not in TOPICS
                or value.get('status') not in {'active', 'proposed', 'closed'}
                or not _text(value.get('source_quote'))
                or not isinstance(value.get('criteria'), dict)):
            raise ValueError('Interest requires id, topic, status, user quote and criteria')
        expiry = dt.datetime.fromisoformat(value.get('expires_at', ''))
        if expiry.tzinfo is None:
            raise ValueError('Expiry must include timezone')
        json.dumps(value, allow_nan=False)
        with self._lock():
            values = self.list()
            values = [x for x in values if x.get('id') != value['id']] + [value]
            self._write(values)
        return value

    def close(self, interest_id):
        with self._lock():
            values = self.list()
            found = False
            for value in values:
                if value.get('id') == interest_id:
                    value['status'] = 'closed'
                    found = True
            if not found:
                raise ValueError('Unknown interest id')
            self._write(values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('topic', choices=sorted(TOPICS))
    parser.add_argument('--store', default=DEFAULT_STORE)
    args = parser.parse_args()
    try:
        result = gate(InterestStore(args.store).list(), args.topic)
    except (OSError, ValueError, TypeError):
        result = {'wakeAgent': False, 'reason': 'interest_store_unavailable'}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
