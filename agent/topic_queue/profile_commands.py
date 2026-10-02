"""Exact profile commands on the already-authenticated native Telegram adapter."""
import asyncio
import copy
import json
import logging
from pathlib import Path

from .admission import Scope
from .contract import require
from .profile_selection import Selection, parse_command


def settings():
    home = Path('/root/.hermes')
    path = home / 'topic-queue/config.json'
    return home, json.loads(path.read_text()) if path.is_file() else {}


def source_selection(adapter, source):
    from .gateway_adapter import _scope
    home, config = settings()
    scope = _scope(adapter, source)
    if not config.get('persistent_profiles') or scope not in [Scope(**s) for s in config.get('scopes', [])]:
        return None
    return Selection(home, config['roster']), scope, config


def apply_source(adapter, source):
    # build_source already resolved static native routes and dedicated bots.
    if getattr(source, 'profile', None) or getattr(source, 'profile_route_rejected', False):
        return
    selected = source_selection(adapter, source)
    if not selected:
        return
    store, scope, config = selected
    profile = store.current(scope)
    if not store.available(profile):
        source.profile_route_rejected = True
        return
    source.profile = 'default' if profile == 'ultron' else profile
    source._ultron_selected_profile = profile


def menu(adapter, original, maximum):
    home, config = settings()
    accounts = {str(s['account_id']) for s in config.get('scopes', [])}
    if not config.get('persistent_profiles') or str(getattr(adapter._bot, 'id', '')) not in accounts:
        return original
    additions = [('ultron', 'Conversar com Ultron'), ('perfil', 'Mostrar o perfil ativo'),
                 ('perfis', 'Listar os perfis')]
    additions += [(p, 'Conversar com ' + config.get('authors', {}).get(p, p))
                  for p in config['roster'] if p != 'ultron']
    names = {p for p, _ in additions}
    return (additions + [p for p in original if p[0] not in names])[:maximum]


async def handle(adapter, event):
    from .gateway_adapter import _scope, send_part, _failed_admission, try_admit, _native_controls_pending
    if getattr(event, 'internal', False) or getattr(event, 'allow_gateway_control', False) is not True:
        return False
    raw = getattr(event, 'raw_message', None)
    if getattr(raw, 'forward_origin', None):
        return False
    runner = getattr(adapter, 'gateway_runner', None)
    if runner is None:
        return False
    selected = await asyncio.to_thread(source_selection, adapter, event.source)
    if not selected:
        return False
    store, scope, config = selected
    command = parse_command(event.text, config['roster'], getattr(adapter._bot, 'username', ''))
    if not command:
        return False
    try:
        candidate = copy.copy(event)
        candidate.source = copy.copy(event.source)
        candidate.metadata = copy.deepcopy(getattr(event, 'metadata', None))
        adapter._canonicalize(candidate.source)
        with runner._profile_scope_for_source(candidate.source):
            admitted = await runner._hm_admit_event(candidate)
            if admitted is None:
                adapter._accept_update()
                return True
            candidate, source, internal = admitted
            require(not internal and _scope(adapter, source) == scope, 'Command identity changed')
            name, question = command
            if name in ('perfil', 'profile', 'perfis'):
                current = await asyncio.to_thread(store.current, scope)
                text = 'Perfil ativo: ' + config.get('authors', {}).get(current, current) + '.'
                if name == 'perfis':
                    text += '\n\n' + '\n'.join('/' + p + ' - ' + config.get('authors', {}).get(p, p)
                                                for p in config['roster'])
            else:
                if not await asyncio.to_thread(store.available, name):
                    text = 'Esse perfil esta indisponivel. A selecao anterior foi mantida.'
                elif _native_controls_pending(runner, runner._session_key_for_source(source)):
                    text = 'Conclua a confirmacao pendente antes de trocar de perfil.'
                else:
                    # Persist before acknowledging, and snapshot a same-line request
                    # before another command can change its target.
                    current = await asyncio.to_thread(store.choose, scope, name, event.message_id)
                    if question:
                        current = await asyncio.to_thread(store.snapshot, scope, event.message_id)
                        from gateway.platforms.base import MessageType
                        from gateway.session_identity import clear_identity
                        candidate.text = question
                        candidate.message_type = MessageType.TEXT
                        clear_identity(candidate.source)
                        candidate.source.profile = 'default' if current == 'ultron' else current
                        candidate.source._ultron_selected_profile = current
                        candidate.reply_to_message_id = None
                        if await try_admit(adapter, candidate):
                            return True
                        await adapter.handle_message(candidate)
                        return True
                    text = 'Perfil ativo: ' + config.get('authors', {}).get(current, current) + '.'
            # This is a deterministic command receipt, not model-generated content.
            adapter._accept_update()
            try:
                await send_part(adapter, scope, text)
            except Exception as exc:
                logging.getLogger(__name__).warning('Profile command persisted; receipt unavailable (%s)', type(exc).__name__)
            return True
    except Exception as exc:
        return _failed_admission(adapter, exc)
