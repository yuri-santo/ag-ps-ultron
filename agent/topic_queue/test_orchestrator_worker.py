import json
from types import SimpleNamespace

import orchestrator_worker
import specialist


def test_primary_worker_keeps_reviewed_text_immutable(tmp_path, monkeypatch):
    observed = {}

    def run(command, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=json.dumps({'profile': 'ultron'}))

    monkeypatch.setattr(orchestrator_worker.subprocess, 'run', run)
    monkeypatch.setenv('ULTRON_HOST_HANDLES_SPEECH', '0')
    orchestrator_worker.dispatch_ultron(tmp_path, 'ta ai ?')
    assert observed['env']['ULTRON_HOST_HANDLES_SPEECH'] == '1'


def test_specialist_worker_keeps_reviewed_text_immutable(monkeypatch):
    observed = {}
    env = {'ULTRON_PROFILE': 'pink', 'ULTRON_HOST_HANDLES_SPEECH': '0'}

    def run(command, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(specialist.subprocess, 'run', run)
    specialist.run_specialist(['python', '/private/worker.py'], env=env)
    assert observed['env']['ULTRON_HOST_HANDLES_SPEECH'] == '1'
    assert env['ULTRON_HOST_HANDLES_SPEECH'] == '0'
