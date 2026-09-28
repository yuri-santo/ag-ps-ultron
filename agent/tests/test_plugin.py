import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ultron_team import register


class Context:
    def __init__(self):
        self.tools = {}
        self.hooks = {}
        self.sections = []
    def get_config(self, key, default=None):
        return default
    def register_tool(self, **kwargs):
        self.tools[kwargs['name']] = kwargs
    def register_hook(self, name, callback):
        self.hooks[name] = callback
    def register_system_prompt_section(self, *args, **kwargs):
        self.sections.append(kwargs)


class PluginTests(unittest.TestCase):
    def context(self, home):
        ctx = Context()
        with patch.dict(sys.modules, {'hermes_constants': SimpleNamespace(get_hermes_home=lambda: home)}):
            register(ctx)
        return ctx

    def test_default_only_coordinates_and_unconnected_voice_is_disabled(self):
        ctx = self.context('/root/.hermes')
        self.assertEqual(set(ctx.tools), {'ultron_specialist'})
        self.assertIsNone(ctx.hooks['transform_llm_output'](response_text='texto'*500, platform='telegram'))
        self.assertIsInstance(ctx.hooks['pre_llm_call'](user_message='oi', session_id='x'), str)

    def test_system_prompt_respects_installed_sdk_limit(self):
        with patch('pathlib.Path.is_file', return_value=True), patch('pathlib.Path.read_text', return_value='Synthetic identity'):
            ctx = self.context('/root/.hermes')
        self.assertEqual(len(ctx.sections), 1)
        self.assertLessEqual(ctx.sections[0]['max_chars'], 4000)

    def test_voice_failure_preserves_text_and_explains_missing_audio(self):
        ctx = self.context('/root/.hermes')
        ctx.get_config = lambda key, default=None: True if key == 'voice_enabled' else default
        ctx.hooks['pre_llm_call'](user_message='mande um áudio', session_id='x')
        fake_config = SimpleNamespace(load_config_readonly=lambda: {'tts': {'elevenlabs': {'voice_id': 'test'}}})
        fake_tts = SimpleNamespace(_resolve_provider_key=lambda *args: None)
        with patch.dict(sys.modules, {'hermes_cli.config': fake_config, 'tools.tts_tool': fake_tts}):
            result = ctx.hooks['transform_llm_output'](response_text='1. Confira. 2. Execute.', platform='telegram', session_id='x')
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('1. Confira. 2. Execute.'))
        self.assertIn('Não consegui gerar o áudio', result)

    def test_mail_profiles_have_only_account_bound_tools(self):
        for profile in ('gmail', 'easysapers'):
            ctx = self.context('/root/.hermes/profiles/' + profile)
            self.assertEqual(set(ctx.tools), {'mail_list', 'mail_read', 'mail_search', 'mail_draft'})
            for tool in ctx.tools.values():
                self.assertNotIn('account', tool['schema']['parameters']['properties'])
            self.assertEqual(ctx.hooks, {})

    def test_meetings_profile_only_queries_calendar_and_context(self):
        ctx = self.context('/root/.hermes/profiles/reunioes')
        self.assertEqual(set(ctx.tools), {'meeting_agenda', 'meeting_context'})

    def test_existing_specialists_untouched_by_plugin(self):
        self.assertEqual(self.context('/root/.hermes/profiles/thor').tools, {})


if __name__ == '__main__':
    unittest.main()
