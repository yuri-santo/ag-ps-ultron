import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "phoneharness_local.py"


class PhoneHarnessLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("phoneharness_local", SCRIPT)
        cls.launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.launcher)

    def test_operation_commands_rejected_before_subprocess(self):
        for command in ("console", "server", "m0b-probe", "m4-run", "tap", "hello"):
            with self.subTest(command=command), patch.object(self.launcher.subprocess, "run") as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                    self.launcher.main([command])
                self.assertEqual(exc.exception.code, 2)
                run.assert_not_called()

    def test_diagnose_never_calls_subprocess(self):
        with patch.object(self.launcher.subprocess, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(self.launcher.main(["diagnose"]), 0)
            run.assert_not_called()
        self.assertIn('"operations_enabled": false', output.getvalue())

    def test_help_does_not_load_or_execute_upstream(self):
        with patch.object(self.launcher.subprocess, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as exc:
                self.launcher.main(["--help"])
            self.assertEqual(exc.exception.code, 0)
            run.assert_not_called()

    def test_extra_arguments_cannot_reach_upstream(self):
        with patch.object(self.launcher.subprocess, "run") as run:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                self.launcher.main(["upstream-help", "console"])
            self.assertEqual(exc.exception.code, 2)
            run.assert_not_called()

    def test_environment_has_no_inherited_credentials_or_python_hooks(self):
        with patch.dict(self.launcher.os.environ, {
            "OPENAI_API_KEY": "secret-test-only",
            "OPENAI_BASE_URL": "https://example.invalid",
            "PYTHONPATH": "/tmp/untrusted",
            "ADB_SERIAL": "unknown-device",
        }):
            env = self.launcher.offline_environment()
        for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "PYTHONPATH", "ADB_SERIAL"):
            self.assertNotIn(key, env)

    def test_upstream_execution_requires_network_namespace(self):
        with patch.object(self.launcher.shutil, "which", return_value=None):
            with patch.object(self.launcher.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "unshare"):
                    self.launcher.run_offline(["-m", "phoneharness", "--help"])
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
