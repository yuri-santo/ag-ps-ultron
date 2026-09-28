import unittest
import desktop_open as d


class DesktopOpenTests(unittest.TestCase):
    def setUp(self):
        self.opened = []

    def test_web_links_open_in_the_desktop_browser(self):
        for url in ('https://hermes.example.com/#kanban', 'https://ai.example.com', 'http://192.168.0.10:8123/'):
            result = d.open_url(url, self.opened.append)
            self.assertTrue(result['ok'])
            self.assertEqual((result['opened_on'], result['via']), ('Saitama', 'browser'))
        self.assertEqual(self.opened[0], 'https://hermes.example.com/#kanban')

    def test_meeting_links_prefer_the_installed_app(self):
        self.assertEqual(d.open_url('https://teams.microsoft.com/l/meetup-join/x', self.opened.append)['app'], 'Teams')
        self.assertEqual(self.opened[-1], 'msteams://teams.microsoft.com/l/meetup-join/x')
        self.assertEqual(d.open_url('https://zoom.us/j/1234567890', self.opened.append)['app'], 'Zoom')
        self.assertEqual(self.opened[-1], 'zoommtg://zoom.us/join?action=join&confno=1234567890')

    def test_dangerous_or_local_targets_are_refused(self):
        for url in ('file:///C:/Windows/System32/cmd.exe', 'javascript:alert(1)', 'ms-settings:privacy',
                    'C:\\Windows\\notepad.exe', '\\\\servidor\\share', 'https://user:senha@site.com/',
                    'https://site.com/a b', 'https://site.com/"&calc', 'https://x.com/\n', '', None, 42,
                    'https://x.com/' + 'a' * 5000):
            with self.subTest(url=url):
                self.assertFalse(d.open_url(url, self.opened.append)['ok'])
        self.assertEqual(self.opened, [])

    def test_meeting_button_only_accepts_known_providers(self):
        self.assertFalse(d.open_meeting('https://evil.test/join', self.opened.append)['ok'])
        self.assertFalse(d.open_meeting('https://teams.microsoft.com.evil.test/x', self.opened.append)['ok'])
        self.assertTrue(d.open_meeting('https://meet.google.com/abc-defg-hij', self.opened.append)['ok'])
        self.assertEqual(self.opened, ['https://meet.google.com/abc-defg-hij'])

    def test_failure_reports_error_without_touching_the_phone(self):
        def broken(target):
            raise OSError('sem navegador')
        result = d.open_url('https://example.com', broken)
        self.assertFalse(result['ok'])
        self.assertIn('OSError', result['error'])


if __name__ == '__main__':
    unittest.main()
