"""Exercise native stop/finalization with the candidate gate, without a live bot."""
import logging
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import ultron_review_gate as gate
from patch_review_transform import patch_file

try:
    from agent import turn_stop_gates as stop, turn_finalizer as finalizer
except ImportError:
    stop = finalizer = None


@unittest.skipIf(stop is None, 'Hermes runtime is not installed')
class PresenceIntegrationTests(unittest.TestCase):
    def test_stop_then_delivery_transform_use_local_validation(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        target = Path(directory.name) / 'turn_finalizer.py'
        shutil.copyfile(finalizer.__file__, target)
        patch_file(target)
        spec = importlib.util.spec_from_file_location('_isolated_finalizer', target)
        patched_finalizer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patched_finalizer)
        agent = SimpleNamespace(_current_turn_id='presence-integration',
                                provider='custom', model='hermes-reasoning',
                                platform='telegram', session_id='isolated-presence-test')
        messages = [
            {'role': 'user', 'content': 'Old task', '_db_persisted': True, '_row_id': 1},
            {'role': 'tool', 'content': 'Old receipt'},
            {'role': 'user', 'content': 'ta ai ?', '_db_persisted': True, '_row_id': 2},
        ]
        candidate = 'Candidato de outro assunto.'
        with patch.dict(sys.modules, {'agent.ultron_review_gate': gate}), \
             patch.object(gate, 'broker', side_effect=AssertionError('network review')), \
             patch.object(stop, '_verify_on_stop_nudge', return_value=None), \
             patch.object(stop, '_pre_verify_nudge', return_value=None), \
             patch.object(stop, '_kanban_stop_nudge', return_value=None), \
             patch.object(patched_finalizer, '_invoke_hook_safely', return_value=[]) as hooks:
            decision = stop.apply_stop_gates(
                agent, {'role': 'assistant', 'content': candidate}, final_response=candidate,
                messages=messages, conversation_history=None,
                pending_verification_response=None, pending_verification_response_previewed=None)
            self.assertFalse(decision.continue_turn)
            visible, transformed, original = patched_finalizer.apply_llm_output_transform(
                agent, candidate, turn_id='presence-integration', logger=logging.getLogger(__name__))
        self.assertEqual(visible, 'Tô aqui. O que manda?')
        self.assertTrue(transformed, 'The native transcript must persist the validated replacement')
        self.assertIsNone(original, 'Do not expose a rejected candidate as alternate output')
        self.assertEqual(hooks.call_args.kwargs['response_text'], visible)
        self.assertEqual(len(messages), 3)
        self.assertTrue(gate.completion_allowed(agent))
        self.assertEqual(agent._ultron_review_verdict['status'], 'approved')


if __name__ == '__main__':
    unittest.main()
