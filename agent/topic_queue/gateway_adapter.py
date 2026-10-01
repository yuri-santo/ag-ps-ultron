"""Authenticated original-message admission and one-attempt native Telegram I/O."""
import asyncio
import copy
import logging

try:
    from .admission import Scope
    from .contract import QueueError, require
except ImportError:
    from admission import Scope
    from contract import QueueError, require


logger = logging.getLogger(__name__)
SEND_TIMEOUT_SECONDS = 45


class TransportNotSent(QueueError):
    """A local preflight refusal before any Telegram request was attempted."""


def _runtime():
    if __package__:
        from .runtime import Runtime
    else:
        from runtime import Runtime
    return Runtime.from_home()


def _value(value):
    return getattr(value, 'value', value)


def _plain_request(event):
    text = getattr(event, 'text', None)
    raw = getattr(event, 'raw_message', None)
    if getattr(raw, 'forward_origin', None) or any(
            _value(getattr(e, 'type', None)) in ('blockquote', 'expandable_blockquote')
            for e in (getattr(raw, 'entities', None) or ())):
        return False
    return (
        _value(getattr(event, 'message_type', None)) == 'text'
        and isinstance(text, str) and bool(text.strip())
        and not text.lstrip().startswith(('/', '!'))
        and not event.get_command()
        and not getattr(event, 'internal', False)
        and getattr(event, 'allow_gateway_control', False) is True
        and not getattr(event, 'media_urls', None)
        and not getattr(event, 'media_types', None)
        and not getattr(event.source, 'is_bot', False)
        and _value(event.source.platform) == 'telegram'
    )


def _scope(adapter, source):
    bot = getattr(adapter, '_bot', None)
    account = getattr(bot, 'id', None)
    require(type(account) is int and account > 0, 'Telegram bot identity unavailable')
    require(source.user_id is not None and source.chat_id is not None,
            'Telegram origin identity unavailable')
    return Scope('telegram', str(account), str(source.user_id), str(source.chat_id),
                 str(source.thread_id) if source.thread_id is not None else '')


def _native_controls_pending(runner, key):
    from tools import clarify_gateway, slash_confirm
    from tools.approval import has_blocking_approval

    state = runner._peek_session_state(key)
    return bool(
        (state is not None and state.persistent.update_prompt_pending)
        or clarify_gateway.get_pending_for_session(key, include_choice_prompts=True) is not None
        or slash_confirm.get_pending(key)
        or has_blocking_approval(key)
    )


def _failed_admission(adapter, exc):
    # PTB's core callback checks failed/not-accepted and stops later observer groups.
    # Raising here would enter native error callbacks, which can mark the update accepted.
    adapter._fail_update_preparation()
    logger.error('Topic queue admission failed (%s); update not acknowledged', type(exc).__name__)
    return True


async def try_admit(adapter, event):
    """True consumes this callback; only durable admission marks its update accepted.

    Install before Telegram text batching, while its native update claim is active.
    False preserves the original envelope for native control/command/media handling.
    """
    if not _plain_request(event):
        return False
    runner = (getattr(getattr(adapter, '_message_handler', None), '__self__', None)
              or getattr(adapter, 'gateway_runner', None))
    if runner is None:
        return False
    if any(getattr(runner, attr, False) for attr in
           ('_draining', '_external_drain_active', '_startup_restore_in_progress')):
        return False
    candidate = copy.copy(event)
    candidate.source = copy.copy(event.source)
    candidate.metadata = copy.deepcopy(getattr(event, 'metadata', None))
    candidate.media_urls = list(getattr(event, 'media_urls', ()) or ())
    candidate.media_types = list(getattr(event, 'media_types', ()) or ())
    try:
        adapter._canonicalize(candidate.source)
        adapter._apply_topic_recovery(candidate)
        with runner._profile_scope_for_source(candidate.source):
            runtime = await asyncio.to_thread(_runtime)
            if not getattr(runtime, 'enabled', True):
                return False
            scope = _scope(adapter, candidate.source)
            if scope not in runtime.configured_scopes:
                return False
            reply = getattr(candidate, 'reply_to_message_id', None)
            if reply and not await asyncio.to_thread(runtime.knows_reply, scope, reply):
                return False
            key = runner._session_key_for_source(candidate.source)
            if _native_controls_pending(runner, key):
                return False
            admitted = await runner._hm_admit_event(candidate)
            if admitted is None:
                adapter._accept_update()
                return True
            candidate, source, is_internal = admitted
            require(not is_internal and _plain_request(candidate), 'Native ingress changed request kind')
            require(_scope(adapter, source) == scope, 'Native ingress changed origin scope')
            if runner._hm_estop_gate(candidate, source, is_internal) is not None:
                return False
            key = runner._session_key_for_source(source)
            if _native_controls_pending(runner, key):
                return False
            require(isinstance(candidate.message_id, str) and bool(candidate.message_id),
                    'Telegram message identity unavailable')
            receipt = await asyncio.to_thread(
                runtime.admit, scope, candidate.text, candidate.message_id,
                reply_to=getattr(candidate, 'reply_to_message_id', None))
            require(bool(receipt), 'Durable admission receipt unavailable')
        adapter._accept_update()
        return True
    except Exception as exc:
        return _failed_admission(adapter, exc)


