import unittest,tempfile,pathlib
from unittest.mock import patch
import hub_api,hub_media
class MediaTests(unittest.TestCase):
    def test_multiple_roots_same_filename_remain_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            first=pathlib.Path(folder,'old');second=pathlib.Path(folder,'new');first.mkdir();second.mkdir()
            (first/'video.mp4').write_bytes(b'old');(second/'video.mp4').write_bytes(b'new')
            with patch.object(hub_media,'ROOT',first),patch.object(hub_media,'EXTRA_ROOTS',(second,)):
                videos=hub_media.catalog()['videos'];self.assertEqual(len(videos),2)
                self.assertEqual(len({v['id'] for v in videos}),2)
                self.assertEqual({hub_media.resolve(v['id']).read_bytes() for v in videos},{b'old',b'new'})
    def test_ranges(self):
        self.assertEqual(hub_media.bounds('bytes=0-99',1000),(0,99,True))
        self.assertEqual(hub_media.bounds('bytes=-50',1000),(950,999,True))
        for value in ['bytes=1000-','bytes=4-1','bytes=0-1,3-5','garbage']:
            with self.assertRaises(ValueError):hub_media.bounds(value,1000)
    def test_no_arbitrary_file_access(self):
        with self.assertRaises(ValueError):hub_media.resolve('../server.py')
    def test_documents_bounded_searchable(self):
        with tempfile.TemporaryDirectory() as root,patch.object(hub_api,'ROOT',pathlib.Path(root)):
            for i in range(75):pathlib.Path(root,f'guia-{i:02}.md').write_text('teste')
            first=hub_api.documents();second=hub_api.documents(offset=60)
            self.assertEqual(len(first['documents']),60);self.assertEqual(len(second['documents']),15)
            self.assertEqual(hub_api.documents(query='guia-74')['total'],1)
if __name__=='__main__':unittest.main()
