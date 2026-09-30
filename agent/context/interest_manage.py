"""Manage only explicit interests, never infer purchase or transaction consent."""
import argparse
import datetime as dt
import json
import sys
from interests import InterestStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['list', 'upsert', 'close'])
    parser.add_argument('--id')
    args = parser.parse_args()
    store = InterestStore()
    if args.action == 'list':
        result = store.list()
    elif args.action == 'close':
        store.close(args.id)
        result = {'status': 'closed', 'id': args.id}
    else:
        value = json.load(sys.stdin)
        expiry = dt.datetime.fromisoformat(value['expires_at'])
        days = (expiry - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400
        if not 0 < days <= 90:
            raise ValueError('New interests require an expiry within 90 days')
        result = store.upsert(value)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
