"""Installed-policy smoke test. No real model request, tool action or Telegram send."""
import hashlib
import importlib.util
import json
from types import SimpleNamespace
from unittest.mock import patch

from agent import ultron_review_gate as gate


def main():
    worker = '/root/.hermes/plugins/ultron_team/worker.py'
    spec = importlib.util.spec_from_file_location('probe_worker', worker)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = []
    errors = [type('NotFoundError', (Exception,), {'status_code': 404})(), TimeoutError()]
    for error in errors:
        agent = SimpleNamespace(provider='custom', model='ag/gemini-3.8-flash-high',
            last_served_model='gemini-3.8-flash-high', _current_turn_id='confidence-smoke',
            _ultron_review_messages=[{'role': 'user', 'content': 'Analise a nota SAP final 14'}])
        with patch('ultron_topic_queue.reviewer._call', side_effect=error) as call:
            text = gate.review_final(agent, 'Preciso do numero completo da nota para confirmar a analise.',
                                     agent._current_turn_id)
        record = agent._ultron_review_verdict
        assert call.call_count == 1
        assert record['status'] == 'unvalidated' and record['approval_completed'] is False
        assert gate.completion_allowed(agent)
        assert 'Confianca limitada' in text and 'Nao validado por Thor' in text
        assert record['output_sha256'] == hashlib.sha256(text.encode()).hexdigest()
        proof = module._worker_proof(dict(completed=True, final_response=text,
                                          model_review=record, messages=[]), agent, False)
        assert not proof['_proof_rejected'] and proof['model_review']['confidence'] == 'limited'
        checks.append(type(error).__name__)
    print(json.dumps(dict(installed_policy='ok', checks=checks, real_network_calls=0)))


if __name__ == '__main__':
    main()
