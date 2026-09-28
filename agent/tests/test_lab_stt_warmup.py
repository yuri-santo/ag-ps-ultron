import os, unittest, wave
from ultron_lab import stt_warmup


class WarmupTests(unittest.TestCase):
    def test_only_the_gateway_service_warms(self):
        env = {'INVOCATION_ID': 'x'}
        self.assertTrue(stt_warmup.is_gateway_process(['hermes', 'gateway', 'run'], env))
        self.assertFalse(stt_warmup.is_gateway_process(['hermes', 'gateway', 'run'], {}))
        self.assertFalse(stt_warmup.is_gateway_process(['hermes', 'dashboard'], env))
        self.assertFalse(stt_warmup.is_gateway_process(['python', '-m', 'pytest'], env))

    def test_warm_transcribes_one_second_of_silence(self):
        seen = {}
        def transcribe(path):
            with wave.open(path) as w:
                seen.update(frames=w.getnframes(), rate=w.getframerate())
            return {'success': True, 'transcript': ''}
        self.assertEqual(stt_warmup.warm(transcribe, delay=0, sleep=lambda s: None), 'ok')
        self.assertEqual(seen, {'frames': 16000, 'rate': 16000})

    def test_errors_never_propagate(self):
        def boom(path):
            raise RuntimeError('sem modelo')
        self.assertEqual(stt_warmup.warm(boom, delay=0, sleep=lambda s: None), 'falhou')


if __name__ == '__main__':
    unittest.main()
