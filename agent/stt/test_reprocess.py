import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

import reprocess as r


class ReprocessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / 'audio'
        self.audio.mkdir()
        self.events = self.root / 'events.jsonl'
        self.output = self.root / 'result'
        self.durations = {}

    def add_audio(self, name, duration=4):
        path = self.audio / name
        path.write_bytes(b'synthetic-audio')
        self.durations[name] = duration
        return path

    def write_events(self, events):
        self.events.write_text('\n'.join(json.dumps(ev) for ev in events), encoding='utf-8')

    def event(self, name, confidence='low', kind='transcript'):
        return {'id': name + ':0', 'kind': kind, 'audio_file': name,
                'confidence': confidence, 'text': 'original'}

    def execute(self, recognizer=None, **kwargs):
        if recognizer is None:
            recognizer = Mock(return_value=[SimpleNamespace(
                avg_logprob=-0.2, no_speech_prob=0.01, compression_ratio=1.1,
                words=[SimpleNamespace(word=' new', start=0, end=1, probability=0.9)])])
        return r.run(self.audio, self.events, self.output, recognizer=recognizer,
                     audio_info=lambda p: self.durations[p.name],
                     audio_reader=lambda p, start, duration: [0.0] * round(duration * r.RATE),
                     **kwargs)

    def candidates(self):
        return [json.loads(line) for line in (self.output / 'candidates.jsonl').read_text().splitlines()]

    def test_selects_low_confidence_transcripts_only_and_preserves_sources(self):
        names = ['100_mic_a.flac', '104_mic_b.flac', '108_loopback_c.flac']
        for name in names:
            self.add_audio(name)
        self.write_events([self.event(names[0]), self.event(names[1], 'high'),
                           self.event(names[2], kind='analysis')])
        before = self.events.read_bytes()
        manifest = self.execute()
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['eligible_audio'], 1)
        self.assertEqual(len(self.candidates()), 1)
        self.assertEqual(self.events.read_bytes(), before)
        candidate = self.candidates()[0]
        self.assertEqual(candidate['source_event_ids'], [names[0] + ':0'])
        self.assertNotEqual(candidate['id'], names[0] + ':0')
        self.assertTrue(candidate['review_required'])
        self.assertNotIn('wer', manifest['metrics'])

    def test_context_same_channel_contiguous_and_bounded_to_two_seconds(self):
        chunks = [r.Chunk(Path('a'), 100, 'mic', 4), r.Chunk(Path('b'), 104.1, 'mic', 4),
                  r.Chunk(Path('c'), 108.2, 'mic', 4), r.Chunk(Path('d'), 100, 'loopback', 20)]
        pieces, start, end = r.context_window(chunks[1], chunks)
        self.assertAlmostEqual(start, 102.1)
        self.assertAlmostEqual(end, 110.1)
        self.assertEqual([piece[0].path.name for piece in pieces], ['a', 'b', 'c'])

    def test_long_gaps_never_become_context(self):
        chunks = [r.Chunk(Path('a'), 100, 'mic', 4), r.Chunk(Path('b'), 104.151, 'mic', 4),
                  r.Chunk(Path('c'), 109, 'mic', 4)]
        pieces, start, end = r.context_window(chunks[1], chunks)
        self.assertEqual([piece[0].path.name for piece in pieces], ['b'])
        self.assertEqual((start, end), (104.151, 108.151))

    def test_words_are_selected_by_midpoint_and_timestamps_clamped(self):
        before = '100_mic_a.flac'
        central = '104_mic_b.flac'
        for name in [before, central]:
            self.add_audio(name)
        self.write_events([self.event(central)])
        words = [SimpleNamespace(word=text, start=start, end=end, probability=.8)
                 for text, start, end in [(' skip', 0, 1), (' first', 1.5, 2.5),
                                          (' last', 5, 6.5), (' outside', 5.5, 6.5)]]
        recognizer = Mock(return_value=[SimpleNamespace(words=words, avg_logprob=-.3)])
        self.execute(recognizer)
        candidate = self.candidates()[0]
        self.assertEqual(candidate['text'], 'first last')
        self.assertEqual(candidate['words'][0]['start'], 104)
        self.assertEqual(candidate['words'][-1]['end'], 108)

    def test_checkpoint_skips_completed_and_invalidates_content_and_config(self):
        name = '100_mic_a.flac'
        path = self.add_audio(name)
        self.write_events([self.event(name)])
        recognizer = Mock(return_value=[])
        self.execute(recognizer)
        self.execute(recognizer)
        self.assertEqual(recognizer.call_count, 1)
        self.execute(recognizer, model='medium')
        self.assertEqual(recognizer.call_count, 2)
        path.write_bytes(b'changed-audio')
        self.execute(recognizer, model='medium')
        self.assertEqual(recognizer.call_count, 3)

    def test_failure_keeps_original_audio_and_completed_candidate(self):
        names = ['100_mic_a.flac', '200_mic_b.flac']
        for name in names:
            self.add_audio(name)
        self.write_events([self.event(name) for name in names])
        recognizer = Mock(side_effect=[[], RuntimeError('audio failed')])
        manifest = self.execute(recognizer)
        self.assertEqual(manifest['status'], 'partial')
        self.assertEqual(len(self.candidates()), 1)
        self.assertEqual(len(manifest['failures']), 1)
        self.assertTrue(all((self.audio / name).read_bytes() == b'synthetic-audio' for name in names))
        self.execute(Mock(return_value=[]))
        self.assertEqual(len(self.candidates()), 2)

    def test_limit_is_partial_and_resume_keeps_previously_completed_files(self):
        names = ['100_mic_a.flac', '200_mic_b.flac']
        for name in names:
            self.add_audio(name)
        self.write_events([self.event(name) for name in names])
        self.assertEqual(self.execute(limit=1)['status'], 'partial')
        self.assertEqual(self.execute()['status'], 'complete')
        self.assertEqual(len(self.candidates()), 2)

    def test_all_selection_includes_high_confidence(self):
        name = '100_mic_a.flac'
        self.add_audio(name)
        self.write_events([self.event(name, 'high')])
        self.assertEqual(self.execute(selection='all')['eligible_audio'], 1)

    def test_traversal_and_absolute_references_are_rejected(self):
        for reference in ['../outside.flac', '..\\outside.flac', '/tmp/out.flac', 'C:\\outside.flac']:
            with self.subTest(reference=reference):
                self.write_events([self.event(reference)])
                with self.assertRaises(ValueError):
                    self.execute()

    def test_glossary_is_limited_and_missing_local_models_do_not_download(self):
        glossary = self.root / 'terms.txt'
        glossary.write_text('a' * 1001)
        name = '100_mic_a.flac'
        self.add_audio(name)
        self.write_events([self.event(name)])
        with self.assertRaises(ValueError):
            self.execute(glossary=glossary)
        factory = Mock(return_value=Mock())
        r.WhisperRecognizer('small', 4, '', False, model_factory=factory)
        self.assertTrue(factory.call_args.kwargs['local_files_only'])

    def test_resume_limit_applies_to_new_work_and_keeps_cached_results(self):
        names = ['100_mic_a.flac', '200_mic_b.flac']
        for name in names:
            self.add_audio(name)
        self.write_events([self.event(name) for name in names])
        recognizer = Mock(return_value=[])
        self.execute(recognizer, limit=1)
        manifest = self.execute(recognizer, limit=1)
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['cache_hits'], 1)
        self.assertEqual(recognizer.call_count, 2)
        self.assertEqual(len(self.candidates()), 2)

    def test_changed_context_and_local_model_invalidate_checkpoints(self):
        previous = self.add_audio('100_mic_a.flac')
        self.add_audio('104_mic_b.flac')
        self.write_events([self.event('104_mic_b.flac')])
        model = self.root / 'model'
        model.mkdir()
        weights = model / 'model.bin'
        weights.write_bytes(b'v1')
        recognizer = Mock(return_value=[])
        self.execute(recognizer, model=str(model))
        previous.write_bytes(b'updated-context')
        self.execute(recognizer, model=str(model))
        weights.write_bytes(b'v2')
        self.execute(recognizer, model=str(model))
        self.assertEqual(recognizer.call_count, 3)

    def test_gap_preserves_time_with_silence_and_does_not_mix_channels(self):
        chunks = [r.Chunk(Path('a'), 100, 'mic', 4), r.Chunk(Path('b'), 104.1, 'mic', 4)]
        pieces, start, end = r.context_window(chunks[1], chunks)
        samples = r._assemble(pieces, start, end,
                              lambda path, begin, duration: [1.0] * round(duration * r.RATE))
        self.assertEqual(len(samples), round((end - start) * r.RATE))
        self.assertEqual(samples[round((104.05 - start) * r.RATE)], 0)
        self.assertEqual(samples[round((104.1 - start) * r.RATE)], 1)

    def test_all_failures_produce_failed_manifest_and_nonempty_error(self):
        name = '100_mic_a.flac'
        self.add_audio(name)
        self.write_events([self.event(name)])
        manifest = self.execute(Mock(side_effect=RuntimeError('decode failed')))
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('decode failed', manifest['failures'][0]['error'])
        self.assertEqual(self.candidates(), [])

    def test_empty_selection_does_not_load_model(self):
        self.write_events([])
        with patch.object(r, 'WhisperRecognizer') as factory:
            self.assertEqual(self.execute()['status'], 'complete')
        factory.assert_not_called()

    def test_broken_checkpoint_is_recomputed(self):
        name = '100_mic_a.flac'
        self.add_audio(name)
        self.write_events([self.event(name)])
        recognizer = Mock(return_value=[])
        self.execute(recognizer)
        checkpoint = next((self.output / 'checkpoints').glob('*.json'))
        checkpoint.write_text('{truncated', encoding='utf-8')
        self.execute(recognizer)
        self.assertEqual(recognizer.call_count, 2)

    def test_empty_words_remain_explicit_review_candidates(self):
        name = '100_mic_a.flac'
        self.add_audio(name)
        self.write_events([self.event(name)])
        self.execute(Mock(return_value=[SimpleNamespace(text='Unaligned hallucination', words=None)]))
        candidate = self.candidates()[0]
        self.assertEqual(candidate['text'], '')
        self.assertEqual(candidate['warnings'], ['no_timestamped_words_in_central_window'])

    def test_atomic_failure_preserves_existing_output(self):
        path = self.root / 'existing.json'
        path.write_text('original', encoding='utf-8')
        with patch.object(r.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                r._atomic(path, 'replacement')
        self.assertEqual(path.read_text(encoding='utf-8'), 'original')
        self.assertFalse(list(self.root.glob('.existing.json*')))


if __name__ == '__main__':
    unittest.main()
