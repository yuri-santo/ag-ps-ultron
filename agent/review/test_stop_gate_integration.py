"""Run with Hermes' venv to verify invisible in-turn review continuation."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from agent import turn_stop_gates as stop
except ImportError:
    stop = None


@unittest.skipIf(stop is None, 'Hermes runtime is not installed')
class StopGateIntegration(unittest.TestCase):
    def test_rejected_candidate_is_not_emitted_and_is_revised_once(self):
        agent = SimpleNamespace(_current_turn_id='turn-1')
        messages = [{'role': 'user', 'content': 'Tudo bem com você?'}]
        candidate = {'role': 'assistant', 'content': 'Revisão concluída.'}
        with patch.object(stop, '_verify_on_stop_nudge', return_value=None), \
             patch.object(stop, '_pre_verify_nudge', return_value=None), \
             patch.object(stop, '_kanban_stop_nudge', return_value=None), \
             patch('agent.ultron_review_gate.review_stop_feedback',
                   return_value='Responda à pergunta do usuário.'):
            verdict = stop.apply_stop_gates(
                agent, candidate, final_response=candidate['content'], messages=messages,
                conversation_history=None, pending_verification_response=None,
                pending_verification_response_previewed=None)
            self.assertTrue(verdict.continue_turn)
            self.assertIsNone(verdict.pending_verification_response)
            self.assertEqual(messages[-2]['role'], 'assistant')
            self.assertTrue(messages[-2]['_review_stop_synthetic'])
            self.assertEqual(messages[-1]['role'], 'user')
            self.assertTrue(messages[-1]['_review_stop_synthetic'])
            second = stop.apply_stop_gates(
                agent, {'role': 'assistant', 'content': 'Tudo bem!'},
                final_response='Tudo bem!', messages=messages,
                conversation_history=None, pending_verification_response=None,
                pending_verification_response_previewed=None)
            self.assertFalse(second.continue_turn)

    def test_revision_is_rechecked_and_finalizer_reuses_approval(self):
        from agent import ultron_review_gate as gate
        agent = SimpleNamespace(_current_turn_id='turn-2', provider='ag',
                                model='ag/gemini-3.8-flash-high')
        messages = [{'role': 'user', 'content': 'Responda a pergunta com precisão.'}]
        decisions = [
            {'completed': False, 'status': 'revision_required', 'reviews': [
                {'verdict': {'issues': ['Faltou responder ao pedido.']}}]},
            {'completed': True, 'status': 'approved', 'reviews': []},
        ]
        def review_output(**_kwargs):
            return decisions.pop(0)
        with patch.object(stop, '_verify_on_stop_nudge', return_value=None), \
             patch.object(stop, '_pre_verify_nudge', return_value=None), \
             patch.object(stop, '_kanban_stop_nudge', return_value=None), \
             patch.object(gate, 'hold_output', return_value=True), \
             patch.object(gate, 'broker') as broker:
            broker.return_value.review_output.side_effect = review_output
            first = stop.apply_stop_gates(
                agent, {'role': 'assistant', 'content': 'Errada.'},
                final_response='Errada.', messages=messages,
                conversation_history=None, pending_verification_response=None,
                pending_verification_response_previewed=None)
            self.assertTrue(first.continue_turn)
            second = stop.apply_stop_gates(
                agent, {'role': 'assistant', 'content': 'Resposta correta.'},
                final_response='Resposta correta.', messages=messages,
                conversation_history=None, pending_verification_response=None,
                pending_verification_response_previewed=None)
            self.assertFalse(second.continue_turn)
            self.assertEqual(gate.review_final(agent, 'Resposta correta.', 'turn-2'),
                             'Resposta correta.')
            self.assertEqual(broker.return_value.review_output.call_count, 2)
            self.assertEqual(decisions, [])


if __name__ == '__main__':
    unittest.main()
