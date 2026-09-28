import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deploy
import deploy_lab


SOURCE = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name) / 'hermes'
        self.home.mkdir()
        (self.home / 'config.yaml').write_text(yaml.safe_dump({
            'model': {'default': 'test-only'},
            'platform_toolsets': {'cli': ['memory']},
        }), encoding='utf-8')

    def test_lab_stage_installs_plugin_from_published_repository(self):
        deploy_lab.Installer(self.home, SOURCE).run('stage')
        installed = self.home / 'plugins' / 'ultron_lab'
        self.assertEqual(
            (installed / '__init__.py').read_bytes(),
            (SOURCE / 'plugins' / 'ultron_lab' / '__init__.py').read_bytes(),
        )
        self.assertTrue((self.home / 'skills' / 'ultron-lab' / 'homelab-ops' / 'SKILL.md').is_file())

    def test_team_stage_and_activate_resolve_published_sources(self):
        for name in ('bigode', 'thor', 'hercules'):
            profile = self.home / 'profiles' / name
            profile.mkdir(parents=True)
            (profile / 'SOUL.md').write_text('Synthetic fixture.', encoding='utf-8')
            (profile / 'config.yaml').write_text('model: test-only\n', encoding='utf-8')
        (self.home / 'SOUL.md').write_text('Synthetic orchestrator.', encoding='utf-8')
        meeting = self.home / 'plugins' / 'meeting_copilot'
        meeting.mkdir(parents=True)
        (meeting / '__init__.py').write_text('# meeting_specialist_unavailable\n', encoding='utf-8')

        def isolated_path(value):
            return self.home if str(value) == '/root/.hermes' else Path(value)

        with patch.object(deploy, 'Path', side_effect=isolated_path), contextlib.redirect_stdout(io.StringIO()):
            with patch('sys.argv', ['deploy.py', 'stage']):
                deploy.main()
            installed = self.home / 'plugins' / 'ultron_team'
            self.assertEqual(
                (installed / 'personality.md').read_bytes(),
                (SOURCE / 'plugins' / 'ultron_team' / 'personality.md').read_bytes(),
            )
            with patch('sys.argv', ['deploy.py', 'activate']):
                deploy.main()
        self.assertIn(deploy.START, (self.home / 'SOUL.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
