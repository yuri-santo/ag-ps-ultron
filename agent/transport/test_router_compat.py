import json
from pathlib import Path
import tempfile
import unittest

from patch_router_compat import ANCHOR, patch_file
from ultron_router_compat import protect_router_tool_results


class RouterCompatTests(unittest.TestCase):
    def test_nested_schema_is_opaque_but_preserved(self):
        raw = json.dumps({'schema': {'properties': {'tier': {'$ref': '#/$defs/ReasoningTier'}}}})
        messages = [{'role': 'tool', 'tool_call_id': 'call_1', 'content': raw}]
        result = protect_router_tool_results(messages, base_url='http://127.0.0.1:20130/v1')
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result[0]['content'])
        self.assertTrue(result[0]['content'].endswith(raw))
        self.assertEqual(result[0]['tool_call_id'], 'call_1')
        self.assertEqual(messages[0]['content'], raw)
        self.assertIsNot(messages, result)
        self.assertIsNot(messages[0], result[0])

    def test_array_schema_and_idempotence(self):
        messages = [{'role': 'tool', 'content': '[{"$ref":"#/definitions/X"}]'}]
        once = protect_router_tool_results(messages, base_url='http://localhost:20130/v1/')
        twice = protect_router_tool_results(once, base_url='http://localhost:20130/v1')
        self.assertEqual(once, twice)
        self.assertIs(once, twice)

    def test_ordinary_results_and_other_roles_are_unchanged(self):
        for role, content in [('tool', '{"status":"ok","count":2}'),
                              ('tool', 'not json'),
                              ('assistant', '{"$ref":"#/X"}'),
                              ('user', '{"$ref":"#/X"}'),
                              ('tool', [{'type': 'image_url', 'image_url': {'url': 'data:x'}}])]:
            messages = [{'role': role, 'content': content}]
            self.assertIs(messages, protect_router_tool_results(
                messages, base_url='http://127.0.0.1:20130/v1'))

    def test_other_transports_are_unchanged(self):
        messages = [{'role': 'tool', 'content': '{"$ref":"#/X"}'}]
        for base_url in ('https://api.openai.com/v1', 'http://127.0.0.1:9999/v1',
                         'http://127.0.0.1.evil.example:20130/v1', None):
            self.assertIs(messages, protect_router_tool_results(messages, base_url=base_url))
        self.assertIs(messages, protect_router_tool_results(
            messages, base_url='http://127.0.0.1:20130/v1', api_mode='anthropic_messages'))

    def test_patch_is_idempotent_and_backs_up_original(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'chat_completion_helpers.py'
            original = 'def build_api_kwargs(agent, api_messages, tools_for_api=None):\n' + ANCHOR
            target.write_text(original, encoding='utf-8')
            self.assertTrue(patch_file(target))
            self.assertFalse(patch_file(target))
            self.assertEqual(target.read_text().count('protect_router_tool_results('), 1)
            backups = list(Path(directory).glob('*.bak-ultron-router-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), original)
            compile(target.read_text(), str(target), 'exec')

    def test_patch_refuses_unknown_upstream(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'chat_completion_helpers.py'
            target.write_text('changed upstream\n')
            with self.assertRaises(RuntimeError):
                patch_file(target)
            self.assertEqual(target.read_text(), 'changed upstream\n')
            with self.assertRaises(ValueError):
                patch_file(Path(directory) / 'wrong.py')


if __name__ == '__main__':
    unittest.main()
