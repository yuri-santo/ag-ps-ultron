"""Gateway boundary tests with an offline Telegram transport."""
import asyncio
import importlib
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace

import pytest

from admission import Scope


SCOPE = Scope('telegram', '123', '456', '456')


class Event(SimpleNamespace):
    def get_command(self):
        return self.text.split()[0][1:] if self.text.startswith('/') else None


class Runner:
    def __init__(self):
        self.authorized = True
        self.paused = None
        self._draining = False
        self._external_drain_active = False
        self._startup_restore_in_progress = False
        self.auth_events = []

    async def _handle_message(self, event):
        raise AssertionError('Native agent must not run during queue admission')

    def _profile_scope_for_source(self, source):
        return nullcontext()

    async def _hm_admit_event(self, event):
        self.auth_events.append(event)
        event.metadata['native_auth'] = True
        event.source.profile = 'resolved'
        return (event, event.source, False) if self.authorized else None

    def _hm_estop_gate(self, event, source, is_internal):
        return self.paused

    def _session_key_for_source(self, source):
        return 'session'

    def _peek_session_state(self, key):
        return None


class Adapter:
    def __init__(self, runner):
        self._message_handler = runner._handle_message
        self.gateway_runner = runner
        self._bot = SimpleNamespace(id=123)
        self.platform = 'telegram'
        self.accepted = 0
        self.failed = 0
        self.in_lock = False
        self._send_path_degraded = False

    def _canonicalize(self, source):
        return None

    def _apply_topic_recovery(self, event):
        return None

    def _accept_update(self):
        self.accepted += 1

    def _fail_update_preparation(self):
        self.failed += 1

    @asynccontextmanager
    async def _chat_send_lock(self, chat_id):
        self.in_lock = True
        try:
            yield
        finally:
            self.in_lock = False

    def _thread_kwargs_for_send(self, chat_id, thread_id, **kwargs):
        return {'message_thread_id': int(thread_id) if thread_id not in ('', '1') else None}

    def _send_flood_cooldown_remaining(self, chat_id):
        return None

    def _chat_outbound_slot_remaining(self, chat_id):
        return 0

    def _hold_chat_outbound_slot(self, chat_id):
        assert self.in_lock


def event(**changes):
    value = Event(text='Do the request', message_type='text', internal=False,
                  allow_gateway_control=True, message_id='789', reply_to_message_id=None,
                  media_urls=[], media_types=[], metadata={},
                  source=SimpleNamespace(platform='telegram', user_id='456', chat_id='456',
                                         thread_id=None, is_bot=False, profile=None))
    value.__dict__.update(changes)
    return value


@pytest.fixture
def setup(monkeypatch):
    assert importlib.util.find_spec('gateway_adapter') is not None, 'Gateway bridge is missing'
    module = importlib.import_module('gateway_adapter')
    runtime = SimpleNamespace(configured_scopes=[SCOPE], records=[])

    def admit(scope, text, message_id, reply_to=None):
        runtime.records.append((scope, text, message_id, reply_to))
        return 'ingress'

    runtime.admit = admit
    runtime.knows_reply = lambda scope, message_id: message_id == '700'
    runtime.native_pending_reader = module._native_controls_pending
    monkeypatch.setattr(module, '_runtime', lambda: runtime)
    monkeypatch.setattr(module, '_native_controls_pending', lambda runner, key: False)
    runner = Runner()
    return module, runtime, runner, Adapter(runner)


def test_each_original_text_is_authenticated_persisted_and_acknowledged(setup):
    module, runtime, runner, adapter = setup
    first, second = event(), event(text='Another request', message_id='790', reply_to_message_id='700')
    assert asyncio.run(module.try_admit(adapter, first)) is True
    assert asyncio.run(module.try_admit(adapter, second)) is True
    assert [r[2] for r in runtime.records] == ['789', '790']
    assert runtime.records[1][3] == '700'
    assert len(runner.auth_events) == adapter.accepted == 2
    assert first.metadata == {} and first.source.profile is None


@pytest.mark.parametrize('changes', [
    {'text': '/stop'}, {'text': '!approve'}, {'message_type': 'command'},
    {'internal': True}, {'media_urls': ['private-image']}, {'message_type': 'voice'},
    {'allow_gateway_control': False},
])
def test_native_control_internal_and_media_events_are_unchanged(setup, changes):
    module, runtime, runner, adapter = setup
    original = event(**changes)
    assert asyncio.run(module.try_admit(adapter, original)) is False
    assert not runtime.records and not runner.auth_events and not adapter.accepted


