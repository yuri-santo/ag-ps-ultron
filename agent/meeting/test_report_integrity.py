import tempfile
import unittest
from pathlib import Path

import pymupdf

from render_report import render


class TranscriptIntegrityTests(unittest.TestCase):
    def test_pdf_preserves_literal_transcript_markers(self):
        lines = ['# literal heading', '**literal emphasis**', '`literal code`',
                 '- literal dash', '* literal star', '<tag> & literal markup']
        data = {
            'session': {'id': 'synthetic', 'title': 'Synthetic meeting'},
            'transcript_events': [
                {'id': 'speech-1', 'at': 1789663000, 'channel': 'loopback',
                 'text': '\n'.join(lines)},
                {'id': 'speech-2', 'at': 1789663002, 'channel': 'loopback',
                 'text': 'original ' * 1100 + 'END_OF_TRANSCRIPT'}],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.pdf'
            render(data, output)
            with pymupdf.open(output) as pdf:
                text = '\n'.join(page.get_text() for page in pdf)
        for line in lines:
            with self.subTest(line=line):
                self.assertTrue(line in text, 'Missing literal transcript line: ' + line)
        self.assertIn('END_OF_TRANSCRIPT', text)


if __name__ == '__main__':
    unittest.main()
