import unittest,threading,json,urllib.request,urllib.error
from unittest.mock import patch
import server

class DeckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close()
    def test_only_current_panel_available(self):
        with urllib.request.urlopen(self.url+'/') as response:self.assertIn('COMMAND DECK',response.read().decode())
        for path in ('/classic','/panel.html','/panel-classic.html'):
            with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(self.url+path)
            self.assertEqual(err.exception.code,404)
    def test_external_webpage_cannot_trigger_local_actions(self):
        request=urllib.request.Request(self.url+'/action',data=json.dumps({'action':'cmd'}).encode(),headers={'Content-Type':'application/json','Origin':'https://other.test'})
        with patch.dict(server.ACTIONS,cmd=lambda:self.fail('Cross-origin action executed')):
            with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(request)
        self.assertEqual(err.exception.code,403)
    def test_calendar_rejects_shell_fragments(self):
        with patch.object(server.subprocess,'run') as call:
            self.assertFalse(server.get_calendar('2026-09-17;whoami')['ok']);call.assert_not_called()
    def test_open_runs_on_the_desktop_and_blocks_other_sites(self):
        import desktop_open
        opened=[]
        body=json.dumps({'url':'https://hermes.example.com/#kanban'}).encode()
        with patch.object(desktop_open.os,'startfile',side_effect=opened.append,create=True):
            with urllib.request.urlopen(urllib.request.Request(self.url+'/open',data=body,headers={'Content-Type':'application/json'})) as response:
                result=json.loads(response.read())
            self.assertTrue(result['ok']);self.assertEqual(opened,['https://hermes.example.com/#kanban'])
            bad=urllib.request.Request(self.url+'/open',data=json.dumps({'url':'file:///C:/Windows/System32/cmd.exe'}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(bad) as response:self.assertFalse(json.loads(response.read())['ok'])
            evil=urllib.request.Request(self.url+'/open',data=body,headers={'Content-Type':'application/json','Origin':'https://other.test'})
            with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(evil)
            self.assertEqual(err.exception.code,403)
        self.assertEqual(len(opened),1)
    def test_open_script_is_served_and_loaded_before_hub(self):
        with urllib.request.urlopen(self.url+'/abrir-local.js') as response:self.assertIn('abrirNoSaitama',response.read().decode())
        with urllib.request.urlopen(self.url+'/') as response:html=response.read().decode()
        self.assertLess(html.index('/abrir-local.js'),html.index('/hub.js'))
    def test_unknown_action_is_an_error(self):
        request=urllib.request.Request(self.url+'/action',data=b'{"action":"missing"}',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(request)
        self.assertEqual(err.exception.code,404)

if __name__=='__main__':unittest.main()
