"""Local native cron script: renew auth without a model or leaking provider output."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

CLI = '/opt/hermes-agent-20260924/venv/bin/notebooklm'
STATE = Path('/root/ultron-local/notebooklm-auth-health.json')


def refresh(state=STATE, runner=subprocess.run):
    state = Path(state)
    state.parent.mkdir(parents=True, exist_ok=True)
    with open(str(state) + '.lock', 'a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            previous = json.loads(state.read_text()).get('status') if state.exists() else None
        except (ValueError, OSError, AttributeError):
            previous = None
        env = dict(os.environ, NOTEBOOKLM_HOME='/root/.notebooklm', NOTEBOOKLM_PROFILE='default')
        env.pop('NOTEBOOKLM_AUTH_JSON', None)
        try:
            result = runner([CLI, '-p', 'default', 'auth', 'refresh', '--quiet'],
                            env=env, capture_output=True, text=True, timeout=90)
            status = 'ok' if result.returncode == 0 else 'failed'
        except (OSError, subprocess.TimeoutExpired):
            status = 'failed'
        fd, temporary = tempfile.mkstemp(prefix='.notebooklm-health-', dir=state.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'status': status}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, state)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        if status == previous or (status == 'ok' and previous is None):
            return ''
        if status == 'ok':
            return 'Ultron: A conexao com o NotebookLM foi restabelecida.'
        return ('Ultron: Nao consegui renovar a sessao local do NotebookLM. '
                'Pode ser necessario autenticar novamente no navegador.')


if __name__ == '__main__':
    message = refresh()
    if message:
        print(message)
