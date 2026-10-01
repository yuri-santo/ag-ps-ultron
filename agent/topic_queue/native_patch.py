"""Exact-source offline patcher. Unknown upstream versions need a fresh audit."""
import hashlib

SOURCE_SHA256 = {
    'plugins/platforms/telegram/adapter.py': '2e18f91d2abeaa70e23b2b7e6e9d469a372f11f243dc161c158206d0e413bd79',
    'gateway/kanban_watchers.py': 'a9ba617c7cae2d83022d07d32cd80a391b7a0ff72ece54b04890521466d067d9',
    'hermes_cli/kanban_db_dispatch.py': 'cae1e2eaa7d95083a2c94e13f6e01a25cc307e88c64be89b123504a2aa80c3f8',
    'hermes_cli/kanban_db.py': 'b51a4ea1d2fe614f9c69c79e8c9a5345e711b2f1171916840a4ada5edb106edf',
    'gateway/kanban_watchers_notifier.py': 'b50ceea5fb309a7ecdc801ccda919cc5038ecbc7d2ad299d7ecf4c5eef26dbe1',
}
PATCHES = {
    'gateway/kanban_watchers_notifier.py': [
        ('                    claimed = self._claim_for_sub(conn, slug, sub)',
         '                    task = kb.get_task(conn, sub["task_id"])\n'
         '                    if task is not None and task.created_by == "topic_queue":\n'
         '                        continue  # Only the reviewed outbox delivers these cards.\n'
         '                    claimed = self._claim_for_sub(conn, slug, sub)'),
    ],
    'plugins/platforms/telegram/adapter.py': [
        ('        self._enqueue_text_event(await self._build_triggered_event(msg, update, MessageType.TEXT))',
         '        event = await self._build_triggered_event(msg, update, MessageType.TEXT)\n'
         '        from ultron_topic_queue import gateway_adapter as _ultron_topic_queue\n'
         '        if await _ultron_topic_queue.try_admit(self, event):\n'
         '            return\n'
         '        self._enqueue_text_event(event)'),
        ('        event = await self._build_triggered_event(msg, update, MessageType.COMMAND)\n',
         '        event = await self._build_triggered_event(msg, update, MessageType.COMMAND)\n'
         '        from ultron_topic_queue import gateway_adapter as _ultron_topic_queue\n'
         '        await _ultron_topic_queue.control_command(self, event)\n'),
    ],
    'gateway/kanban_watchers.py': [
        ('                    results = await _to_thread_process_service(dispatcher.tick_once)',
         '                    from ultron_topic_queue import gateway_adapter as _ultron_topic_queue\n'
         '                    await _ultron_topic_queue.tick(self)\n'
         '                    results = await _to_thread_process_service(dispatcher.tick_once)'),
    ],
    'hermes_cli/kanban_db_dispatch.py': [
        ('    cmd = [\n        *_resolve_hermes_argv(),',
         '    if task.created_by == "topic_queue":\n'
         '        from hermes_constants import get_default_hermes_root\n'
         '        return [sys.executable, "-m", "ultron_topic_queue.worker_host",\n'
         '                "--task", task.id, "--run", str(task.current_run_id),\n'
         '                "--home", str(get_default_hermes_root())]\n'
         '    cmd = [\n        *_resolve_hermes_argv(),'),
    ],
    'hermes_cli/kanban_db.py': [
        ('\ndef complete_task(\n',
         '\nfrom ultron_topic_queue.native_guard import guard_completion, guard_mutation\n\n'
         '@guard_completion\ndef complete_task(\n'),
        *[('\ndef ' + name + '(', '\n@guard_mutation\ndef ' + name + '(')
          for name in ('edit_task', 'archive_task', 'delete_task', 'delete_archived_task')],
    ],
}


def _hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def patch_sources(sources):
    if set(sources) != set(SOURCE_SHA256):
        raise ValueError('Missing or unknown native source files')
    result, states = {}, set()
    for path, source in sources.items():
        original = source
        if _hash(source) == SOURCE_SHA256[path]:
            states.add('original')
        else:
            for before, after in reversed(PATCHES[path]):
                if original.count(after) != 1:
                    raise ValueError('Unknown upstream source or partial patch: ' + path)
                original = original.replace(after, before, 1)
            if _hash(original) != SOURCE_SHA256[path]:
                raise ValueError('Unknown upstream source: ' + path)
            states.add('patched')
        patched = original
        for before, after in PATCHES[path]:
            if patched.count(before) != 1:
                raise ValueError('Ambiguous native source anchor: ' + path)
            patched = patched.replace(before, after, 1)
        compile(patched, path, 'exec')
        result[path] = patched
    if len(states) != 1:
        raise ValueError('Mixed partial installation is not accepted')
    return result
