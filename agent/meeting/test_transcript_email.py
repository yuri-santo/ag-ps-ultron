import unittest
from patch_transcript_email import transform


class MailMigrationTests(unittest.TestCase):
    def test_adds_transcript_preserving_existing_attachments(self):
        source = "attachments = [pdf_path] + [x for x in optional if x.is_file()]"
        changed = transform(source)
        self.assertIn('[pdf_path, transcript_path]', changed)
        self.assertIn('[x for x in optional if x.is_file()]', changed)
        self.assertEqual(transform(changed), changed)

    def test_refuses_unknown_or_ambiguous_version(self):
        for text in ['attachments=[]', '[pdf_path] + [x for x in a]\n[pdf_path] + [x for x in b]']:
            with self.assertRaises(ValueError):
                transform(text)


if __name__ == '__main__':
    unittest.main()
