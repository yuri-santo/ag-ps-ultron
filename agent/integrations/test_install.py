import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml

from integrations.install_local import configure, stage_plugin, worker_source


def test_configuration_preserves_all_other_values_and_is_idempotent():
    original = {'plugins': {'enabled': ['old'], 'entries': {'old': {'keep': True}}},
                'platform_toolsets': {'cli': ['web'], 'telegram': ['memory'], 'cron': []},
                'model': {'default': 'unchanged'}, 'personal': 'private'}
    result = configure(original)
    assert original['plugins']['enabled'] == ['old']
    assert result['model'] == original['model'] and result['personal'] == 'private'
    assert result['plugins']['entries'] == original['plugins']['entries']
    assert result['plugins']['enabled'] == ['old', 'ultron_adoption']
    for tools in result['platform_toolsets'].values():
        assert tools.count('ultron_adoption') == 1
    assert configure(result) == result


def test_unrecognized_worker_is_never_patched():
    with pytest.raises(ValueError, match='worker'):
        worker_source('def execute(request): pass\n')


def test_staged_plugin_imports_without_source_path_hacks(tmp_path, monkeypatch):
    plugin = stage_plugin(tmp_path / 'ultron_adoption')
    name = 'staged_adoption_test'
    spec = importlib.util.spec_from_file_location(name, plugin / '__init__.py',
                                                submodule_search_locations=[str(plugin)])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    calls = []
    base = tmp_path / 'home'
    (base / 'integrations/adoption').mkdir(parents=True)
    (base / 'integrations/adoption/runtime.json').write_text(json.dumps({'skills': {}, 'image': ''}))
    monkeypatch.setattr(module, 'BASE_HOME', base)
    monkeypatch.setitem(sys.modules, 'hermes_constants', SimpleNamespace(get_hermes_home=lambda: base))
    ctx = SimpleNamespace(register_tool=lambda **kw: calls.append(kw),
                          register_system_prompt_section=lambda *a, **k: None)
    module.register(ctx)
    assert {c['name'] for c in calls} == {'adoption_status', 'adoption_skill_audit', 'adoption_caption_import'}
    status = next(c for c in calls if c['name'] == 'adoption_status')
    assert json.loads(status['handler']({}))['tiktok_shop'] == 'blocked_by_owner'


def test_worker_registers_only_contextual_capabilities(tmp_path, monkeypatch):
    plugin = stage_plugin(tmp_path / 'worker_plugin')
    name = 'staged_worker_plugin_test'
    spec = importlib.util.spec_from_file_location(name, plugin / '__init__.py',
                                                submodule_search_locations=[str(plugin)])
    integrations = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, integrations)
    spec.loader.exec_module(integrations)
    base = tmp_path / 'home'
    (base / 'integrations/adoption').mkdir(parents=True)
    (base / 'integrations/adoption/runtime.json').write_text(json.dumps({'skills': {}, 'image': ''}))
    for profile, expected in [('mrrobot', {'adoption_status', 'adoption_skill_audit'}),
                              ('dona', {'adoption_status', 'adoption_caption_import'}),
                              ('maquiavel', {'adoption_status', 'adoption_caption_import'}),
                              ('money', {'adoption_status', 'adoption_marketing_guide'}), ('greg', set())]:
        calls = []
        toolset, prompt = integrations.register_worker_tools(lambda **kw: calls.append(kw),
            profile, base / 'profiles' / profile, base)
        assert {c['name'] for c in calls} == expected
        assert bool(toolset) == bool(expected)
        assert ('adoption_' in prompt) == bool(expected)


def install_fixture(tmp_path, monkeypatch):
    from integrations import install_local as module
    home = tmp_path / 'home'
    worker = home / 'plugins/ultron_team/worker.py'
    worker.parent.mkdir(parents=True)
    worker.write_text('original worker')
    config = home / 'config.yaml'
    config.write_text(yaml.safe_dump({'platform_toolsets': {'cli': [], 'telegram': [], 'cron': []},
                                      'model': {'default': 'preserved'}}))
    monkeypatch.setattr(module, 'worker_source', lambda s: s + '\n# patched')
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='sha256:'+'a'*64))
    return module, home, worker, config


def test_install_has_private_backup_and_complete_package(tmp_path, monkeypatch):
    module, home, worker, config = install_fixture(tmp_path, monkeypatch)
    before = config.read_bytes()
    backup = tmp_path / 'backup'
    result = module.install(home, 'sha256:'+'a'*64, backup)
    assert result['catalog_count'] == 0
    assert (backup / 'config.yaml').read_bytes() == before
    assert backup.stat().st_mode & 0o777 == 0o700
    assert (backup / 'config.yaml').stat().st_mode & 0o777 == 0o600
    assert (home / 'plugins/ultron_adoption/skill_audit.py').is_file()
    assert (home / 'plugins/ultron_adoption/import_transcriptonic.py').is_file()
    assert yaml.safe_load(config.read_text())['model']['default'] == 'preserved'


@pytest.mark.parametrize('changed', ['config', 'worker'])
def test_config_edit_during_stage_is_preserved(tmp_path, monkeypatch, changed):
    module, home, worker, config = install_fixture(tmp_path, monkeypatch)
    stage = module.stage_plugin
    target = config if changed == 'config' else worker
    def concurrent_edit(path):
        target.write_text('newer: user edit\n')
        return stage(path)
    monkeypatch.setattr(module, 'stage_plugin', concurrent_edit)
    with pytest.raises(RuntimeError, match='changed'):
        module.install(home, 'sha256:'+'a'*64, tmp_path / 'backup')
    assert target.read_text() == 'newer: user edit\n'


def test_failure_rolls_back_applied_files(tmp_path, monkeypatch):
    module, home, worker, config = install_fixture(tmp_path, monkeypatch)
    before = config.read_bytes()
    write = module.atomic_write
    failed = False
    def failing_write(path, content):
        nonlocal failed
        if path == worker and not failed:
            failed = True
            raise OSError('disk error')
        write(path, content)
    monkeypatch.setattr(module, 'atomic_write', failing_write)
    with pytest.raises(OSError):
        module.install(home, 'sha256:'+'a'*64, tmp_path / 'backup')
    assert config.read_bytes() == before and worker.read_text() == 'original worker'
    assert not (home / 'plugins/ultron_adoption/__init__.py').exists()


@pytest.mark.parametrize('code,state,allowed', [(0,'inactive',True),(0,'failed',True),
    (0,'active',False),(0,'deactivating',False),(1,'',False),(0,'',False)])
def test_gateway_state_gate_fails_closed(code, state, allowed):
    from integrations.install_local import require_stopped
    runner = lambda *a, **k: SimpleNamespace(returncode=code, stdout=state)
    if allowed:
        require_stopped(runner)
    else:
        with pytest.raises(RuntimeError):
            require_stopped(runner)
