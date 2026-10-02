"""Offline patch tests using copies of the inspected native Python sources."""
import ast
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


TELEGRAM = 'plugins/platforms/telegram/adapter.py'
WATCHER = 'gateway/kanban_watchers.py'
DISPATCH = 'hermes_cli/kanban_db_dispatch.py'
DATABASE = 'hermes_cli/kanban_db.py'
NOTIFIER = 'gateway/kanban_watchers_notifier.py'
PATHS = (TELEGRAM, WATCHER, DISPATCH, DATABASE, NOTIFIER,
         'agent/turn_response_intake.py', 'gateway/run_turn_runner.py')


@pytest.fixture
def patcher():
    path = Path(__file__).with_name('native_patch.py')
    assert path.is_file(), 'offline native patcher is not implemented'
    spec = importlib.util.spec_from_file_location('native_patch_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sources(tmp_path):
    root = Path(os.environ.get('NATIVE_SOURCE_ROOT', '/opt/hermes-agent-20260924'))
    if not all((root / path).is_file() for path in PATHS):
        pytest.skip('set NATIVE_SOURCE_ROOT to an offline copy of the inspected Hermes sources')
    result = {}
    for path in PATHS:
        original = (root / path).read_bytes()
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original)
        result[path] = target.read_text(encoding='utf-8')
    return result


def function_node(source, name):
    return next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)


def load_function(source, name, namespace=None):
    node = function_node(source, name)
    tree = ast.Module(body=[ast.ImportFrom(module='__future__',
                                         names=[ast.alias(name='annotations')], level=0), node],
                      type_ignores=[])
    namespace = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(tree), '<offline native function>', 'exec'), namespace)
    return namespace[name]


def test_patch_compiles_all_files_and_is_idempotent(patcher, sources):
    before = dict(sources)
    result = patcher.patch_sources(sources)
    assert sources == before
    assert set(result) == set(PATHS)
    assert all(result[path] != sources[path] for path in PATHS)
    for path, source in result.items():
        compile(source, path, 'exec')
    assert patcher.patch_sources(result) == result


@pytest.mark.parametrize('path', PATHS)
def test_unknown_source_is_rejected(patcher, sources, path):
    sources[path] += '\n# unrelated upstream change\n'
    with pytest.raises(ValueError, match='source|upstream'):
        patcher.patch_sources(sources)


def test_mixed_and_partial_installations_are_rejected(patcher, sources):
    result = patcher.patch_sources(sources)
    mixed = dict(sources, **{TELEGRAM: result[TELEGRAM]})
    with pytest.raises(ValueError, match='partial|mixed'):
        patcher.patch_sources(mixed)
    result[TELEGRAM] = result[TELEGRAM].replace(
        '        await _ultron_topic_queue.control_command(self, event)\n', '', 1)
    with pytest.raises(ValueError):
        patcher.patch_sources(result)


def test_missing_source_rejected(patcher, sources):
    del sources[WATCHER]
    with pytest.raises(ValueError, match='source|missing'):
        patcher.patch_sources(sources)


def test_modified_installed_patch_is_rejected(patcher, sources):
    result = patcher.patch_sources(sources)
    result[DISPATCH] = result[DISPATCH].replace('ultron_topic_queue.worker_host', 'other_worker')
    with pytest.raises(ValueError):
        patcher.patch_sources(result)


@pytest.fixture
def adapter_stub(monkeypatch):
    calls = []
    adapter = ModuleType('ultron_topic_queue.gateway_adapter')
    adapter.admitted = True

    async def admit(instance, event):
        calls.append(('admit', event))
        return adapter.admitted

    async def control(instance, event):
        calls.append(('control', event))

    adapter.try_admit = admit
    adapter.control_command = control
    package = ModuleType('ultron_topic_queue')
    package.gateway_adapter = adapter
    monkeypatch.setitem(sys.modules, 'ultron_topic_queue', package)
    monkeypatch.setitem(sys.modules, 'ultron_topic_queue.gateway_adapter', adapter)
    commands = ModuleType('ultron_topic_queue.profile_commands')
    async def profile_command(instance, event):
        return False
    commands.handle = profile_command
    monkeypatch.setitem(sys.modules, 'ultron_topic_queue.profile_commands', commands)
    return adapter, calls


