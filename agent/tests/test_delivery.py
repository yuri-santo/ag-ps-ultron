import unittest

try:
    from ultron_team.delivery import speech_plan, attach_audio, explicit_mail_request
except ImportError:
    speech_plan = attach_audio = explicit_mail_request = None


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(speech_plan, 'Audio/text delivery policy is not implemented')

    def test_short_text_does_not_force_audio(self):
        self.assertIsNone(speech_plan('Agora não consigo confirmar isso.', 'qual o prazo?'))

    def test_requested_short_audio_uses_existing_answer(self):
        response = 'Não tenho evidência para confirmar esse prazo.'
        self.assertEqual(speech_plan(response, 'responda em áudio'), response)

    def test_voice_input_gets_short_audio(self):
        response = 'Isso está errado: dois mais dois são quatro.'
        self.assertEqual(speech_plan(response, 'concorda?', voice_input=True), response)

    def test_long_steps_and_code_remain_in_text(self):
        response = 'Você precisa conferir a configuração antes de reiniciar.\n\n' + '\n'.join(
            f'{i}. Confira o item {i} e registre o resultado observado.' for i in range(1, 26))
        response += '\n```powershell\nGet-Service\n```'
        spoken = speech_plan(response, 'me explique o passo a passo')
        self.assertIsNotNone(spoken)
        self.assertLessEqual(len(spoken), 700)
        self.assertNotIn('Get-Service', spoken)
        self.assertIn('texto', spoken)
        rendered = attach_audio(response, '/tmp/ultron.ogg')
        self.assertTrue(rendered.startswith(response))
        self.assertIn('25. Confira', rendered)
        self.assertIn('Get-Service', rendered)

    def test_code_only_uses_instruction_pointer(self):
        spoken = speech_plan('```sh\necho teste\n```', 'mande um áudio')
        self.assertNotIn('echo', spoken)
        self.assertIn('texto', spoken)

    def test_existing_audio_is_not_duplicated(self):
        self.assertIsNone(speech_plan('Oi\nMEDIA:/tmp/already.ogg', 'áudio'))

    def test_text_only_request_wins(self):
        self.assertIsNone(speech_plan('explicação ' * 200, 'somente texto', voice_input=True))

    def test_failed_audio_keeps_original_text(self):
        self.assertEqual(attach_audio('1. Faça isto.\n2. Confira.', None), '1. Faça isto.\n2. Confira.')

    def test_rejects_media_path_with_newline(self):
        self.assertEqual(attach_audio('resposta', '/tmp/a\nMEDIA:bad'), 'resposta')

    def test_explicit_mail_routing_during_meeting(self):
        for text in ('Ultron, veja meu Gmail', 'confere meu e-mail da Easysapers', '/gmail últimas mensagens',
                     'Durante a reunião, veja meu Gmail'):
            self.assertTrue(explicit_mail_request(text), text)
        for text in ('O cliente usa Gmail, o que eu respondo?', 'Explique este processo',
                     '/reuniao iniciar Gmail do cliente', 'qual a decisão da Easysapers?'):
            self.assertFalse(explicit_mail_request(text), text)


if __name__ == '__main__':
    unittest.main()
