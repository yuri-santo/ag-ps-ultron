import unittest
from copy import deepcopy
from cron_migration import updates_for


class CronMigrationTests(unittest.TestCase):
    def test_preserves_schedule_and_permissions(self):
        job = {'name': 'tiktok-mercenario-5x', 'prompt': 'python3 /root/tools/tiktok/auto_tiktok_publicador_loop.py',
               'schedule': {'expr': '0 12,15,18,21,0 * * *'}, 'enabled': True, 'fire_claim': None}
        before = deepcopy(job)
        updates = updates_for(job)
        self.assertEqual(job, before)
        self.assertEqual(set(updates), {'prompt', 'context_from'})
        self.assertIn('affiliate_autonomy.py tick', updates['prompt'])
        self.assertEqual(updates['context_from'], [])

    def test_refuses_running_or_unknown_job(self):
        for job in ({'name': 'other'}, {'name': 'tiktok-mercenario-5x', 'prompt': 'unknown'},
                    {'name': 'tiktok-mercenario-5x', 'fire_claim': {'active': True}}):
            with self.assertRaises(ValueError):
                updates_for(job)


if __name__ == '__main__':
    unittest.main()
