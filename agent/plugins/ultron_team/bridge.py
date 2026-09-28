"""Dispatch a task into one persistent Hermes profile in its own process."""
import json
import os
from pathlib import Path
import subprocess
import sys

PROFILES = ('gmail', 'easysapers', 'reunioes')


class Bridge:
    def __init__(self, home='/root/.hermes', *, python=None, runner=subprocess.run, timeout=180):
        self.home = Path(home).resolve()
        self.python = python or sys.executable
        self.runner = runner
        self.timeout = timeout

    def dispatch(self, profile, task, *, context='', parent_session_id=''):
        def error(code):
            return {'status': 'error', 'profile': profile, 'error': code,
                    'answer': 'Não consegui concluir a consulta ao especialista.'}
        if profile not in PROFILES:
            return error('invalid_profile')
        if not isinstance(task, str) or not task.strip() or len(task) > 200000:
            return error('invalid_task')
        if not isinstance(context, str) or len(context) > 200000:
            return error('invalid_context')
        profile_home = self.home / 'profiles' / profile
        if profile_home.resolve() != profile_home or not all(
            (profile_home / name).is_file() for name in ('SOUL.md', 'config.yaml')
        ):
            return error('profile_not_installed')
        env = dict(os.environ)
        for key in tuple(env):
            if key.startswith('HERMES_SESSION_') or key in (
                'HERMES_YOLO_MODE', 'HERMES_ACCEPT_HOOKS', 'HERMES_INFERENCE_MODEL',
                'HERMES_INFERENCE_PROVIDER', 'HERMES_INTERACTIVE',
            ):
                env.pop(key, None)
        env.update(HERMES_HOME=str(profile_home), ULTRON_PROFILE=profile,
                   ULTRON_BASE_HOME=str(self.home), PYTHONIOENCODING='utf-8')
        request = {'task': task, 'context': context, 'parent_session_id': parent_session_id}
        try:
            result = self.runner(
                [self.python, str(Path(__file__).with_name('worker.py'))],
                input=json.dumps(request, ensure_ascii=False), text=True, encoding='utf-8',
                capture_output=True, timeout=self.timeout, env=env, cwd=str(profile_home),
            )
        except subprocess.TimeoutExpired:
            return error('worker_timeout')
        except OSError:
            return error('worker_unavailable')
        if result.returncode != 0:
            return error('worker_failed')
        if len(result.stdout) > 2000000:
            return error('worker_output_too_large')
        try:
            payload = json.loads(result.stdout)
        except (ValueError, TypeError):
            return error('worker_invalid_json')
        if not isinstance(payload, dict) or payload.get('profile') != profile:
            return error('worker_identity_mismatch')
        if payload.get('failed') or payload.get('partial'):
            payload['status'] = 'error'
        if payload.get('status') not in ('ok', 'error'):
            return error('worker_invalid_status')
        return payload
