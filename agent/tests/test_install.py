import copy
import unittest
try:
    from deploy import profile_config, activate_config, update_soul
except ImportError:
    profile_config = activate_config = update_soul = None


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(profile_config, 'Scoped installer is not implemented')
        self.original = {'model': {'default': 'existing', 'api_key': 'test-only'},
            'fallback_providers': [{'model': 'fallback'}],
            'plugins': {'enabled': ['claude_harness', 'meeting_copilot'],
                        'entries': {'meeting_copilot': {'settings': {'interval': 60}}}},
            'platform_toolsets': {'telegram': ['hermes-telegram'], 'cli': ['hermes-cli']},
            'custom': {'preserve': True}}

    def test_activation_preserves_existing_integrations(self):
        before = copy.deepcopy(self.original)
        result = activate_config(self.original)
        self.assertEqual(self.original, before)
        self.assertEqual(result['model'], before['model'])
        self.assertEqual(result['custom'], before['custom'])
        self.assertIn('meeting_copilot', result['plugins']['enabled'])
        self.assertIn('claude_harness', result['plugins']['enabled'])
        self.assertEqual(result['plugins']['entries']['meeting_copilot']['settings']['interval'], 60)
        self.assertTrue(result['plugins']['entries']['meeting_copilot']['settings'].get('team_specialist', False))
        self.assertEqual(result, activate_config(result))
        self.assertFalse(result['plugins']['entries']['ultron_team']['settings']['voice_enabled'])

    def test_new_mail_profile_has_no_parent_tools_or_credentials_for_mail(self):
        result = profile_config(self.original, 'gmail')
        self.assertEqual(result['platform_toolsets']['cli'], ['ultron_mail', 'memory'])
        self.assertNotIn('claude_harness', result['plugins']['enabled'])
        self.assertEqual(result['model'], self.original['model'])
        self.assertEqual(result['mcp_servers'], {})

    def test_soul_append_is_idempotent(self):
        text = update_soul('# Ultron\nExisting rule.', 'Casual and honest.')
        self.assertIn('Existing rule.', text)
        self.assertEqual(text, update_soul(text, 'Casual and honest.'))


if __name__ == '__main__':
    unittest.main()