def test_unconfigured_origin_keeps_native_path(setup):
    module, runtime, runner, adapter = setup
    original = event()
    original.source.user_id = '999'
    assert asyncio.run(module.try_admit(adapter, original)) is False
    assert not runtime.records and not runner.auth_events


def test_full_auth_rejection_never_reaches_queue(setup):
    module, runtime, runner, adapter = setup
    runner.authorized = False
    assert asyncio.run(module.try_admit(adapter, event())) is True
    assert not runtime.records and adapter.accepted == 1


def test_wrapped_native_message_handler_resolves_gateway_runner(setup):
    module, runtime, runner, adapter = setup
    adapter._message_handler = lambda value: value
    assert asyncio.run(module.try_admit(adapter, event())) is True
    assert len(runner.auth_events) == 1


def test_paused_and_pending_replies_stay_native(setup, monkeypatch):
    module, runtime, runner, adapter = setup
    runner.paused = 'Paused'
    assert asyncio.run(module.try_admit(adapter, event())) is False
    runner.paused = None
    monkeypatch.setattr(module, '_native_controls_pending', lambda runner, key: True)
    assert asyncio.run(module.try_admit(adapter, event())) is False
    assert not runtime.records and not adapter.accepted


def test_changed_native_hook_destination_fails_closed(setup):
    module, runtime, runner, adapter = setup

    async def redirected(original):
        original.source.chat_id = 'other-chat'
        return original, original.source, False

    runner._hm_admit_event = redirected
    assert asyncio.run(module.try_admit(adapter, event())) is True
    assert not runtime.records and adapter.failed == 1 and not adapter.accepted


def test_storage_failure_is_not_acknowledged_or_exposed(setup, caplog):
    module, runtime, runner, adapter = setup

    def failed(*args, **kwargs):
        raise OSError('sensitive-storage-secret')

    runtime.admit = failed
    assert asyncio.run(module.try_admit(adapter, event())) is True
    assert adapter.failed == 1 and adapter.accepted == 0
    assert 'sensitive-storage-secret' not in caplog.text


def test_send_one_frozen_part_with_native_lock_and_real_message_id(setup):
    module, runtime, runner, adapter = setup
    sent = []

    async def send_message(**kwargs):
        assert adapter.in_lock
        sent.append(kwargs)
        return SimpleNamespace(message_id=88, chat=SimpleNamespace(id=456))

    adapter._bot.send_message = send_message
    scope = Scope('telegram', '123', '456', '456', '9')
    assert asyncio.run(module.send_part(adapter, scope, 'Pink: [literal](text)', reply_to='789')) == '88'
    assert len(sent) == 1
    assert sent[0]['text'] == 'Pink: [literal](text)'
    assert sent[0]['parse_mode'] is None and sent[0]['disable_web_page_preview'] is True
    assert sent[0]['message_thread_id'] == 9 and sent[0]['reply_to_message_id'] == 789


@pytest.mark.parametrize('result', [None, SimpleNamespace(message_id=None),
                                   SimpleNamespace(message_id=12, chat=SimpleNamespace(id=999))])
def test_missing_or_wrong_transport_receipt_is_uncertain(setup, result):
    module, runtime, runner, adapter = setup
    calls = []

    async def send_message(**kwargs):
        calls.append(kwargs)
        return result

    adapter._bot.send_message = send_message
    with pytest.raises(Exception):
        asyncio.run(module.send_part(adapter, SCOPE, 'Pink: answer'))
    assert len(calls) == 1


def test_network_error_is_never_retried(setup):
    module, runtime, runner, adapter = setup
    calls = []

    async def send_message(**kwargs):
        calls.append(kwargs)
        raise TimeoutError('unknown delivery')

    adapter._bot.send_message = send_message
    with pytest.raises(TimeoutError):
        asyncio.run(module.send_part(adapter, SCOPE, 'Pink: answer'))
    assert len(calls) == 1


@pytest.mark.parametrize('text', ['', ' ', 'x' * 4097, '\U0001f600' * 2049],
                         ids=['empty', 'whitespace', 'long-ascii', 'long-utf16'])
def test_invalid_part_fails_before_network(setup, text):
    module, runtime, runner, adapter = setup
    with pytest.raises(Exception):
        asyncio.run(module.send_part(adapter, SCOPE, text))


def test_wrong_bot_fails_before_network(setup):
    module, runtime, runner, adapter = setup
    adapter._bot.id = 999
    with pytest.raises(Exception):
        asyncio.run(module.send_part(adapter, SCOPE, 'Pink: answer'))


