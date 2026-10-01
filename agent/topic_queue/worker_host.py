"""Native Kanban subprocess entry; not a scheduler or model-facing tool."""
import argparse
import os
from pathlib import Path


def execute(home, task, run, *, factory=None):
    home = str(Path(home).resolve())
    os.environ.update(HERMES_HOME=home, ULTRON_BASE_HOME=home, HERMES_KANBAN_HOME=home)
    # Child specialists must not acquire native lifecycle tools implicitly.
    for key in list(os.environ):
        if key.startswith('HERMES_KANBAN_') and key != 'HERMES_KANBAN_HOME':
            os.environ.pop(key, None)
        elif key.startswith('HERMES_SESSION_') or key in ('HERMES_PROFILE', 'HERMES_TENANT'):
            os.environ.pop(key, None)
    if factory is None:
        from .runtime import Runtime
        factory = Runtime.from_home
    factory(home).run(task, int(run))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--run', required=True, type=int)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        execute(args.home, args.task, args.run)
    except Exception as exc:
        # Worker logs may be displayed by the native UI. No task/evidence text.
        print('Topic worker failed: ' + type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
