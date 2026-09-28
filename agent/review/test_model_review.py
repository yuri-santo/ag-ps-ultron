import json
import tempfile
import unittest
from pathlib import Path

from model_review import Broker, classify, canonical_model, default_policy


class ReviewContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy = default_policy()
        self.calls = []
        self.decisions = []
        self.aliases = {'hermes-reasoning': ['ag/gemini-3.8-flash-high', 'openrouter/openrouter/free'], 'nested': ['hermes-reasoning']}
        self.broker = Broker(self.policy, Path(self.tmp.name), self.transport, aliases=self.aliases)

    def tearDown(self):
        self.tmp.cleanup()

    def transport(self, route, payload, max_tokens, timeout):
        self.calls.append((route, payload))
        decision = self.decisions.pop(0) if self.decisions else 'approved'
        if isinstance(decision, Exception):
            raise decision
        return {'model': route['model'], 'content': json.dumps({'verdict': decision, 'issues': [] if decision == 'approved' else ['Correct arithmetic.'], 'checks': ['Checked supplied task and candidate.']}), 'usage': {'total_tokens': 20}}

    def review(self, **kwargs):
        args = dict(task_id='task-1', producer={'provider': 'custom', 'model': 'ag/gemini-3.8-flash-high'}, output='2 + 2 = 4.', request='Calculate 2 + 2.', evidence=[], task_kind='answer')
        args.update(kwargs)
        return self.broker.review_output(**args)

    def test_google_openrouter_and_aliases_are_detected(self):
        for model in ['openrouter/google/gemma-4-26b-a4b-it:free', 'google/gemini-3.1-pro', 'nested', 'ag/gemini-3.8-flash-high']:
            with self.subTest(model=model):
                info = classify({'model': model}, self.aliases, self.policy)
                self.assertTrue(info['requires_review'])
                self.assertIn('google', info['authors'])

    def test_alias_cycle_and_unknown_route_fail_closed(self):
        for model, aliases in [('cycle', {'cycle': ['cycle']}), ('opaque-route', {})]:
            info = classify({'model': model}, aliases, self.policy)
            self.assertTrue(info['requires_review'])
            self.assertTrue(info['unknown'])

    def test_authorship_differs_from_antigravity_transport(self):
        info = classify({'model': 'ag/claude-opus-4-6-thinking'}, {}, self.policy)
        self.assertEqual(info['authors'], ['anthropic'])
        self.assertTrue(info['second_pass'])
        self.assertEqual(canonical_model('openrouter/anthropic/claude-opus-4-6-thinking'), canonical_model('ag/claude-opus-4-6-thinking'))

    def test_antigravity_requires_two_independent_calls(self):
        result = self.review()
        self.assertEqual(result['status'], 'approved')
        self.assertTrue(result['completed'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(result['reviews']), 2)
        self.assertGreater(result['reviews'][0]['reviewer']['tier'], result['producer']['tier'])

    def test_reviewer_outage_never_completes(self):
        self.decisions = [RuntimeError('private provider details'), RuntimeError('private provider details')]
        result = self.review()
        self.assertEqual(result['status'], 'pending_review')
        self.assertFalse(result['completed'])
        self.assertNotIn('private provider details', json.dumps(result))
        self.assertLessEqual(len(self.calls), 2)

    def test_revision_is_rechecked_then_approved(self):
        self.decisions = ['revise']
        result = self.review(output='2 + 2 = 5.')
        self.assertEqual(result['status'], 'revision_required')
        result = self.review(output='2 + 2 = 4.')
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['revision'], 1)
        self.assertEqual(len(self.calls), 3)

    def test_second_pass_rejection_blocks_completion(self):
        self.decisions = ['approved', 'revise']
        result = self.review()
        self.assertEqual(result['status'], 'revision_required')
        self.assertFalse(result['completed'])

    def test_existing_result_does_not_recursively_review(self):
        self.review()
        result = self.review()
        self.assertTrue(result['completed'])
        self.assertEqual(len(self.calls), 2)
        result = self.review(task_id='review-child', context={'review_depth': 1})
        self.assertEqual(result['status'], 'pending_review')
        self.assertFalse(result['completed'])
        self.assertEqual(len(self.calls), 2)

    def test_no_same_model_or_lower_tier_reviewer(self):
        self.broker.policy['reviewers'] = [{'model': 'openrouter/google/gemini-3.1-pro', 'tier': 4}, {'model': 'openrouter/z-ai/glm-5.2:free', 'tier': 2}]
        result = self.review(producer={'model': 'ag/gemini-3.1-pro-low'})
        self.assertEqual(result['status'], 'pending_review')
        self.assertEqual(len(self.calls), 0)

    def test_google_mislabeled_as_reviewer_is_rejected(self):
        def mislabeled(route, payload, max_tokens, timeout):
            return {'model': 'google/gemini-3.8-flash', 'content': json.dumps({'verdict': 'approved','issues': [], 'checks':['a']})}
        self.broker.transport = mislabeled
        result = self.review()
        self.assertEqual(result['status'], 'pending_review')
        self.assertFalse(result['completed'])

    def test_failed_validation_stops_before_llm(self):
        result = self.review(task_kind='code', evidence=[{'kind':'test', 'ok':False, 'summary':'Regression failed'}])
        self.assertEqual(result['status'], 'validation_failed')
        self.assertEqual(len(self.calls), 0)

    def test_artifact_must_match_recorded_hash(self):
        artifact = Path(self.tmp.name)/'artifact.txt'
        artifact.write_text('actual')
        result = self.review(task_kind='artifact', evidence=[{'kind':'artifact','path':str(artifact),'sha256':'0'*64,'ok':True}])
        self.assertEqual(result['status'], 'validation_failed')

    def test_task_budget_stops_before_network(self):
        self.broker.policy['max_task_tokens'] = 10
        result = self.review()
        self.assertEqual(result['status'], 'pending_review')
        self.assertEqual(len(self.calls), 0)

    def test_large_candidate_is_pending_without_silent_truncation(self):
        result = self.review(output='a' * (self.policy['max_input_bytes'] + 1))
        self.assertEqual(result['status'], 'pending_review')
        self.assertEqual(len(self.calls), 0)


if __name__ == '__main__':
    unittest.main()
