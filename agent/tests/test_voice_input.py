"""Use gateway metadata: successful STT deliberately contains no voice marker."""
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ultron_team import register
from test_plugin import Context


class VoiceInputTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Context()
        with patch.dict(sys.modules, {'hermes_constants': SimpleNamespace(get_hermes_home=lambda: '/root/.hermes')}):
            register(self.ctx)
        self.ctx.get_config = lambda key, default=None: True if key == 'voice_enabled' else default
        self.env = {
            'HERMES_SESSION_PLATFORM': 'telegram',
            'HERMES_SESSION_CHAT_ID': 'chat-a',
            'HERMES_SESSION_USER_ID': 'yuri',
            'HERMES_SESSION_THREAD_ID': '',
            'HERMES_SESSION_MESSAGE_ID': '100',
            'HERMES_SESSION_PROFILE': '',
        }
        self.modules = {
            'gateway.session_context': SimpleNamespace(get_session_env=lambda key, default='': self.env.get(key, default)),
            'hermes_cli.config': SimpleNamespace(load_config_readonly=lambda: {'tts': {'elevenlabs': {'voice_id': 'sample'}}}),
            'tools.tts_tool': SimpleNamespace(_resolve_provider_key=lambda *args: None),
        }

    def incoming(self, kind='voice', message_id='100', chat_id='chat-a', profile=''):
        source = SimpleNamespace(platform=SimpleNamespace(value='telegram'), chat_id=chat_id,
                                 user_id='yuri', thread_id=None, profile=profile)
        event = SimpleNamespace(message_type=SimpleNamespace(value=kind), source=source, message_id=message_id)
        hook = self.ctx.hooks.get('pre_gateway_dispatch')
        self.assertTrue(callable(hook), 'Register inbound voice metadata before STT removes its marker')
        self.assertIsNone(hook(event=event))

    def respond(self, request='"Qual o prazo?"', session='session-a'):
        with patch.dict(sys.modules, self.modules):
            self.ctx.hooks['pre_llm_call'](user_message=request, session_id=session)
            return self.ctx.hooks['transform_llm_output'](
                response_text='Ainda nao tenho esse prazo confirmado.', platform='telegram', session_id=session)

    def test_successful_voice_transcription_attempts_audio_and_keeps_text_on_missing_key(self):
        self.incoming()
        result = self.respond()
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('Ainda nao tenho esse prazo confirmado.'))
        self.assertIn('gerar o', result)

    def test_typed_quotation_is_not_mistaken_for_voice(self):
        self.incoming(kind='text')
        self.assertIsNone(self.respond())

    def test_voice_metadata_does_not_leak_to_next_message(self):
        self.incoming()
        self.assertIsNotNone(self.respond())
        self.env['HERMES_SESSION_MESSAGE_ID'] = '101'
        self.assertIsNone(self.respond())

    def test_same_message_id_in_other_chat_does_not_trigger_audio(self):
        self.incoming(chat_id='chat-b')
        self.assertIsNone(self.respond())

    def test_text_only_instruction_wins_over_real_voice_input(self):
        self.incoming()
        self.assertIsNone(self.respond(request='"Responda somente texto"'))

    def test_other_profile_voice_is_not_consumed_by_ultron(self):
        self.incoming(profile='thor')
        self.assertIsNone(self.respond())

    def test_gateway_observer_does_not_record_when_voice_is_disabled(self):
        self.ctx.get_config = lambda key, default=None: default
        self.incoming()
        self.ctx.get_config = lambda key, default=None: True if key == 'voice_enabled' else default
        self.assertIsNone(self.respond())


if __name__ == '__main__':
    unittest.main()