@pytest.mark.parametrize('command', [False, True])
@pytest.mark.parametrize('authorized', [False, True])
def test_telegram_hooks_follow_auth_and_preserve_native_fallback(
        patcher, sources, adapter_stub, command, authorized):
    adapter, calls = adapter_stub
    event = SimpleNamespace(text='/stop' if command else 'hello')
    message = SimpleNamespace(text=event.text)

    async def ensure(message):
        calls.append(('ensure', message))

    async def build(*args):
        calls.append(('build', event))
        return event

    async def handle(event):
        calls.append(('handle', event))

    instance = SimpleNamespace(
        _effective_update_message=lambda update: message,
        _is_user_authorized_from_message=lambda message: authorized,
        _log_blocked_user=lambda message: calls.append(('blocked', message)),
        _gate_or_observe=lambda *args: True,
        _should_process_message=lambda *args, **kwargs: True,
        _ensure_forum_commands=ensure, _build_triggered_event=build,
        _enqueue_text_event=lambda event: calls.append(('enqueue', event)),
        handle_message=handle, _SPLIT_THRESHOLD=4096)
    source = patcher.patch_sources(sources)[TELEGRAM]
    name = '_handle_command' if command else '_handle_text_message'
    function = load_function(source, name, {'MessageType': SimpleNamespace(TEXT='text', COMMAND='command')})
    asyncio.run(function(instance, SimpleNamespace(message=message), None))
    names = [name for name, _ in calls]
    if not authorized:
        assert names == ['blocked']
    elif command:
        assert names == ['ensure', 'build', 'control', 'handle']
    else:
        assert names == ['ensure', 'build', 'admit']
        calls.clear()
        adapter.admitted = False
        asyncio.run(function(instance, SimpleNamespace(message=message), None))
        assert [name for name, _ in calls] == ['ensure', 'build', 'admit', 'enqueue']


def test_worker_argv_changes_only_managed_task(patcher, sources, monkeypatch):
    constants = ModuleType('hermes_constants')
    constants.get_default_hermes_root = lambda: Path('/offline/default-home')
    monkeypatch.setitem(sys.modules, 'hermes_constants', constants)
    namespace = {'sys': sys, '_resolve_hermes_argv': lambda: ['hermes'],
                 '_resolve_worker_cli_toolsets': lambda home: ['read']}
    source = patcher.patch_sources(sources)[DISPATCH]
    patched = load_function(source, '_worker_argv', namespace)
    original = load_function(sources[DISPATCH], '_worker_argv', namespace)
    task = SimpleNamespace(created_by='operator', id='t_abcd', current_run_id=17,
                           skills=['audit'], model_override=None, reasoning_effort=None)
    assert patched(task, 'greg', '/profile/greg') == original(task, 'greg', '/profile/greg')
    task.created_by = 'topic_queue'
    assert patched(task, 'greg', '/profile/greg') == [
        sys.executable, '-m', 'ultron_topic_queue.worker_host', '--task', 't_abcd',
        '--run', '17', '--home', '/offline/default-home']
    for name in ('_default_spawn', '_restart_safe_worker_argv'):
        assert ast.dump(function_node(source, name)) == ast.dump(function_node(sources[DISPATCH], name))


def test_watcher_tick_is_inside_dispatch_allowed_branch(patcher, sources):
    node = function_node(patcher.patch_sources(sources)[WATCHER], '_kanban_dispatcher_watcher')
    branch = next(item for item in ast.walk(node) if isinstance(item, ast.If)
                  and '_kanban_dispatch_allowed' in ast.unparse(item.test))
    assert 'ultron_topic_queue' not in ast.unparse(ast.Module(body=branch.body, type_ignores=[]))
    allowed = ast.unparse(ast.Module(body=branch.orelse, type_ignores=[]))
    assert allowed.index('await _ultron_topic_queue.tick(self)') < allowed.index('dispatcher.tick_once')


def test_native_database_guards_do_not_change_function_bodies(patcher, sources):
    source = patcher.patch_sources(sources)[DATABASE]
    for name in ('complete_task', 'edit_task', 'archive_task', 'delete_task', 'delete_archived_task'):
        node = function_node(source, name)
        expected = 'guard_completion' if name == 'complete_task' else 'guard_mutation'
        assert [ast.unparse(item) for item in node.decorator_list] == [expected]
        node.decorator_list = []
        assert ast.dump(node) == ast.dump(function_node(sources[DATABASE], name))


def test_native_notifier_skips_managed_cards_only(patcher, sources):
    function = load_function(patcher.patch_sources(sources)[NOTIFIER], 'collect_board', {
        '_kbc': lambda: SimpleNamespace(connect=lambda **kw: SimpleNamespace(close=lambda: None)),
        '_kbn': lambda: SimpleNamespace(list_notify_subs=lambda *a, **kw:
            [dict(task_id='managed'), dict(task_id='ordinary')]),
    })
    instance = SimpleNamespace(_board_has_subs=lambda slug: True, gc_due=False,
        notifier_profiles=None, include_unowned=True, deliveries=[],
        kb=SimpleNamespace(get_task=lambda conn, task_id: SimpleNamespace(
            created_by='topic_queue' if task_id == 'managed' else 'operator')),
        _claim_for_sub=lambda conn, slug, sub: sub['task_id'])
    function(instance, 'ultron-topics')
    assert instance.deliveries == ['ordinary']
