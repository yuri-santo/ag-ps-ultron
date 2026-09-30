import datetime as dt
from pathlib import Path
import tempfile
import unittest
from interests import InterestStore, eligible, gate

NOW = dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc)


def item(topic='shopping', **changes):
    value = dict(id='test', topic=topic, status='active', source_quote='Quero monitorar este item',
                 expires_at='2026-10-30T00:00:00+00:00', criteria={'query': 'SSD modelo exato',
                 'budget_max': 500, 'currency': 'BRL'})
    value.update(changes)
    return value


class InterestsTests(unittest.TestCase):
    def test_missing_expired_or_proposed_do_not_wake(self):
        for value in [item(status='proposed'), item(expires_at='2026-09-01T00:00:00+00:00'),
                      item(source_quote=''), item(expires_at='bad'), item(criteria={})]:
            self.assertFalse(eligible(value, NOW))
        self.assertFalse(gate([], 'shopping', NOW)['wakeAgent'])

    def test_require_budget_or_explicit_lowest_price_mode(self):
        self.assertTrue(eligible(item(), NOW))
        self.assertFalse(eligible(item(criteria={'query': 'SSD'}), NOW))
        self.assertTrue(eligible(item(criteria={'query': 'SSD', 'price_mode': 'lowest_verified'}), NOW))
        self.assertFalse(eligible(item(criteria={'query': 'SSD', 'budget_max': float('nan')}), NOW))

    def test_travel_needs_route_and_future_dates(self):
        self.assertFalse(eligible(item('travel', criteria={'destination': 'Recife'}), NOW))
        criteria={'origin':'Belo Horizonte','destination':'Recife','departure':'2026-12-01',
                  'return':'2026-12-07','travelers':1,'budget_max':3000,'currency':'BRL'}
        self.assertTrue(eligible(item('travel',criteria=criteria),NOW))
        criteria['return']='2026-11-01'
        self.assertFalse(eligible(item('travel',criteria=criteria),NOW))

    def test_property_keeps_information_only_without_affordability_claim(self):
        self.assertTrue(eligible(item('property',criteria={'locations':['Santa Luzia'],
                        'purpose':'research','budget_status':'unknown'}),NOW))
        self.assertFalse(eligible(item('trading',criteria={'query':'acoes'}),NOW))

    def test_store_upsert_does_not_duplicate_or_modify_others(self):
        with tempfile.TemporaryDirectory() as temp:
            store=InterestStore(Path(temp)/'interests.json')
            store.upsert(item())
            store.upsert(item(criteria={'query':'SSD atualizado','price_mode':'lowest_verified'}))
            self.assertEqual(len(store.list()),1)
            self.assertEqual(store.list()[0]['criteria']['query'],'SSD atualizado')
            store.close('test')
            self.assertEqual(store.list()[0]['status'],'closed')

    def test_corrupt_store_does_not_wake_or_get_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'interests.json';path.write_text('bad')
            store=InterestStore(path)
            with self.assertRaises(ValueError):store.upsert(item())
            self.assertEqual(path.read_text(),'bad')


if __name__=='__main__':unittest.main()
