import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import affiliate_quality as quality


class QualityTests(unittest.TestCase):
    def test_audio_fades_follow_real_audio_duration(self):
        self.assertEqual(quality.voice_filter(2),
                         'aresample=48000,afade=t=in:st=0:d=0.03,afade=t=out:st=1.970000:d=0.03')
        with self.assertRaises(ValueError):
            quality.voice_filter(float('nan'))

    def test_failed_check_does_not_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'video.mp4'
            video.write_bytes(b'media')
            report = {'path': str(video), 'technical_pass': False, 'errors': ['missing audio']}
            with patch.object(quality, 'run_preflight', return_value=report):
                with self.assertRaises(ValueError):
                    quality.check_render(video, 30)
            self.assertFalse(json.loads((video.parent / 'media-preflight.json').read_text())['technical_pass'])

    def test_gate_binds_exact_media_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'video.mp4'
            video.write_bytes(b'media')
            report = {'path': str(video), 'sha256': quality.sha256(video),
                      'technical_pass': True, 'full_decode_passed': True, 'warnings': []}
            with patch.object(quality, 'run_preflight', return_value=report):
                binding = quality.check_render(video, 30)
            self.assertEqual(quality.require_preflight(video, {'preflight': binding}), report)
            video.write_bytes(b'different')
            with self.assertRaises(ValueError):
                quality.require_preflight(video, {'preflight': binding})

    def test_old_render_needs_new_inspection(self):
        with self.assertRaises(ValueError):
            quality.require_preflight(Path('video.mp4'), {})


if __name__ == '__main__':
    unittest.main()
