"""Regression coverage for keeping review scaffolding out of durable history."""
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from patch_review_persistence import patch_file
except ModuleNotFoundError:
    patch_file = None


FLAGS = '''_EPHEMERAL_SCAFFOLDING_FLAGS = (
    "_empty_recovery_synthetic",
    "_empty_terminal_sentinel",
    "_thinking_prefill",
    "_verification_stop_synthetic",  # verify-on-stop nudge; the assistant candidate itself is NOT synthetic
    "_pre_verify_synthetic",
    "_kanban_stop_synthetic",  # kanban worker stop-guard
    "_dropped_toolcall_nudge",  # internal retry instruction; must not replay as user context
)
'''
ADDITION = '    "_review_stop_synthetic",  # Ultron: rejected candidate and internal reviewer nudge\n'
GUARD = '''def _is_ephemeral_scaffolding(msg: Any) -> bool:
    """True when ``msg`` is internal recovery scaffolding that must never reach the durable transcript."""
    return isinstance(msg, dict) and any(msg.get(flag) for flag in _EPHEMERAL_SCAFFOLDING_FLAGS)
'''
COLLECT = '''def collect(msg):
    for msg in [msg]:
        if not isinstance(msg, dict) or _is_ephemeral_scaffolding(msg) or msg.get(_DB_PERSISTED_MARKER):
            continue
'''
SOURCE = ('from typing import Any\n_DB_PERSISTED_MARKER = "_db_persisted"\n'
          + FLAGS + '\n' + GUARD + '\n' + COLLECT)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(patch_file, 'review persistence patcher is not implemented')

    def test_preserves_all_other_bytes_and_makes_private_backup(self):
        for eol, bom in ((b'\n', b''), (b'\r\n', b'\xef\xbb\xbf')):
            with self.subTest(eol=eol, bom=bom), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / 'session_persistence.py'
                original = bom + SOURCE.encode().replace(b'\n', eol)
                target.write_bytes(original)
                target.chmod(0o640)
                self.assertTrue(patch_file(target))
                expected = original.replace(
                    FLAGS.encode().replace(b'\n', eol),
                    (FLAGS[:-2] + ADDITION + ')\n').encode().replace(b'\n', eol), 1)
                self.assertEqual(target.read_bytes(), expected)
                backups = list(Path(tmp).glob('session_persistence.py.bak-ultron-review-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), original)
                if os.name == 'posix':
                    self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
                self.assertFalse(patch_file(target))
                self.assertEqual(target.read_bytes(), expected)
                self.assertEqual(len(list(Path(tmp).glob('*.bak-ultron-review-*'))), 1)

    def test_rejects_unknown_ambiguous_or_partially_patched_sources(self):
        variants = [
            SOURCE.replace('"_pre_verify_synthetic",', '"_new_upstream_flag",'),
            SOURCE + '\n' + FLAGS,
            SOURCE + '\n# _review_stop_synthetic\n',
            SOURCE.replace('any(msg.get(flag)', 'all(msg.get(flag)'),
            SOURCE.replace(' or _is_ephemeral_scaffolding(msg)', ''),
        ]
        for source in variants:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / 'session_persistence.py'
                original = source.encode()
                target.write_bytes(original)
                with self.assertRaisesRegex(RuntimeError, 'upstream_persistence_changed'):
                    patch_file(target)
                self.assertEqual(target.read_bytes(), original)
                self.assertEqual(list(Path(tmp).glob('*.bak-ultron-review-*')), [])

    def test_rejects_wrong_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'another_file.py'
            target.write_text(SOURCE)
            with self.assertRaisesRegex(ValueError, 'unexpected_target'):
                patch_file(target)

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlink behavior')
    def test_rejects_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            actual = Path(tmp) / 'actual.py'
            actual.write_text(SOURCE)
            target = Path(tmp) / 'session_persistence.py'
            target.symlink_to(actual)
            with self.assertRaisesRegex(ValueError, 'unexpected_target'):
                patch_file(target)
            self.assertEqual(actual.read_text(), SOURCE)

    def test_failed_replacement_keeps_original_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'session_persistence.py'
            original = SOURCE.encode()
            target.write_bytes(original)
            with patch('patch_review_persistence.os.replace', side_effect=OSError('replace failed')):
                with self.assertRaisesRegex(OSError, 'replace failed'):
                    patch_file(target)
            self.assertEqual(target.read_bytes(), original)
            backups = list(Path(tmp).glob('*.bak-ultron-review-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             sorted([target.name, backups[0].name]))

    def test_only_truthy_review_scaffolding_is_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'session_persistence.py'
            target.write_text(SOURCE)
            patch_file(target)
            namespace = {}
            exec(compile(target.read_bytes(), str(target), 'exec'), namespace)
            is_ephemeral = namespace['_is_ephemeral_scaffolding']
            for role in ('user', 'assistant'):
                self.assertTrue(is_ephemeral({'role': role, '_review_stop_synthetic': True}))
            self.assertFalse(is_ephemeral({'role': 'assistant', 'content': 'Approved answer'}))
            self.assertFalse(is_ephemeral({'role': 'assistant', '_review_stop_synthetic': False}))
            self.assertFalse(is_ephemeral({'role': 'user', '_db_persisted': True, '_row_id': 42}))
            self.assertTrue(is_ephemeral({'role': 'user', '_kanban_stop_synthetic': True}))


class HermesIntegrationTests(unittest.TestCase):
    def test_real_collector_and_database_keep_only_real_user_and_approved_answer(self):
        self.assertIsNotNone(patch_file, 'review persistence patcher is not implemented')
        try:
            from agent import session_persistence as installed
            from hermes_state import SessionDB
        except ImportError:
            self.skipTest('Hermes runtime is not installed')
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'session_persistence.py'
            shutil.copyfile(installed.__file__, target)
            patch_file(target)
            spec = importlib.util.spec_from_file_location('_ultron_test_persistence', target)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            messages = [
                {'role': 'user', 'content': 'ta ai ?'},
                {'role': 'assistant', 'content': 'Rejected candidate', '_review_stop_synthetic': True},
                {'role': 'user', 'content': 'Internal reviewer note', '_review_stop_synthetic': True},
                {'role': 'assistant', 'content': 'Estou aqui. Pode falar.'},
            ]
            database = SessionDB(db_path=Path(tmp) / 'state.db')
            try:
                database.create_session(session_id='isolated-review-test', source='test')
                agent = SimpleNamespace(session_id='isolated-review-test', _last_flushed_db_idx=0,
                                        _session_db=database)
                rows, originals = module._db_flush_collect(agent, messages, None)
                module._db_flush_write(agent, rows, originals, messages)
                persisted = database.get_messages('isolated-review-test')
                self.assertEqual([(m['role'], m['content']) for m in persisted],
                                 [('user', 'ta ai ?'), ('assistant', 'Estou aqui. Pode falar.')])
                self.assertTrue(messages[0]['_db_persisted'])
                self.assertTrue(messages[3]['_db_persisted'])
                self.assertNotIn('_db_persisted', messages[1])
                self.assertNotIn('_db_persisted', messages[2])
                rows, _ = module._db_flush_collect(agent, messages, None)
                self.assertEqual(rows, [])
            finally:
                database.close()


if __name__ == '__main__':
    unittest.main()
