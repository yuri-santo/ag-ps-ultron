import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from test_runtime import runtime, plan, finish, SCOPE
import speech


def test_audio_only_claimed_after_text_sent_and_never_replayed(runtime):
    rows = plan(runtime)
    finish(runtime, rows[0]['native_card_id'])
    with runtime.store._transaction() as db:
        approval = db.execute('SELECT id FROM delivery_approvals').fetchone()[0]
    speech.enqueue(runtime, approval, 'Resposta aprovada', 'pedido')
    assert speech.claim(runtime, SCOPE) is None
    with runtime.store._transaction() as db:
        db.execute('UPDATE delivery_outbox SET state=? WHERE approval_id=?', ('sent', approval))
        db.execute('UPDATE delivery_parts SET state=?,message_id=? WHERE approval_id=?',
                   ('sent', '123', approval))
    assert speech.claim(runtime, SCOPE)['text'] == 'Consulta concluida com limites declarados.'
    assert speech.claim(runtime, SCOPE) is None


def test_audio_failure_does_not_change_text_delivery(runtime, monkeypatch):
    rows = plan(runtime)
    finish(runtime, rows[0]['native_card_id'])
    with runtime.store._transaction() as db:
        approval = db.execute('SELECT id FROM delivery_approvals').fetchone()[0]
        db.execute('UPDATE delivery_outbox SET state=? WHERE approval_id=?', ('sent', approval))
        db.execute('UPDATE delivery_parts SET state=?,message_id=? WHERE approval_id=?',
                   ('sent', '123', approval))
    speech.enqueue(runtime, approval, 'Resposta aprovada', 'pedido')
    item = speech.claim(runtime, SCOPE)

    def unavailable(*args):
        raise RuntimeError('TTS unavailable')

    monkeypatch.setattr(speech, 'render', unavailable)
    asyncio.run(speech.deliver(runtime, None, SCOPE, item))
    with runtime.store._transaction() as db:
        assert db.execute('SELECT state FROM delivery_outbox').fetchone()[0] == 'sent'
        assert db.execute('SELECT state FROM host_speech').fetchone()[0] == 'failed'


def test_audio_upload_has_own_receipt_and_no_reviewer(runtime, monkeypatch):
    finish(runtime, plan(runtime)[0]['native_card_id'])
    with runtime.store._transaction() as db:
        db.execute('UPDATE delivery_outbox SET state=?', ('sent',))
        db.execute('UPDATE delivery_parts SET state=?,message_id=?', ('sent', '123'))
    item = speech.claim(runtime, SCOPE)
    cache = runtime.home / 'audio_cache'
    cache.mkdir(exist_ok=True)
    audio = cache / 'test.mp3'
    audio.write_bytes(b'audio-test')
    monkeypatch.setattr(speech, 'render', lambda *args: {'path': str(audio), 'voice': False})
    sent = []

    async def upload(**kwargs):
        sent.append(kwargs['reply_to_message_id'])
        return SimpleNamespace(message_id=456, chat=SimpleNamespace(id=1234))

    @asynccontextmanager
    async def lock(*args):
        yield

    adapter = SimpleNamespace(_bot=SimpleNamespace(send_audio=upload),
        _chat_send_lock=lock, _send_flood_cooldown_remaining=lambda *a: None,
        _chat_outbound_slot_remaining=lambda *a: 0, _hold_chat_outbound_slot=lambda *a: None,
        _thread_kwargs_for_send=lambda *a, **kw: {})
    import gateway_adapter
    monkeypatch.setattr(gateway_adapter, '_transport_preflight', lambda *a: adapter._bot)
    monkeypatch.setattr(runtime.proofs, 'control', lambda *a: 'active')
    scope = SimpleNamespace(chat_id='1234', thread_id='')
    asyncio.run(speech.deliver(runtime, adapter, scope, item))
    assert sent == [123]
    with runtime.store._transaction() as db:
        assert tuple(db.execute('SELECT state,message_id FROM host_speech').fetchone()) == ('sent', '456')