async def control_command(adapter, event):
    """Cancel scoped pending topics before native /stop or /new continues."""
    if (str(event.text).strip().lower() not in ('/stop', '/new')
            or getattr(event, 'internal', False)
            or getattr(event, 'allow_gateway_control', False) is not True):
        return
    runner = getattr(adapter, 'gateway_runner', None)
    if runner is None:
        return
    candidate = copy.copy(event)
    candidate.source = copy.copy(event.source)
    candidate.metadata = copy.deepcopy(getattr(event, 'metadata', None))
    with runner._profile_scope_for_source(candidate.source):
        runtime = await asyncio.to_thread(_runtime)
        scope = _scope(adapter, candidate.source)
        if not getattr(runtime, 'enabled', True) or scope not in runtime.configured_scopes:
            return
        admitted = await runner._hm_admit_event(candidate)
        if admitted is None:
            return
        candidate, source, internal = admitted
        require(not internal and _scope(adapter, source) == scope, 'Command scope changed')
        await asyncio.to_thread(runtime.control_scope, scope, 'cancelled')


def _transport_preflight(adapter, scope, text):
    bot = getattr(adapter, '_bot', None)
    if (scope.platform != 'telegram' or bot is None
            or str(getattr(bot, 'id', '')) != scope.account_id
            or getattr(adapter, '_send_path_degraded', False)
            or getattr(bot, 'rate_limiter', None) is not None):
        raise TransportNotSent('Native Telegram transport unavailable for this account')
    if (not isinstance(text, str) or not text.strip()
            or len(text.encode('utf-16-le')) // 2 > 4096):
        raise TransportNotSent('Frozen delivery part must fit one Telegram message')
    return bot


async def send_part(adapter, scope, text, reply_to=None):
    """Send frozen plain text once; return only a verified Telegram message ID.

    Any request exception or missing receipt is uncertain and must not be retried.
    TransportNotSent is reserved for refusals before calling the native bot.
    """
    bot = _transport_preflight(adapter, scope, text)
    try:
        chat_id = int(scope.chat_id)
        reply_id = int(reply_to) if reply_to is not None else None
        thread_kwargs = adapter._thread_kwargs_for_send(
            scope.chat_id, scope.thread_id, reply_to_message_id=reply_id, reply_to_mode='all')
    except (TypeError, ValueError) as exc:
        raise TransportNotSent('Invalid approved Telegram destination') from exc
    async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
        async with adapter._chat_send_lock(scope.chat_id):
            if adapter._send_flood_cooldown_remaining(scope.chat_id) is not None:
                raise TransportNotSent('Telegram flood cooldown active')
            delay = adapter._chat_outbound_slot_remaining(scope.chat_id)
            if delay > 0:
                await asyncio.sleep(delay)
            _transport_preflight(adapter, scope, text)
            require(adapter._bot is bot, 'Native Telegram transport changed before send')
            adapter._hold_chat_outbound_slot(scope.chat_id)
            message = await bot.send_message(
                chat_id=chat_id, text=text, parse_mode=None, disable_web_page_preview=True,
                reply_to_message_id=reply_id, **thread_kwargs,
                read_timeout=30, write_timeout=30, connect_timeout=10, pool_timeout=10)
    message_id = getattr(message, 'message_id', None)
    require(type(message_id) is int and message_id > 0, 'Telegram receipt is missing a message ID')
    require(str(getattr(getattr(message, 'chat', None), 'id', '')) == scope.chat_id,
            'Telegram receipt destination mismatch')
    return str(message_id)


async def tick(gateway):
    """Run outbox work from the existing gateway Kanban tick."""
    runtime = await asyncio.to_thread(_runtime)
    if not getattr(runtime, 'enabled', True):
        return None
    return await runtime.drain(gateway)
