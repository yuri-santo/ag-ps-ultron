"""The Money skill deployment never changes persona or other profiles."""
import tempfile
import unittest
from pathlib import Path

from install_marketingskills import SKILLS, install


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        (self.bundle / 'LICENSE').write_text('MIT License\n')
        for name in SKILLS:
            source = self.bundle / name
            (source / 'references').mkdir(parents=True)
            (source / 'SKILL.md').write_text(
                f'---\nname: {name}\ndescription: "upstream"\n---\n\n# {name}\n\nOriginal guidance.\n')
            (source / 'references' / 'guide.md').write_text('Original reference.\n')
            (source / 'run.py').write_text('raise RuntimeError("never copy code")\n')
        self.profile = self.root / 'profiles' / 'money'
        self.profile.mkdir(parents=True)
        (self.profile / 'SOUL.md').write_text('Money persona unchanged.\n')

    def test_installs_curated_reference_only_skills_for_money(self):
        result = install(self.profile, self.bundle)
        self.assertEqual(set(result['installed']), set(SKILLS))
        self.assertEqual((self.profile / 'SOUL.md').read_text(), 'Money persona unchanged.\n')
        for name in SKILLS:
            skill = self.profile / 'skills' / 'marketing' / name
            content = (skill / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('Original guidance.', content)
            self.assertIn('autorização explícita', content)
            self.assertTrue((skill / 'references' / 'guide.md').is_file())
            self.assertFalse((skill / 'run.py').exists())
            self.assertTrue((skill / '.ultron-marketingskills-managed').is_file())
        self.assertTrue((self.profile / 'skills' / 'marketing' / 'LICENSE').is_file())

    def test_rejects_other_profile_and_unowned_skill(self):
        with self.assertRaises(ValueError):
            install(self.root / 'profiles' / 'ultron', self.bundle)
        target = self.profile / 'skills' / 'marketing' / SKILLS[0]
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('personal skill')
        with self.assertRaises(RuntimeError):
            install(self.profile, self.bundle)
        self.assertEqual((target / 'SKILL.md').read_text(), 'personal skill')

    def test_second_install_is_idempotent_and_makes_backup(self):
        install(self.profile, self.bundle)
        first = (self.profile / 'skills' / 'marketing' / SKILLS[0] / 'SKILL.md').read_bytes()
        result = install(self.profile, self.bundle)
        self.assertEqual((self.profile / 'skills' / 'marketing' / SKILLS[0] / 'SKILL.md').read_bytes(), first)
        self.assertTrue(result['backup'])


if __name__ == '__main__':
    unittest.main()
