#!/usr/bin/env python3
"""Offline-only launcher for the pinned PhoneHarness evaluation checkout."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


REVISION = "1cdc0d963641d517f5deb687adb37332cf844e70"
ROOT = Path("/opt/phoneharness-1cdc0d9")
PYTHON = ROOT / ".venv/bin/python"


def offline_environment():
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(ROOT / "offline-home"),
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run_offline(arguments):
    unshare = shutil.which("unshare", path="/usr/bin:/bin")
    if not unshare:
        raise RuntimeError("unshare is required; offline commands fail closed")
    if not PYTHON.is_file():
        raise RuntimeError("isolated PhoneHarness environment is not installed")
    return subprocess.run(
        [unshare, "--net", "--", str(PYTHON), "-s", *arguments],
        cwd=ROOT,
        env=offline_environment(),
        timeout=90,
        check=False,
    ).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="PhoneHarness local preparation. Device and model operations are disabled."
    )
    parser.add_argument(
        "command", nargs="?", default="diagnose",
        choices=("diagnose", "upstream-help", "self-test"),
    )
    args = parser.parse_args(argv)
    if args.command == "diagnose":
        print(json.dumps({
            "revision": REVISION,
            "runtime_directory": str(ROOT),
            "venv_present": PYTHON.is_file(),
            "source_present": (ROOT / "phoneharness/__main__.py").is_file(),
            "operations_enabled": False,
            "network_checks_performed": False,
            "device_checks_performed": False,
            "missing_adb_helpers": [
                name for name in ("health_check.sh", "adb_ubuntu_exec.sh")
                if not (ROOT / "scripts" / name).is_file()
            ],
        }, indent=2))
        return 0
    if args.command == "upstream-help":
        return run_offline(["-m", "phoneharness", "--help"])
    return run_offline(["-m", "unittest", "discover", "-s", "tests", "-v"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"PhoneHarness preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
