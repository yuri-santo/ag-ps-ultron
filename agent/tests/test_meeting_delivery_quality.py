import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'meeting'))
import render_report as report
from render_docx import render_docx


def fixture():
    return {
        'session': {'id': 'demo', 'title': 'Project review', 'created': 1789662754,
                    'state': {'meeting': {'organizer': {'name': 'Alex'}}}},
        'transcript_events': [
            {'id': 'very-long-internal-event-id-0001', 'at': 1789663000,
             'channel': 'loopback', 'text': 'We approved the prototype.'},
            {'id': 'very-long-internal-event-id-0002', 'at': 1789663010,
             'channel': 'mic', 'text': 'I will send the prototype.', 'confidence': 'low'}],
        'records': [
            {'kind': 'decision', 'status': 'confirmed', 'text': 'We approved the prototype.',
             'at': 1789663000, 'transcript_ids': ['very-long-internal-event-id-0001']}],
        'sources': [], 'rejected': 3,
    }


class DeliveryQualityTests(unittest.TestCase):
    def test_no_attendance_or_chair_invented_from_invitation(self):
        data = fixture()
        data['transcript_events'] = []
        result = report.build_minutes(data)
        self.assertEqual(result['presidente'], report.NAO_APURADO)
        self.assertEqual(result['organizador'], 'Alex')
        self.assertEqual(result['presentes'], [])

    def test_short_references_resolve_to_original_events_without_mutation(self):
        data = fixture()
        before = copy.deepcopy(data)
        result = report.build_minutes(data)
        self.assertEqual(result['citation_labels']['very-long-internal-event-id-0001'], 'F001')
        self.assertIn('F001', result['transcript'])
        self.assertEqual(data, before)

    def test_quality_reports_rejections_and_low_confidence(self):
        quality = report.build_minutes(fixture())['quality']
        self.assertEqual(quality['rejected'], 3)
        self.assertEqual(quality['low_confidence'], 1)
        self.assertEqual(quality['transcript_events'], 2)

    def test_pdf_starts_with_useful_summary_and_preserves_long_transcript(self):
        import pymupdf
        data = fixture()
        data['transcript_events'][0]['text'] = 'original ' * 1100 + 'END_OF_ORIGINAL'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.pdf'
            report.render(data, path)
            with pymupdf.open(stream=path.read_bytes(), filetype='pdf') as pdf:
                first = pdf[0].get_text()
                whole = '\n'.join(page.get_text() for page in pdf)
            self.assertIn('Resumo executivo', first)
            self.assertIn('We approved the prototype.', first)
            self.assertNotIn('very-long-internal-event-id', first)
            self.assertIn('END_OF_ORIGINAL', whole)
            self.assertNotIn('Nada mais havendo', whole)
            self.assertNotIn('foi presidida por Alex', whole)

    def test_word_contains_summary_quality_and_reference_index(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.docx'
            render_docx(fixture(), path)
            text = '\n'.join(p.text for p in Document(path).paragraphs)
            self.assertIn('Resumo executivo', text)
            self.assertIn('F001', text)
            self.assertIn('very-long-internal-event-id-0001', text)
            self.assertNotIn('Nada mais havendo', text)

    def test_long_title_does_not_overlap_brand_header(self):
        import pymupdf
        data = fixture()
        data['session']['title'] = 'Long meeting title ' * 12
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.pdf'
            report.render(data, path)
            with pymupdf.open(stream=path.read_bytes(), filetype='pdf') as pdf:
                brand = pdf[0].search_for('COMMAND DECK')[0]
                title = pdf[0].search_for('Long meeting title')[0]
                self.assertGreater(title.y0, brand.y1)


if __name__ == '__main__':
    unittest.main()
