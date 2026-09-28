import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import diarizar as d


class DiarizarTests(unittest.TestCase):
    def test_map_back_to_absolute_time(self):
        mapa = [(0.0, 1000.0, 20.0), (20.3, 1030.0, 20.0)]
        self.assertEqual(d.para_absoluto(5.0, mapa), 1005.0)
        self.assertEqual(d.para_absoluto(25.3, mapa), 1035.0)
        self.assertIsNone(d.para_absoluto(20.1, mapa))

    def test_labels_follow_first_appearance_and_ignore_mic(self):
        segs = [(1000, 1010, 3), (1010, 1020, 0), (1020, 1030, 3)]
        events = [{'id': 'a', 'at': 1001, 'end': 1008, 'channel': 'loopback'},
                  {'id': 'b', 'at': 1012, 'end': 1019, 'channel': 'loopback'},
                  {'id': 'c', 'at': 1021, 'end': 1025, 'channel': 'loopback'},
                  {'id': 'm', 'at': 1001, 'end': 1005, 'channel': 'mic'}]
        rot, n = d.atribuir(segs, events)
        self.assertEqual(n, 2)
        self.assertEqual(rot, {'a': 'Participante 1', 'b': 'Participante 2', 'c': 'Participante 1'})

    def test_no_audio(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(d.diarizar_sessao(t, [])['motivo'], 'sem_audio_da_reuniao')

    def test_segment_ending_in_padding_preserves_recorded_speech(self):
        out = self.run_session([(8, 10.1, 0)], [
            {'id': 'a', 'at': 1008, 'end': 1010, 'channel': 'loopback'}])
        self.assertEqual(out['rotulos'], {'a': 'Participante 1'})
        self.assertEqual(out['segmentos'], 1)

    def test_segment_crossing_chunks_does_not_fill_absolute_gap(self):
        out = self.run_session([(8, 12, 0)], [
            {'id': 'a', 'at': 1008, 'end': 1010, 'channel': 'loopback'},
            {'id': 'gap', 'at': 1012, 'end': 1020, 'channel': 'loopback'},
            {'id': 'b', 'at': 1030, 'end': 1031, 'channel': 'loopback'}])
        self.assertEqual(out['rotulos'], {'a': 'Participante 1', 'b': 'Participante 1'})
        self.assertEqual(out['segmentos'], 2)

    def run_session(self, segments, events):
        sd = Mock()
        sd.process.return_value.sort_by_start_time.return_value = [
            SimpleNamespace(start=start, end=end, speaker=speaker)
            for start, end, speaker in segments]
        timeline = ([], [(0, 1000, 10), (10.3, 1030, 10)])
        with patch.object(Path, 'glob', return_value=[Path('1000_loopback_0.flac')]), \
                patch.object(d, 'montar_linha_do_tempo', return_value=timeline), \
                patch.object(d, 'diarizador', return_value=sd):
            return d.diarizar_sessao('unused', events)

    def test_ambiguous_or_insufficient_evidence_has_no_label(self):
        event = {'id': 'a', 'at': 1000, 'end': 1010, 'channel': 'loopback'}
        cases = [
            [(1000, 1005, 0), (1005, 1010, 1)],
            [(1000, 1006, 0), (1006, 1010, 1)],
            [(1000, 1010, 0), (1000, 1010, 1)],
            [(1000, 1000.1, 0)],
            [(1000, 1004, 0)],
        ]
        for segments in cases:
            with self.subTest(segments=segments):
                self.assertEqual(d.atribuir(segments, [event]), ({}, 0))

    def test_same_speaker_evidence_is_aggregated(self):
        event = {'id': 'a', 'at': 1000, 'end': 1010, 'channel': 'loopback'}
        segments = [(1000, 1002, 1), (1002, 1004, 1), (1004, 1006, 1),
                    (1006, 1007, 1), (1007, 1010, 0)]
        self.assertEqual(d.atribuir(segments, [event]), ({'a': 'Participante 1'}, 1))
        # A second clear event proves the first label belonged to speaker 1.
        later = {'id': 'b', 'at': 1010, 'end': 1012, 'channel': 'loopback'}
        segments.append((1010, 1012, 1))
        self.assertEqual(d.atribuir(segments, [event, later])[0],
                         {'a': 'Participante 1', 'b': 'Participante 1'})

    def test_duplicate_segments_do_not_inflate_speaker_evidence(self):
        event = {'id': 'a', 'at': 1000, 'end': 1010, 'channel': 'loopback'}
        segments = [(1000, 1004, 0)] * 4 + [(1004, 1010, 1)]
        self.assertEqual(d.atribuir(segments, [event]), ({}, 0))


if __name__ == '__main__':
    unittest.main()
