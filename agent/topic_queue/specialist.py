"""Use the installed restricted worker, retaining actual response-model metadata."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def capture_identity(agent, response, aliases):
    model = getattr(response, 'model', None)
    agent.last_served_model = (
        model if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_.:/+\-]{1,200}', model)
        and '://' not in model and model not in aliases else None)


def run_specialist(command, **kwargs):
    # The original bridge supplies allowlisted profile, scrubbed session env,
    # timeout, JSON request and cwd. Only its script entry is substituted.
    return subprocess.run([command[0], '-m', 'ultron_topic_queue.specialist', command[1]], **kwargs)


def main():
    home = Path(os.environ['ULTRON_BASE_HOME']).resolve()
    target = Path(sys.argv[1]).resolve()
    if target != home / 'plugins' / 'ultron_team' / 'worker.py':
        raise ValueError('Unexpected worker boundary')
    sys.path.insert(0, str(home.parent / 'ultron-local'))
    sys.path.insert(0, str(home / 'plugins'))
    import model_review
    aliases = set(model_review.live_aliases())
    from agent import ultron_review_gate
    original_producer = ultron_review_gate.producer
    def observed_producer(agent):
        value = original_producer(agent)
        if value.get('served_model') and value['served_model'] not in aliases:
            value['requested_model'] = value['model']
            value['model'] = value['served_model']
        return value
    ultron_review_gate.producer = observed_producer
    import run_agent
    original_agent = run_agent.AIAgent
    class TopicAgent(original_agent):
        def __init__(self, *args, **kwargs):
            kwargs['enabled_toolsets'] = [s for s in kwargs.get('enabled_toolsets', []) if s != 'kanban']
            kwargs['ephemeral_system_prompt'] = kwargs.get('ephemeral_system_prompt', '') + (
                '\nConversa direta com o titular no perfil explicitamente escolhido. '
                'Use a personalidade do seu SOUL. Responda de modo natural; parecer com '
                'veredicto e campos formais somente quando solicitado ou necessario. '
                'Quando perguntado sobre o perfil ativo, informe seu nome real. '
                'Bordao curto so quando couber; nunca substitui a resposta solicitada.')
            super().__init__(*args, **kwargs)
    run_agent.AIAgent = TopicAgent
    from agent import turn_response_intake
    original = turn_response_intake.normalize_response_for_agent
    def observed(agent, response):
        capture_identity(agent, response, aliases)
        return original(agent, response)
    turn_response_intake.normalize_response_for_agent = observed
    spec = importlib.util.spec_from_file_location('_restricted_topic_worker', target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_proof = module._worker_proof
    def with_evidence(result, agent, failed):
        proof = original_proof(result, agent, failed)
        proof['evidence'] = ultron_review_gate.tool_evidence(result.get('messages') or [])
        return proof
    module._worker_proof = with_evidence
    if os.environ.get('ULTRON_PROFILE') == 'ultron':
        from .orchestrator_worker import execute
        module.execute = lambda request: execute(request, with_evidence)
    module.main()


if __name__ == '__main__':
    main()
