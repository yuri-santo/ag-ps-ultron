import unittest,types
from unittest.mock import patch
import meeting_controls as m
class ControlTests(unittest.TestCase):
    def test_shutdown_needs_explicit_confirmation(self):
        with patch.object(m.subprocess,'run') as run:
            self.assertFalse(m.power('shutdown')['ok']);run.assert_not_called()
    def test_shutdown_is_delayed_and_can_be_cancelled(self):
        with patch.object(m.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)) as run:
            self.assertTrue(m.power('shutdown',True)['ok']);self.assertIn('30',run.call_args.args[0]);self.assertNotIn('/f',run.call_args.args[0])
            self.assertTrue(m.power('cancel')['ok']);self.assertEqual(run.call_args.args[0],['shutdown.exe','/a'])
    def test_join_only_opens_a_cached_teams_link(self):
        with patch.object(m,'meetings'),patch.object(m.os,'startfile') as opened:
            m._meeting_cache['test']={'join_url':'https://evil.test/action','subject':'Test'}
            self.assertFalse(m.join('test')['ok']);opened.assert_not_called()
            m._meeting_cache['test']['join_url']='https://teams.microsoft.com/l/meetup-join/example'
            self.assertTrue(m.join('test')['ok']);opened.assert_called_once_with('msteams://teams.microsoft.com/l/meetup-join/example')
    def test_join_opens_other_providers_on_the_desktop(self):
        cases={'https://us02web.zoom.us/j/81234567890?pwd=abc':'zoommtg://zoom.us/join?action=join&confno=81234567890&pwd=abc',
               'https://meet.google.com/abc-defg-hij':'https://meet.google.com/abc-defg-hij',
               'https://empresa.webex.com/meet/yuri':'https://empresa.webex.com/meet/yuri'}
        for url,expected in cases.items():
            with self.subTest(url=url),patch.object(m,'meetings'),patch.object(m.os,'startfile') as opened:
                m._meeting_cache['x']={'join_url':url,'subject':'Daily'}
                result=m.join('x')
                self.assertTrue(result['ok']);self.assertEqual(result['opened_on'],'Saitama');opened.assert_called_once_with(expected)
    def test_join_falls_back_to_browser_when_teams_app_is_missing(self):
        def startfile(target):
            if target.startswith('msteams:'):raise OSError('sem app')
        with patch.object(m,'meetings'),patch.object(m.os,'startfile',side_effect=startfile) as opened:
            m._meeting_cache['t']={'join_url':'https://teams.microsoft.com/l/meetup-join/x','subject':'Daily'}
            result=m.join('t')
            self.assertTrue(result['ok']);self.assertEqual(opened.call_args.args[0],'https://teams.microsoft.com/l/meetup-join/x')
    def test_join_rejects_non_web_links(self):
        for url in ('file:///C:/Windows/System32/cmd.exe','javascript:alert(1)','ms-settings:privacy',None):
            with self.subTest(url=url),patch.object(m,'meetings'),patch.object(m.os,'startfile') as opened:
                m._meeting_cache['b']={'join_url':url,'subject':'X'}
                self.assertFalse(m.join('b')['ok']);opened.assert_not_called()
    def test_decline_does_not_send_without_user_click(self):
        with patch.object(m,'remote') as remote:
            self.assertFalse(m.decline('test',False)['ok']);remote.assert_not_called()
if __name__=='__main__':unittest.main()
