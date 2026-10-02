import json
import asyncio
from types import SimpleNamespace

import pytest
from test_runtime import runtime, SCOPE


def test_pending_package_preserves_text_and_documents_not_audio(runtime, tmp_path):
    import native_delivery as delivery
    doc = runtime.home.parent / 'report.docx'
    doc.write_bytes(b'report')
    record = {'candidate': 'Relatorio\nMEDIA:' + str(doc) + '\nMEDIA:/tmp/voice.ogg',
              'task_id': 'native-turn', 'request': 'relatorio', 'producer': {}, 'evidence': []}
    key = delivery.save(runtime, SCOPE, record)
    with runtime.store._transaction() as db:
        row = db.execute('SELECT payload FROM host_native_delivery WHERE id=?', (key,)).fetchone()
    payload = json.loads(row[0])
    assert payload['text'] == 'Relatorio'
    assert len(payload['files']) == 1
    assert payload['files'][0]['sha256']
    doc.write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        delivery.check_files(payload)


def test_pending_package_is_idempotent_and_scoped(runtime):
    import native_delivery as delivery
    record = {'candidate': 'Resposta', 'task_id': 'same', 'request': 'pedido',
              'producer': {}, 'evidence': []}
    assert delivery.save(runtime, SCOPE, record) == delivery.save(runtime, SCOPE, record)
    with runtime.store._transaction() as db:
        assert db.execute('SELECT count(*) FROM host_native_delivery').fetchone()[0] == 1


def test_model_body_clears_stale_identity(monkeypatch):
    import model_identity
    monkeypatch.setattr(model_identity, 'aliases', lambda: {'combo'})
    agent = SimpleNamespace(last_served_model='old')
    model_identity.observe(agent, SimpleNamespace(model='gemini-3.8-flash'))
    assert agent.last_served_model == 'gemini-3.8-flash'
    model_identity.observe(agent, SimpleNamespace(model='combo'))
    assert agent.last_served_model is None


def test_package_sends_all_parts_and_preserves_receipts(runtime, monkeypatch):
    import native_delivery as delivery
    import gateway_adapter
    doc = runtime.home.parent / 'report.docx'
    doc.write_bytes(b'report')
    key = delivery.save(runtime, SCOPE, dict(candidate='Resposta\nMEDIA:' + str(doc),
        task_id='turn', request='relatorio', producer={}, evidence=[]))
    monkeypatch.setattr(delivery, 'review_package', lambda p, *a: dict(completed=True,
        status='approved', output_sha256=delivery.sha(p['text'].encode())))
    calls = []

    async def text(*args):
        calls.append('text')
        return '100'

    async def file(*args):
        calls.append('document')
        return '101'

    monkeypatch.setattr(gateway_adapter, 'send_part', text)
    monkeypatch.setattr(delivery, 'send_document', file)
    with runtime.store._transaction() as db:
        row = dict(db.execute('SELECT * FROM host_native_delivery WHERE id=?', (key,)).fetchone())
    asyncio.run(delivery.process(runtime, None, SCOPE, row))
    assert calls == ['text', 'document']
    with runtime.store._transaction() as db:
        assert db.execute('SELECT state FROM host_native_delivery').fetchone()[0] == 'sent'
        assert [r[0] for r in db.execute('SELECT message_id FROM host_native_parts ORDER BY ordinal')] == ['100', '101']


def test_review_failure_retains_package_without_sending(runtime, monkeypatch):
    import native_delivery as delivery
    import gateway_adapter
    delivery.save(runtime, SCOPE, dict(candidate='Resposta', task_id='turn', request='pedido', producer={}))
    monkeypatch.setattr(delivery, 'review_package', lambda *a: dict(completed=False, reason='provider_unavailable'))

    async def forbidden(*args):
        raise AssertionError('Unapproved delivery')

    monkeypatch.setattr(gateway_adapter, 'send_part', forbidden)
    with runtime.store._transaction() as db:
        row = dict(db.execute('SELECT * FROM host_native_delivery').fetchone())
    asyncio.run(delivery.process(runtime, None, SCOPE, row))
    with runtime.store._transaction() as db:
        assert tuple(db.execute('SELECT state,attempts FROM host_native_delivery').fetchone()) == ('review_pending', 1)
        assert db.execute('SELECT count(*) FROM host_native_parts').fetchone()[0] == 0


def test_cancel_during_review_cannot_release_package(runtime, monkeypatch):
    import native_delivery as delivery
    delivery.save(runtime, SCOPE, dict(candidate='Resposta', task_id='turn', request='pedido', producer={}))

    def review(payload, *args):
        delivery.cancel(runtime, SCOPE)
        return dict(completed=True, status='approved', output_sha256=delivery.sha(payload['text'].encode()))

    monkeypatch.setattr(delivery, 'review_package', review)
    with runtime.store._transaction() as db:
        row = dict(db.execute('SELECT * FROM host_native_delivery').fetchone())
    asyncio.run(delivery.process(runtime, None, SCOPE, row))
    with runtime.store._transaction() as db:
        assert db.execute('SELECT state FROM host_native_delivery').fetchone()[0] == 'cancelled'


def test_terminal_block_is_reported_once_without_claiming_delivery(runtime, monkeypatch):
    import native_delivery as delivery
    import gateway_adapter
    key = delivery.save(runtime, SCOPE, dict(candidate='Resposta', task_id='turn', request='pedido', producer={}))
    with runtime.store._transaction() as db:
        db.execute('UPDATE host_native_delivery SET state=? WHERE id=?', ('blocked', key))
    sent = []

    async def send(adapter, scope, text):
        sent.append(text)
        return 'notification-1'

    monkeypatch.setattr(gateway_adapter, 'send_part', send)
    asyncio.run(delivery.notify_blocked(runtime, None, SCOPE))
    asyncio.run(delivery.notify_blocked(runtime, None, SCOPE))
    assert len(sent) == 1
    assert 'nao foi entregue' in sent[0]
