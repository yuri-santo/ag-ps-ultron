import unittest
from cron_interests import updates


class NativeGateTests(unittest.TestCase):
    def test_only_payload_changes(self):
        value = updates({'name':'monitor-promos-novos'})
        self.assertEqual(value['script'], 'interest_shopping.py')
        self.assertFalse(value['no_agent'])
        for field in ['schedule','enabled','state','deliver','tools','skills']:
            self.assertNotIn(field, value)

    def test_never_edit_running_job(self):
        with self.assertRaises(ValueError):
            updates({'name':'monitor-promos-novos','fire_claim':{'id':'active'}})


if __name__ == '__main__':
    unittest.main()
