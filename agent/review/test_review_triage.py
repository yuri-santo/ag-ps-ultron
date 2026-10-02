"""Regressions for cheap conversational turns and reviewer-facing failures."""
import unittest
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

import ultron_review_gate as gate


class Agent:
    provider = 'ag'
    model = 'ag/gemini-3.8-flash-high'
    _current_turn_id = 'greeting-1'

    def __init__(self, request):
        self._ultron_review_messages = [{'role': 'user', 'content': request}]


class TriageTests(unittest.TestCase):
    def test_subject_unavailability_releases_answer_with_confidence(self):
        agent = Agent('Analise a nota SAP')
        record = dict(status='unvalidated', completed=True, approval_completed=False,
                      confidence='limited', delivery_notice='\n\nConfianca limitada: revisao incompleta. Thor indisponivel.')
        module = SimpleNamespace(review_answer=lambda *a: record)
        with patch.object(gate.Path, 'read_text', return_value=json.dumps({'subject_review_v2': True})), \
             patch.dict(sys.modules, {'ultron_topic_queue.subject_review': module}):
            visible = gate.review_final(agent, 'Analise da nota.', 'greeting-1')
        self.assertTrue(visible.startswith('Analise da nota.'))
        self.assertIn('Confianca limitada', visible)
        self.assertTrue(gate.completion_allowed(agent))
        self.assertFalse(agent._ultron_review_verdict['approval_completed'])

    def test_only_standalone_social_greetings_skip_network_review(self):
        for request in ('Oi!', 'Tudo bem com você?', 'Bom dia', 'Obrigado!',
                        'ultron voce esta ai?', 'ta ai ultron?'):
            with self.subTest(request=request):
                self.assertEqual(gate.triage_request(request), 'social')
        for request in ('Tudo bem com você? Analise meu contrato.',
                        'Oi, qual a dose do remédio?', 'Bom dia, publique no TikTok',
                        'Obrigado. Qual ação devo comprar?'):
            with self.subTest(request=request):
                self.assertEqual(gate.triage_request(request), 'review')

    def test_greeting_does_not_show_reviewers_internal_status(self):
        agent = Agent('tudo bem com você')
        with patch.object(gate, 'hold_output', side_effect=AssertionError('review called')):
            visible = gate.review_final(agent, 'Revisão concluída. Nenhuma pendência identificada.', 'greeting-1')
        self.assertIn('bem', visible.lower())
        self.assertNotIn('revisão', visible.lower())
        self.assertTrue(gate.completion_allowed(agent))

    def test_substantive_revision_does_not_expose_issues(self):
        agent = Agent('Analise meu contrato')
        record = {'completed': False, 'status': 'revision_required',
                  'reason': 'independent_review_revise',
                  'reviews': [{'verdict': {'issues': ['private English reviewer note']}}]}
        with patch.object(gate, 'hold_output', return_value=True), \
             patch.object(gate, 'broker') as broker:
            broker.return_value.review_output.return_value = record
            visible = gate.review_final(agent, 'Resposta defeituosa', 'greeting-1')
        self.assertNotIn('private English reviewer note', visible)
        self.assertNotIn('independent_review_revise', visible)
        self.assertFalse(gate.completion_allowed(agent))

    def test_reviewer_findings_are_available_only_for_internal_revision(self):
        agent = Agent('Analise meu contrato')
        record = {'completed': False, 'status': 'revision_required',
                  'reason': 'independent_review_revise',
                  'reviews': [{'verdict': {'issues': ['Faltou responder ao pedido.']}}]}
        with patch.object(gate, 'hold_output', return_value=True), \
             patch.object(gate, 'broker') as broker:
            broker.return_value.review_output.return_value = record
            feedback = gate.review_stop_feedback(agent, 'Resposta defeituosa',
                                                 agent._ultron_review_messages, 'greeting-1')
        self.assertIn('Faltou responder', feedback)
        self.assertEqual(agent._ultron_review_verdict['status'], 'revision_required')


if __name__ == '__main__':
    unittest.main()
