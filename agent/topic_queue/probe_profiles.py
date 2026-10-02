"""Read-only installed profile, persona and Telegram command-menu verification."""
import argparse
import asyncio
import json
from pathlib import Path


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--telegram-menu', action='store_true')
    args = parser.parse_args()
    from ultron_topic_queue.runtime import Runtime
    from ultron_topic_queue.profile_selection import Selection
    from hermes_cli.profiles import get_active_profile, read_profile_meta
    from gateway.status import read_runtime_status
    runtime = Runtime.from_home('/root/.hermes')
    selection = Selection(runtime.home, runtime.roster)
    status = read_runtime_status() or {}
    print(json.dumps(dict(primary_internal=get_active_profile(),
        primary_display=read_profile_meta(runtime.home).get('display_name'),
        selected=[selection.current(scope) for scope in runtime.configured_scopes],
        persistent_profiles=runtime.config.get('persistent_profiles'),
        gateway=status.get('gateway_state'),
        persona_blocks=sum('<!-- PROFILE-VOICE v1 -->' in
            ((runtime.home if p == 'ultron' else runtime.home / 'profiles' / p) / 'SOUL.md').read_text()
            for p in runtime.roster))))
    if args.telegram_menu:
        from dotenv import dotenv_values
        from telegram import Bot, BotCommandScopeAllPrivateChats
        values = dotenv_values(runtime.home / '.env')
        async with Bot(values['TELEGRAM_BOT_TOKEN']) as bot:
            commands = await bot.get_my_commands(scope=BotCommandScopeAllPrivateChats())
        names = {command.command for command in commands}
        expected = set(runtime.roster) | {'perfil', 'perfis'}
        print(json.dumps(dict(menu_profiles_present=sorted(expected & names), missing=sorted(expected - names))))


if __name__ == '__main__':
    asyncio.run(main())