def test_tick_delegates_to_runtime_drain(setup):
    module, runtime, runner, adapter = setup
    calls = []

    async def drain(gateway):
        calls.append(gateway)
        return {'delivered': 0}

    runtime.drain = drain
    assert asyncio.run(module.tick(runner)) == {'delivered': 0}
    assert calls == [runner]


def test_disabled_queue_leaves_native_message_untouched(setup):
    module, runtime, runner, adapter = setup
    runtime.enabled = False
    assert asyncio.run(module.try_admit(adapter, event())) is False
    assert not runtime.records and not runner.auth_events


def test_native_auth_gate_and_event_types_with_temporary_home(setup, tmp_path, monkeypatch):
    module, runtime, runner, adapter = setup
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'hermes'))
    base = pytest.importorskip('gateway.platforms.base')
    inbound = pytest.importorskip('gateway.run_inbound')
    session = importlib.import_module('gateway.session')
    runner.config = SimpleNamespace(multiplex_profiles=False)
    runner._scale_to_zero_note_real_inbound = lambda: None
    runner._is_user_authorized_for_source = lambda source: source.user_id == '456'
    runner._admit_bot_message_for_source = lambda source: True

    async def hook(original, source):
        return original

    runner._hm_pre_gateway_dispatch_hook = hook
    runner._hm_admit_event = inbound.GatewayInboundMixin._hm_admit_event.__get__(runner)
    original = base.MessageEvent(
        text='Original native request', message_type=base.MessageType.TEXT, message_id='789',
        source=session.SessionSource(platform=base.Platform.TELEGRAM, chat_id='456',
                                     chat_type='dm', user_id='456'))
    assert asyncio.run(module.try_admit(adapter, original)) is True
    assert runtime.records[0][1:3] == ('Original native request', '789')


def test_native_pending_control_readers_are_nonconsuming(setup, monkeypatch, tmp_path):
    module, runtime, runner, adapter = setup
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'hermes'))
    clarify = pytest.importorskip('tools.clarify_gateway')
    confirm = pytest.importorskip('tools.slash_confirm')
    approval = pytest.importorskip('tools.approval')
    pending_reader = runtime.native_pending_reader
    for index in range(3):
        with monkeypatch.context() as m:
            m.setattr(clarify, 'get_pending_for_session', lambda key, **kwargs: object() if index == 0 else None)
            m.setattr(confirm, 'get_pending', lambda key: object() if index == 1 else None)
            m.setattr(approval, 'has_blocking_approval', lambda key: index == 2)
            assert pending_reader(runner, 'isolated-test-session') is True


def test_native_telegram_lock_and_thread_helper_used_without_network(setup, monkeypatch, tmp_path):
    module, runtime, runner, adapter = setup
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'hermes'))
    native = pytest.importorskip('plugins.platforms.telegram.adapter')
    actual = object.__new__(native.TelegramAdapter)
    actual._bot = SimpleNamespace(id=123)
    actual._send_path_degraded = False
    calls = []

    async def send_message(**kwargs):
        assert actual._telegram_chat_send_lock_owners['456'] is asyncio.current_task()
        calls.append(kwargs)
        return SimpleNamespace(message_id=88, chat=SimpleNamespace(id=456))

    actual._bot.send_message = send_message
    assert asyncio.run(module.send_part(actual, SCOPE, 'Pink: native test')) == '88'
    assert calls[0]['message_thread_id'] is None


@pytest.mark.parametrize('raw', [
    SimpleNamespace(forward_origin=object()),
    SimpleNamespace(entities=[SimpleNamespace(type='blockquote')]),
    SimpleNamespace(entities=[SimpleNamespace(type='expandable_blockquote')]),
])
def test_forwarded_or_quoted_text_is_not_authorized_as_owner_request(setup, raw):
    module, runtime, runner, adapter = setup
    assert asyncio.run(module.try_admit(adapter, event(raw_message=raw))) is False
    assert runtime.records == []


def test_unknown_reply_uses_native_context_path(setup):
    module, runtime, runner, adapter = setup
    assert asyncio.run(module.try_admit(adapter, event(reply_to_message_id='unknown'))) is False
    assert runtime.records == []


def test_queue_cancel_command_requires_full_native_authorization(setup):
    module, runtime, runner, adapter = setup
    runtime.controls = []
    runtime.control_scope = lambda scope, state: runtime.controls.append((scope, state))
    command = event(text='/stop', message_type='command')
    runner.authorized = False
    asyncio.run(module.control_command(adapter, command))
    assert runtime.controls == []
    runner.authorized = True
    asyncio.run(module.control_command(adapter, command))
    assert runtime.controls == [(SCOPE, 'cancelled')]
