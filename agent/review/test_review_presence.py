"""Presence checks are locally validated without admitting unrelated claims."""
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import ultron_review_gate as gate


def agent_for(content, history=None):
    return SimpleNamespace(
        provider='custom', model='hermes-reasoning', platform='telegram',
        _current_turn_id='presence-1',
        _ultron_review_messages=[*(history or []), {
            'role': 'user', 'content': content, 'timestamp': 1790690346.0,
            '_db_persisted': True, '_row_id': 42,
            'display_metadata': {'gateway_input_owner': 'fixture'},
        }],
    )


class PresenceReviewTests(unittest.TestCase):
    def test_portuguese_presence_has_local_approved_text_not_raw_candidate(self):
        for request in ('ta ai ?', 'tá aí?', 'Você está aí?', 'voce ta ai?',
                        'está por aí?', 'oi, ta ai?'):
            with self.subTest(request=request):
                agent = agent_for(request)
                with patch.object(gate, 'broker', side_effect=AssertionError('network review')):
                    text = gate.review_final(agent, 'Revisão concluída.', 'presence-1')
                self.assertEqual(text, 'Tô aqui. O que manda?')
                verdict = agent._ultron_review_verdict
                self.assertEqual(verdict['status'], 'approved')
                self.assertEqual(verdict['reason'], 'local_social_validation')
                self.assertEqual(verdict['validator'], 'standalone_social_v1')
                self.assertEqual(verdict['request_sha256'], hashlib.sha256(request.encode()).hexdigest())
                self.assertEqual(verdict['output_sha256'], hashlib.sha256(text.encode()).hexdigest())
                self.assertTrue(gate.completion_allowed(agent))

    def test_social_candidate_cannot_smuggle_action_or_advice(self):
        for candidate in ('Já publiquei seu anúncio.', 'Tome duas doses agora.',
                          'A viagem custa 800 reais.', 'Nenhuma pendência identificada.'):
            with self.subTest(candidate=candidate):
                agent = agent_for('Oi!')
                with patch.object(gate, 'broker', side_effect=AssertionError('network review')):
                    text = gate.review_final(agent, candidate, 'presence-1')
                self.assertEqual(text, 'Oi! Como posso ajudar?')
                self.assertEqual(agent._ultron_review_verdict['status'], 'approved')

    def assert_network_review(self, agent):
        with patch.object(gate, 'hold_output', return_value=True), \
             patch.object(gate, 'broker') as broker:
            broker.return_value.review_output.return_value = {
                'status': 'pending_review', 'completed': False,
            }
            gate.review_final(agent, 'Candidato', 'presence-1')
            self.assertEqual(broker.return_value.review_output.call_count, 1)
        self.assertFalse(gate.completion_allowed(agent))

    def test_mixed_long_multimodal_and_scheduled_requests_require_review(self):
        for request in ('ta ai? já tomei meu remédio', 'ta ai? publique o anúncio',
                        'ta ai? onde estão os emails?', 'ta ai? qual ação comprar?',
                        'Oi!' + ' ' * 4100 + ' Qual dose devo tomar?',
                        [{'type': 'text', 'text': 'Oi!'}, {'type': 'image_url',
                         'image_url': {'url': 'data:image/png;base64,AAAA'}}], ''):
            with self.subTest(request_type=type(request).__name__):
                self.assert_network_review(agent_for(request, [{'role': 'user', 'content': 'Oi!'}]))
        agent = agent_for('ta ai?')
        agent.platform = 'cron'
        self.assert_network_review(agent)

    def test_tool_attempt_even_without_receipt_requires_review(self):
        for message in (
            {'role': 'assistant', 'tool_calls': [{'id': 'call-1', 'function': {
                'name': 'send_message', 'arguments': '{}'}}]},
            {'role': 'assistant', 'function_call': {'name': 'send_message', 'arguments': '{}'}},
            {'role': 'tool', 'tool_call_id': 'call-1', 'content': 'ok'},
        ):
            with self.subTest(message=message):
                agent = agent_for('Oi!')
                agent._ultron_review_messages.append(message)
                self.assert_network_review(agent)

    def test_persistence_metadata_does_not_include_old_receipts(self):
        old = [
            {'role': 'user', 'content': 'Consultar assunto anterior'},
            {'role': 'assistant', 'tool_calls': [{'id': 'old', 'function': {
                'name': 'web_search', 'arguments': '{}'}}]},
            {'role': 'tool', 'tool_call_id': 'old', 'content': 'old evidence'},
        ]
        agent = agent_for('ta ai ?', old)
        self.assertEqual(gate.tool_evidence(agent._ultron_review_messages), [])
        with patch.object(gate, 'broker', side_effect=AssertionError('network review')):
            self.assertEqual(gate.review_final(agent, 'Texto de outro assunto', 'presence-1'),
                             'Tô aqui. O que manda?')

    def test_revision_nudges_keep_current_tool_receipts(self):
        messages = agent_for('Consulte o pedido')._ultron_review_messages + [
            {'role': 'assistant', 'tool_calls': [{'id': 'current', 'function': {
                'name': 'lookup', 'arguments': '{}'}}]},
            {'role': 'tool', 'tool_call_id': 'current', 'content': 'current evidence'},
            {'role': 'user', 'content': 'Revise a resposta', '_review_stop_synthetic': True},
        ]
        self.assertEqual([r['call_id'] for r in gate.tool_evidence(messages)], ['current'])
        self.assertEqual(gate.task_review_request(messages), 'Consulte o pedido')

    def test_multimodal_current_request_does_not_reuse_old_greeting(self):
        messages = agent_for([{'type': 'text', 'text': 'Analise a imagem'}],
                             [{'role': 'user', 'content': 'Oi!'}])._ultron_review_messages
        self.assertNotEqual(gate.task_review_request(messages), 'Oi!')
        self.assertIn('Analise a imagem', gate.task_review_request(messages))

    def test_cached_approval_is_bound_to_request_and_candidate(self):
        agent = agent_for('Oi!')
        with patch.object(gate, 'broker', side_effect=AssertionError('network review')):
            gate.review_final(agent, 'Oi!', 'presence-1')
        agent._ultron_review_messages[-1]['content'] = 'Analise o contrato'
        self.assert_network_review(agent)

        agent = agent_for('Analise o contrato')
        with patch.object(gate, 'hold_output', return_value=True), \
             patch.object(gate, 'broker') as broker:
            broker.return_value.review_output.side_effect = [
                {'status': 'approved', 'completed': True},
                {'status': 'revision_required', 'completed': False},
            ]
            gate.review_final(agent, 'Primeira versao', 'presence-1')
            gate.review_final(agent, 'Outra versao', 'presence-1')
            self.assertEqual(broker.return_value.review_output.call_count, 2)
        self.assertFalse(gate.completion_allowed(agent))


if __name__ == '__main__':
    unittest.main()
