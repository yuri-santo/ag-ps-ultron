"""Technical preflight contract; integration fixtures require ffmpeg/ffprobe."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("media_preflight.py")
if MODULE_PATH.exists():
    SPEC = importlib.util.spec_from_file_location("media_preflight", MODULE_PATH)
    media = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(media)
else:
    media = None


def valid_probe():
    return {"format": {"duration": "4.0", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [{"codec_type": "video", "width": 1080, "height": 1920,
                         "sample_aspect_ratio": "1:1", "codec_name": "h264"},
                        {"codec_type": "audio", "codec_name": "aac",
                         "channels": 2, "sample_rate": "48000"}]}


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(media, "Implement the missing media_preflight module")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "clip.mp4"
        self.source.write_bytes(b"test media bytes")
        self.probe = valid_probe()
        self.decode_code = 0
        self.decode_output = "frame=120\nprogress=end\n"
        self.diagnostics = ""

    def runner(self, args, **kwargs):
        self.assertFalse(kwargs.get("shell", False))
        self.assertGreater(kwargs["timeout"], 0)
        self.assertLessEqual(kwargs["timeout"], 3600)
        self.assertEqual(args[args.index("-protocol_whitelist") + 1], "file")
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(args, 0, json.dumps(self.probe), "")
        if "-progress" in args:
            return subprocess.CompletedProcess(args, self.decode_code, self.decode_output,
                                               "decode error" if self.decode_code else "")
        return subprocess.CompletedProcess(args, 0, "", self.diagnostics)

    def run_check(self, **kwargs):
        with patch.object(media.subprocess, "run", side_effect=self.runner):
            return media.run_preflight(self.source, **kwargs)

    def test_valid_evidence_is_not_visual_approval(self):
        report = self.run_check(expected_duration=4)
        self.assertTrue(report["technical_pass"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["visual_approval"], "not_reviewed")
        self.assertEqual(report["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_missing_audio_fails(self):
        self.probe["streams"].pop()
        self.assertFalse(self.run_check()["technical_pass"])

    def test_landscape_and_unknown_aspect_fail(self):
        for width in (1920, None, True):
            self.probe["streams"][0]["width"] = width
            self.assertFalse(self.run_check()["technical_pass"])

    def test_anamorphic_and_rotation_affect_display_aspect(self):
        self.probe["streams"][0]["sample_aspect_ratio"] = "2:1"
        self.assertFalse(self.run_check()["technical_pass"])
        self.probe = valid_probe()
        self.probe["streams"][0]["side_data_list"] = [{"rotation": 90}]
        self.assertFalse(self.run_check()["technical_pass"])

    def test_malformed_probe_and_duration_fail(self):
        for probe in (None, [], {}, {"streams": [None]},
                      {"streams": "unknown", "format": {"duration": 4}}):
            self.probe = probe
            self.assertFalse(self.run_check()["technical_pass"])
        for duration in (None, "nan", "inf", "0", "-1", True):
            self.probe = valid_probe()
            self.probe["format"]["duration"] = duration
            self.assertFalse(self.run_check()["technical_pass"])

    def test_malformed_json_fails(self):
        with patch.object(media.subprocess, "run", return_value=
                          subprocess.CompletedProcess([], 0, "{bad", "")):
            self.assertFalse(media.run_preflight(self.source)["technical_pass"])

    def test_corrupt_or_incomplete_decode_fails(self):
        self.decode_code = 1
        self.assertFalse(self.run_check()["technical_pass"])
        self.decode_code = 0
        for output in ("", "frame=0\nprogress=end\n", "frame=1\nprogress=continue\n"):
            self.decode_output = output
            self.assertFalse(self.run_check()["technical_pass"])

    def test_expected_duration_tolerance(self):
        self.assertFalse(self.run_check(expected_duration=10)["technical_pass"])
        self.assertTrue(self.run_check(expected_duration=4.3)["technical_pass"])

    def test_invalid_settings_rejected(self):
        for kwargs in ({"expected_duration": float("nan")}, {"duration_tolerance": -1},
                       {"probe_timeout": 0}, {"decode_timeout": 3601}):
            with self.assertRaises(ValueError):
                self.run_check(**kwargs)

    def test_unavailable_tool_or_timeout_fails_closed(self):
        for error in (FileNotFoundError("ffprobe unavailable"),
                      subprocess.TimeoutExpired("ffprobe", 30)):
            with patch.object(media.subprocess, "run", side_effect=error):
                self.assertFalse(media.run_preflight(self.source)["technical_pass"])

    def test_diagnostic_failure_fails_closed(self):
        def runner(args, **kwargs):
            if "-vf" in args:
                return subprocess.CompletedProcess(args, 1, "", "filter unavailable")
            return self.runner(args, **kwargs)
        with patch.object(media.subprocess, "run", side_effect=runner):
            self.assertFalse(media.run_preflight(self.source)["technical_pass"])

    def test_silence_black_and_freeze_are_contextual_warnings(self):
        self.diagnostics = ("[silencedetect] silence_start: 0\n"
                            "[blackdetect] black_start:0 black_end:2 black_duration:2\n"
                            "[freezedetect] lavfi.freezedetect.freeze_start: 0\n")
        report = self.run_check()
        self.assertTrue(report["technical_pass"])
        self.assertEqual({warning["code"] for warning in report["warnings"]},
                         {"silence", "black", "freeze"})

    def test_source_changed_during_check_fails(self):
        def runner(args, **kwargs):
            result = self.runner(args, **kwargs)
            if "-vf" in args:
                self.source.write_bytes(b"changed")
            return result
        with patch.object(media.subprocess, "run", side_effect=runner):
            self.assertFalse(media.run_preflight(self.source)["technical_pass"])

    def test_missing_source_is_machine_readable_failure(self):
        self.source.unlink()
        self.assertFalse(media.run_preflight(self.source)["technical_pass"])

    def test_atomic_report_and_source_overwrite_protection(self):
        report = self.run_check()
        target = Path(self.tmp.name) / "evidence.json"
        media.write_report(report, target)
        self.assertEqual(json.loads(target.read_text())["sha256"], report["sha256"])
        self.assertEqual(list(Path(self.tmp.name).glob("*.tmp")), [])
        with self.assertRaises(ValueError):
            media.write_report(report, self.source)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
class SyntheticIntegrationTests(unittest.TestCase):
    def test_synthetic_portrait_and_silent_landscape(self):
        self.assertIsNotNone(media, "Implement the missing media_preflight module")
        with tempfile.TemporaryDirectory() as tmp:
            for name, size, audio in (("portrait", "90x160", True),
                                      ("landscape", "160x90", False)):
                path = Path(tmp) / (name + ".mp4")
                args = ["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                        "color=black:s=" + size + ":r=10:d=2"]
                if audio:
                    args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
                args += ["-c:v", "mpeg4", "-c:a", "aac", "-t", "2", str(path)]
                subprocess.run(args, check=True, capture_output=True, timeout=30)
                before = path.read_bytes()
                report = media.run_preflight(path, expected_duration=2)
                self.assertEqual(report["technical_pass"], audio, report)
                self.assertEqual(path.read_bytes(), before)
                if audio:
                    self.assertIn("silence", {item["code"] for item in report["warnings"]})
                    output = Path(tmp) / "report.json"
                    cli = subprocess.run([__import__("sys").executable, str(MODULE_PATH),
                                          str(path), "--output", str(output)],
                                         capture_output=True, text=True, timeout=60)
                    self.assertEqual(cli.returncode, 0, cli.stderr)
                    self.assertTrue(json.loads(output.read_text())["technical_pass"])


if __name__ == "__main__":
    unittest.main()
