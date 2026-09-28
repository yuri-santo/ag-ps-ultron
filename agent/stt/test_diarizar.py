import sys, unittest
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
