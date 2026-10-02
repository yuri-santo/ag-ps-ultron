import asyncio
import importlib
import json
from pathlib import Path
import sys
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def rig(tmp_path, monkeypatch):
    package = ModuleType('profile_test_package')
    package.__path__ = [str(Path(__file__).parent)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    command = importlib.import_module('profile_test_package.profile_commands')
    gateway = importlib.import_module('profile_test_package.gateway_adapter')
    config = dict(persistent_profiles=True, roster={'ultron': 'Principal', 'pink': 'Memoria'},
                  authors={'ultron': 'Ultron', 'pink': 'Pink'},
                  scopes=[dict(platform='telegram', account_id='1', owner_id='2', chat_id='2')])
    for directory in (tmp_path, tmp_path / 'profiles/pink'):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'config.yaml').write_text('test')
        (directory / 'SOUL.md').write_text('test')
    monkeypatch.setattr(command, 'settings', lambda: (tmp_path, config))
    calls = []
    async def send(*args, **kw):
        calls.append(args[2])
        return '123'
    monkeypatch.setattr(gateway, 'send_part', send)
    monkeypatch.setattr(gateway, '_native_controls_pending', lambda *args: False)
    runner = SimpleNamespace(authorized=True, _profile_scope_for_source=lambda s: nullcontext(),
                             _session_key_for_source=lambda s: 'session')
    async def admit(event):
        return (event, event.source, False) if runner.authorized else None
    runner._hm_admit_event = admit
    adapter = SimpleNamespace(gateway_runner=runner, _bot=SimpleNamespace(id=1, username='bot'),
        _canonicalize=lambda s: None, _accept_update=lambda: None,
        _fail_update_preparation=lambda: calls.append('failed'))
    def event(text, message_id='10', owner='2'):
        return SimpleNamespace(text=text, message_id=message_id, internal=False, allow_gateway_control=True,
            source=SimpleNamespace(profile=None, platform='telegram', user_id=owner, chat_id='2', thread_id=None),
            metadata={}, raw_message=None)
    return command, adapter, runner, event, calls


def test_persistent_command_report_and_native_message_profile(rig):
    command, adapter, runner, event, calls = rig
    assert asyncio.run(command.handle(adapter, event('/pink')))
    assert calls == ['Perfil ativo: Pink.']
    next_event = event('oi', '11')
    command.apply_source(adapter, next_event.source)
    assert next_event.source.profile == 'pink'
    assert asyncio.run(command.handle(adapter, event('/perfil', '12')))
    assert calls[-1] == 'Perfil ativo: Pink.'
    assert asyncio.run(command.handle(adapter, event('/ultron', '13')))
    next_event = event('oi', '14')
    command.apply_source(adapter, next_event.source)
    assert next_event.source.profile == 'default'


def test_wrong_owner_and_native_denial_do_not_change_selection(rig):
    command, adapter, runner, event, calls = rig
    assert asyncio.run(command.handle(adapter, event('/pink', owner='outsider'))) is False
    runner.authorized = False
    assert asyncio.run(command.handle(adapter, event('/pink')))
    runner.authorized = True
    asyncio.run(command.handle(adapter, event('/perfil', '12')))
    assert calls == ['Perfil ativo: Ultron.']


def test_native_explicit_route_wins(rig):
    command, adapter, runner, event, calls = rig
    asyncio.run(command.handle(adapter, event('/pink')))
    source = event('oi').source
    source.profile = 'cris'
    command.apply_source(adapter, source)
    assert source.profile == 'cris'


def test_menu_exposes_profile_commands_without_duplicate_names(rig):
    command, adapter, runner, event, calls = rig
    result = command.menu(adapter, [('stop', 'Stop'), ('pink', 'old')], 60)
    assert len([item for item in result if item[0] == 'pink']) == 1
    assert ('ultron', 'Conversar com Ultron') in result
    assert ('stop', 'Stop') in result
