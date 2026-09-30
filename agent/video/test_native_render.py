"""Opt-in local render smoke test; no TTS provider, browser or publication."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('ULTRON_NATIVE_RENDER_TEST') == '1', 'Local native integration opt-in')
class NativeRenderTests(unittest.TestCase):
    def test_live_publication_guard_requires_preflight_in_review_evidence(self):
        sys.path.insert(0, '/root/tools/tiktok')
        import affiliate_guard
        import affiliate_dispatch
        output = Path('/tmp/synthetic-campaign/render')
        video = output / 'video.mp4'
        brief = {'caption': 'Synthetic', 'product': {'expected_account': 'test-account'},
                 'campaign_id': 'fixture', 'trend_evidence': {}}
        campaign = {'stage': 'generated', 'artifact': {'path': str(video)}}
        with patch.object(affiliate_guard, 'validate_bundle', return_value=(brief, campaign, output, {})), \
                patch.object(affiliate_guard, 'validate_trends'), \
                patch.object(affiliate_guard, 'require_product_identity', return_value={
                    'artifacts': [{'path': str(output / 'product-identity.json')}]}), \
                patch.object(affiliate_guard, 'require_review_artifacts') as require, \
                patch.object(affiliate_dispatch, 'slot_at', return_value='fixture-slot'):
            affiliate_guard.publication_guard('/tmp/brief.json', video, 'Synthetic', 'test-account',
                                              {'review_task_id': 'fixture-final'})
        self.assertIn(output / 'media-preflight.json', require.call_args_list[0].args[1])
        self.assertIn(str(output / 'product-identity.json'), require.call_args_list[-1].args[1])

    def test_real_ffmpeg_render_keeps_preflight_and_audio_envelopes(self):
        root = Path('/root/tools/tiktok')
        sys.path.insert(0, str(root))
        spec = importlib.util.spec_from_file_location('native_affiliate_render', root / 'affiliate_render.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            scene = directory / 'scene.mp4'
            voice = directory / 'voice.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=size=180x320:rate=30:duration=5', '-c:v', 'libx264',
                            '-threads', '1', str(scene)], check=True, capture_output=True, timeout=30)
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'sine=frequency=440:sample_rate=48000:duration=4',
                            str(voice)], check=True, capture_output=True, timeout=30)
            brief = {'voice': 'pt-BR-test', 'caption': 'Synthetic fixture', 'comment_text': 'Not for publication',
                     'scenes': [{'path': str(scene), 'sha256': renderer.sha(scene), 'start': 0, 'end': 5,
                                 'narration': 'Teste local'} for _ in range(4)]}
            brief_path = directory / 'brief.json'
            brief_path.write_text(json.dumps(brief))

            async def voices(*args):
                return [{'path': str(voice), 'duration': 4,
                         'words': [{'text': 'Teste', 'offset': 0, 'duration': 10000000},
                                   {'text': 'local', 'offset': 10000000, 'duration': 10000000}]} for _ in range(4)]

            # This smoke tests assembly only. Production brief and publication
            # contracts have separate tests and are not weakened at runtime.
            with patch.object(renderer, 'synthesize', voices), patch.object(renderer, 'validate_brief'), \
                    patch.object(renderer, 'validate_subtitles'):
                renderer.main(brief_path, directory / 'render')
                renderer.main(brief_path, directory / 'render')
            receipt = json.loads((directory / 'render/render-receipt.json').read_text())
            report = json.loads((directory / 'render/media-preflight.json').read_text())
            self.assertTrue(report['technical_pass'])
            self.assertEqual(receipt['preflight']['video_sha256'], report['sha256'])
            self.assertEqual(receipt['preflight']['visual_approval'], 'not_reviewed')
            self.assertFalse(receipt['published'])


if __name__ == '__main__':
    unittest.main()
