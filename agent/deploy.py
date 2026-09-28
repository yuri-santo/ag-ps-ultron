"""Scoped, backed-up installation; run on the existing Hermes VPS."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

PROFILES = ('gmail', 'easysapers', 'reunioes')
START = '<!-- ultron-team-20260913:start -->'
END = '<!-- ultron-team-20260913:end -->'


def profile_config(base, profile):
    if profile not in PROFILES:
        raise ValueError('invalid_profile')
    domain = 'ultron_meetings' if profile == 'reunioes' else 'ultron_mail'
    result = {key: copy.deepcopy(base[key]) for key in ('model', 'fallback_providers', '_config_version') if key in base}
    result.update({
        'agent': {'max_turns': 30, 'reasoning_effort': 'max', 'verify_on_stop': True},
        'display': {'personality': profile},
        'terminal': {'backend': 'local', 'cwd': str(Path('/root/.hermes/profiles') / profile / 'workspace')},
        'memory': {'memory_enabled': True, 'user_profile_enabled': True, 'memory_char_limit': 2200,
                   'user_char_limit': 1375},
        'platform_toolsets': {platform: [domain, 'memory'] for platform in ('cli', 'telegram', 'api_server')},
        'plugins': {'enabled': ['ultron_team'], 'entries': {'ultron_team': {'settings': {'base_home': '/root/.hermes'}}}},
        'skills': {'external_dirs': []}, 'mcp_servers': {},
        'voice': {'auto_tts': False},
        'tool_loop_guardrails': {'hard_stop_enabled': True, 'non_interactive_hard_stop_enabled': True},
    })
    return result


def activate_config(base):
    result = copy.deepcopy(base)
    plugins = result.setdefault('plugins', {})
    enabled = plugins.setdefault('enabled', [])
    if 'ultron_team' not in enabled:
        enabled.append('ultron_team')
    settings = plugins.setdefault('entries', {}).setdefault('ultron_team', {}).setdefault('settings', {})
    settings.setdefault('base_home', '/root/.hermes')
    settings.setdefault('voice_enabled', False)
    plugins.setdefault('entries', {}).setdefault('meeting_copilot', {}).setdefault('settings', {})['team_specialist'] = True
    for platform, values in result.setdefault('platform_toolsets', {}).items():
        if isinstance(values, list) and 'ultron_team' not in values:
            values.append('ultron_team')
    return result


def update_soul(old, content):
    if START in old:
        prefix, remaining = old.split(START, 1)
        if END not in remaining:
            raise ValueError('broken_managed_soul_section')
        _, suffix = remaining.split(END, 1)
        old = prefix.rstrip() + suffix
    return old.rstrip() + '\n\n' + START + '\n' + content.strip() + '\n' + END + '\n'


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.ultron-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['stage', 'activate'])
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    home = Path('/root/.hermes')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = home / 'backups' / ('ultron-team-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    manifest = {'action': args.action, 'backup': str(backup), 'changed': [], 'created': [], 'existing_specialists': {}}
    for name in ('bigode', 'thor', 'hercules'):
        manifest['existing_specialists'][name] = {filename: hashlib.sha256((home/'profiles'/name/filename).read_bytes()).hexdigest()
            for filename in ('SOUL.md', 'config.yaml')}
    def preserve(path):
        if path.exists():
            destination = backup / path.relative_to(home)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
                os.chmod(destination, 0o600)
            manifest['changed'].append(str(path))
        else:
            manifest['created'].append(str(path))
    config = yaml.safe_load((home/'config.yaml').read_text())
    def save_yaml(path, value):
        rendered = yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
        yaml.safe_load(rendered)
        atomic_text(path, rendered)
    if args.action == 'stage':
        plugin = home/'plugins/ultron_team'
        if plugin.exists() and not (plugin/'.ultron-team-managed').exists():
            raise RuntimeError('unowned_plugin_exists')
        for name in PROFILES:
            profile = home/'profiles'/name
            if profile.exists() and not (profile/'.ultron-team-managed').exists():
                raise RuntimeError('unowned_profile_exists: '+name)
        preserve(plugin)
        shutil.copytree(source/'plugins/ultron_team', plugin, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(source/'plugins/ultron_team/personality.md', plugin/'personality.md')
        atomic_text(plugin/'.ultron-team-managed', '20260913\n')
        for name in PROFILES:
            profile = home/'profiles'/name
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            for directory in ('workspace', 'memories', 'data', 'plugins'):
                (profile/directory).mkdir(exist_ok=True, mode=0o700)
            for filename in ('config.yaml', 'SOUL.md'):
                preserve(profile/filename)
            save_yaml(profile/'config.yaml', profile_config(config, name))
            atomic_text(profile/'SOUL.md', (source/'profiles'/name/'SOUL.md').read_text(encoding='utf-8-sig'))
            local_plugin = profile/'plugins/ultron_team'
            shutil.copytree(plugin, local_plugin, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            atomic_text(profile/'.ultron-team-managed', '20260913\n')
    else:
        for name in PROFILES:
            if not (home/'profiles'/name/'.ultron-team-managed').is_file():
                raise RuntimeError('stage_required')
        preserve(home/'config.yaml')
        preserve(home/'SOUL.md')
        save_yaml(home/'config.yaml', activate_config(config))
        atomic_text(home/'SOUL.md', update_soul((home/'SOUL.md').read_text(),
                    (source/'plugins/ultron_team/personality.md').read_text(encoding='utf-8-sig')))
        meeting = home/'plugins/meeting_copilot/__init__.py'
        original = meeting.read_text()
        old = """        result = await ctx.llm.acomplete(messages,max_tokens=8192,timeout=90,
                                         purpose='meeting_copilot')
        return result.text"""
        new = """        if not ctx.get_config('team_specialist',False):
            result = await ctx.llm.acomplete(messages,max_tokens=8192,timeout=90,
                                             purpose='meeting_copilot')
            return result.text
        import json, sys
        plugin_path = str(Path(get_hermes_home())/'plugins')
        if plugin_path not in sys.path:
            sys.path.insert(0,plugin_path)
        from ultron_team.bridge import Bridge
        result = await asyncio.to_thread(Bridge(Path(get_hermes_home())).dispatch,
            'reunioes', 'Execute o pedido de análise do copiloto com o formato solicitado. '
            'Use os registros e fontes fornecidos, sem inventar fatos ou decisões.',
            context=json.dumps(messages,ensure_ascii=False))
        if result.get('status')!='ok':
            raise RuntimeError('meeting_specialist_unavailable')
        return result['answer']"""
        guard_old = "            command = parse_command(text)"
        guard_new = """            import sys
            plugin_path = str(Path(get_hermes_home())/'plugins')
            if plugin_path not in sys.path:
                sys.path.insert(0,plugin_path)
            from ultron_team.delivery import explicit_mail_request
            if explicit_mail_request(text):
                return
            command = parse_command(text)"""
        if old in original:
            modified = original.replace(old, new, 1).replace(guard_old, guard_new, 1)
            compile(modified, str(meeting), 'exec')
            preserve(meeting)
            atomic_text(meeting, modified)
        elif 'meeting_specialist_unavailable' not in original:
            raise RuntimeError('meeting_plugin_changed_review_required')
    for name, fingerprints in manifest['existing_specialists'].items():
        for filename, before in fingerprints.items():
            assert hashlib.sha256((home/'profiles'/name/filename).read_bytes()).hexdigest()==before
    atomic_text(backup/'manifest.json', json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
