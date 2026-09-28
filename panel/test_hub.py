import unittest,tempfile,pathlib
from unittest.mock import patch
import hub_api as h
class HubTests(unittest.TestCase):
    def test_document_cannot_escape_allowed_root(self):
        with self.assertRaises(ValueError):h.document_path('../.ssh/id_rsa')
        with self.assertRaises(ValueError):h.document_path('C:/Windows/win.ini')
    def test_unknown_operation_never_reaches_ssh(self):
        with patch.object(h.subprocess,'run') as run:
            self.assertFalse(h.dispatch({'action':'shell','command':'anything'})['ok']);run.assert_not_called()
    def test_private_recordings_are_not_in_document_index(self):
        paths=[p['path'] for p in h.documents()['documents']]
        self.assertFalse(any('reunioes-privadas' in x for x in paths))
    def test_no_secret_files_are_documents(self):
        for name in ['.env','token.json','openrouter-user.key']:
            with self.assertRaises(ValueError):h.document_path(name)
if __name__=='__main__':unittest.main()
