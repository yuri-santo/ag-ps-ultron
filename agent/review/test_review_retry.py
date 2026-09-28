"""Regressões do aviso 'reviewer_unavailable_or_invalid' (27/09/2026)."""
import json
import tempfile
import unittest
from pathlib import Path

from model_review import Broker, default_policy


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.policy = default_policy()
        self.policy['review_output_tokens'] = 2048
        self.calls, self.replies = [], []
        aliases = {'hermes-reasoning': ['ag/gemini-3.8-flash-high', 'openrouter/openrouter/free']}
        self.broker = Broker(self.policy, Path(self.tmp.name), self.transport, aliases=aliases)

    def transport(self, route, payload, max_tokens, timeout):
        self.calls.append((route['model'], payload.get('pass'), payload.get('attempt', 1), max_tokens))
        reply = self.replies.pop(0) if self.replies else 'ok'
        if isinstance(reply, Exception):
            raise reply
        if reply == 'truncated':
            return {'model': route['model'], 'content': '{"verdict": "approved", "issues": [], "checks": ["Conferi'}
        return {'model': route['model'], 'content': json.dumps({'verdict': 'approved', 'issues': [], 'checks': ['ok']})}

    def review(self, task_id='t1'):
        return self.broker.review_output(task_id=task_id, producer={'provider': 'custom', 'model': 'hermes-reasoning'},
                                         output='2 + 2 = 4.', request='Quanto é 2 + 2?', evidence=[], task_kind='answer')

    def test_truncated_json_is_retried_on_the_single_eligible_reviewer(self):
        self.replies = ['truncated', 'ok', 'ok']
        result = self.review()
        self.assertEqual(result['status'], 'approved', result.get('reason'))
        self.assertEqual([c[:3] for c in self.calls],
                         [('ag/claude-opus-4-6-thinking', 1, 1), ('ag/claude-opus-4-6-thinking', 1, 2),
                          ('ag/claude-opus-4-6-thinking', 2, 1)])
        self.assertEqual(result['attempt_errors'][0]['error_type'], 'JSONDecodeError')
        self.assertTrue(all(c[3] == 2048 for c in self.calls))

    def test_retry_in_both_passes_fits_the_network_budget(self):
        self.replies = ['truncated', 'ok', 'truncated', 'ok']
        result = self.review()
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['network_calls'], 4)

    def test_persistent_failure_still_never_approves(self):
        self.replies = ['truncated', 'truncated']
        result = self.review()
        self.assertEqual((result['status'], result['reason']), ('pending_review', 'reviewer_unavailable_or_invalid'))
        self.assertFalse(result['completed'])
        self.assertEqual(len(self.calls), 2)

    def test_deterministic_failures_are_not_repeated(self):
        for error in ('reviewer_connection_inactive', 'reviewer_model_disabled'):
            with self.subTest(error=error):
                self.calls.clear()
                self.replies = [RuntimeError(error), 'ok']
                result = self.review(task_id='t-' + error)
                self.assertEqual(result['reason'], 'reviewer_unavailable_or_invalid')
                self.assertEqual(len(self.calls), 1)

    def test_mislabeled_reviewer_is_not_retried(self):
        def mislabeled(route, payload, max_tokens, timeout):
            self.calls.append(route['model'])
            return {'model': 'google/gemini-3.8-flash', 'content': json.dumps({'verdict': 'approved', 'issues': [], 'checks': ['a']})}
        self.broker.transport = mislabeled
        result = self.review()
        self.assertFalse(result['completed'])
        self.assertEqual(len(self.calls), 1)

    def test_first_attempt_payload_is_unchanged(self):
        self.review()
        self.assertEqual(self.calls[0][2], 1)


if __name__ == '__main__':
    unittest.main()
