import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'meeting'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_report as r

BASE = {'session': {'id': 's1', 'title': 'Reunião', 'created': 1789662754, 'state': {
    'meeting': {'subject': 'Daily', 'start': '2026-09-17T14:00:00-03:00', 'location': 'Microsoft Teams',
                'organizer': {'name': 'Maria'}, 'attendees': ['a@x.com', {'name': 'Beto'}]}}},
    'ended_at': 1789666354, 'transcript': '[17/09 14:02] Reunião — áudio recebido\noi', 'report_text': 'ok',
    'records': [{'kind': 'decision', 'status': 'confirmed', 'text': 'aprovar', 'transcript_ids': ['t1'], 'at': 1789663000},
                {'kind': 'action', 'status': 'confirmed', 'text': 'enviar', 'owner': None, 'deadline': None, 'transcript_ids': ['t2'], 'at': 1789663100},
                {'kind': 'action', 'status': 'revoked', 'text': 'cancelado', 'transcript_ids': ['t3'], 'at': 1789663200}]}


class MinutesTests(unittest.TestCase):
    def test_fields_come_from_the_record(self):
        ata = r.build_minutes(BASE)
        self.assertEqual((ata['titulo'], ata['organizador'], ata['local'], ata['inicio']), ('Daily', 'Maria', 'Microsoft Teams', '14:00'))
        self.assertEqual(ata['presidente'], r.NAO_APURADO)
        self.assertEqual(ata['data'], '17 de setembro de 2026')
        self.assertEqual(ata['convocados'], ['a@x.com', 'Beto'])
        self.assertEqual([x['text'] for x in ata['decisoes']], ['aprovar'])
        self.assertEqual([x['text'] for x in ata['acoes']], ['enviar'])
        self.assertEqual([x['text'] for x in ata['revogadas']], ['cancelado'])
        self.assertTrue(any('áudio da reunião' in x for x in ata['presentes']))

    def test_old_payload_without_meeting_or_records_does_not_invent(self):
        ata = r.build_minutes({'session': {'id': 'x', 'title': 'Reunião', 'created': 1789662754, 'state': {}}})
        self.assertEqual(ata['presidente'], r.NAO_APURADO)
        self.assertEqual(ata['presentes'], [])
        self.assertEqual(ata['convocados'], [])
        self.assertEqual(ata['fim'], r.NAO_APURADO)
        self.assertEqual(ata['decisoes'], [])

    def test_records_fall_back_to_consolidated_state(self):
        data = json.loads(json.dumps(BASE)); recs = data.pop('records')
        data['session']['state']['consolidated'] = {'records': recs, 'rejected': 2}
        ata = r.build_minutes(data)
        self.assertEqual(len(ata['decisoes']), 1); self.assertEqual(ata['rejeitados'], 2)

    def test_pdf_renders_with_hostile_text(self):
        data = json.loads(json.dumps(BASE))
        data['report_text'] = '### <script>x</script>\n- **negrito** & `código`\n' + 'a' * 20000
        data['records'][0]['text'] = '<b>não é html</b> & <font>'
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'ata.pdf'
            r.render(data, out)
            self.assertGreater(out.stat().st_size, 5000)
            self.assertTrue(out.read_bytes().startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()


class DiarizationTests(unittest.TestCase):
    def test_voices_and_labeled_transcript(self):
        data = json.loads(json.dumps(BASE))
        data['speakers'] = {'vozes': 2, 'rotulos': {'t1': 'Participante 2', 'x9': 'Participante 1'}}
        data['transcript_events'] = [{'id': 'm1', 'at': 1789663000, 'channel': 'mic', 'text': 'oi'},
                                     {'id': 'x9', 'at': 1789663005, 'channel': 'loopback', 'text': 'bom dia'},
                                     {'id': 'zz', 'at': 1789663009, 'channel': 'loopback', 'text': '?', 'confidence': 'low'}]
        ata = r.build_minutes(data)
        self.assertTrue(any('2 voz(es)' in x for x in ata['presentes']))
        self.assertIn('Participante 1 (áudio da reunião)\nbom dia', ata['transcript'])
        self.assertIn('Yuri — microfone\noi', ata['transcript'])
        self.assertIn('Reunião — áudio recebido\n[Baixa confiança', ata['transcript'])
        self.assertEqual(r.quem_falou(data['records'][0], ata['rotulos']), 'Participante 2')
        with tempfile.TemporaryDirectory() as d:
            r.render(data, Path(d) / 'a.pdf')
