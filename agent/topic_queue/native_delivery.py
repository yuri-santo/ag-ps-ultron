"""Durable completion of native attachment turns, using the existing gateway tick.

Only delivery/review is retried. Tool execution is never replayed here. Audio is
optional and is not part of the required text/document completion contract.
"""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
import time

LOG = logging.getLogger(__name__)
_jobs = {}
AUDIO = {'.ogg', '.mp3', '.wav', '.m4a', '.opus'}
DOCUMENTS = {'.docx', '.xlsx', '.pdf', '.csv', '.txt', '.pptx', '.png', '.jpg', '.jpeg', '.mp4'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS host_native_notices ('
               'delivery_id TEXT PRIMARY KEY, state TEXT NOT NULL, message_id TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS host_native_delivery ('
               'id TEXT PRIMARY KEY, scope TEXT NOT NULL, payload TEXT NOT NULL, '
               'state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, due REAL NOT NULL DEFAULT 0, '
               'review TEXT, reason TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS host_native_parts ('
               'delivery_id TEXT, ordinal INTEGER, kind TEXT NOT NULL, payload TEXT NOT NULL, '
               'state TEXT NOT NULL DEFAULT "pending", message_id TEXT, '
               'PRIMARY KEY(delivery_id,ordinal))')


def package(runtime, record):
    candidate = record['candidate']
    files = []
    for match in re.finditer(r'(?m)^MEDIA:([^\r\n]+)\s*$', candidate):
        raw = Path(match[1].strip())
        if raw.suffix.lower() in AUDIO:
            continue
        path = raw.resolve(strict=True)
        if (raw.is_symlink() or path.suffix.lower() not in DOCUMENTS
                or not path.is_relative_to(runtime.home.parent)
                or any(part.startswith('.') for part in path.relative_to(runtime.home.parent).parts)):
            raise ValueError('Unsafe document path')
        data = path.read_bytes()
        if not 0 < len(data) <= 45000000:
            raise ValueError('Unsupported document size')
        entry = dict(path=str(path), sha256=sha(data), bytes=len(data))
        if entry not in files:
            files.append(entry)
    text = re.sub(r'(?m)^MEDIA:[^\r\n]+\s*$', '', candidate)
    text = re.sub(r'\[\[(?:audio_as_voice|as_document)\]\]', '', text).strip()
    if not text:
        text = 'Ultron: Seguem os arquivos solicitados.'
    producer = record.get('producer') or {}
    if 'model' not in producer:
        producer = dict(provider=producer.get('transport'),
                        model=producer.get('requested_model'), served_model=producer.get('served_model'))
    return dict(text=text, files=files, request=record.get('request', ''),
                producer=producer, evidence=record.get('evidence') or [], task_id=record['task_id'])


def check_files(payload):
    for item in payload['files']:
        path = Path(item['path'])
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != item['sha256']:
            raise ValueError('Document changed after capture')


def save(runtime, scope, record):
    if scope not in runtime.configured_scopes:
        raise ValueError('Scope not enabled')
    payload = package(runtime, record)
    key = sha((scope.key() + record['task_id'] + record['candidate']).encode())
    with runtime.store._transaction() as db:
        schema(db)
        db.execute('INSERT OR IGNORE INTO host_native_delivery(id,scope,payload,state) VALUES(?,?,?,?)',
                   (key, scope.key(), json.dumps(payload, ensure_ascii=False), 'review_pending'))
    return key


def capture(ctx, result, gateway):
    review = result.get('model_review') or {}
    if not review or review.get('completed') is True:
        return False
    from .runtime import Runtime
    from .gateway_adapter import _scope
    runtime = Runtime.from_home()
    source = ctx.source
    adapter = next((a for k, a in gateway.adapters.items()
        if str(getattr(k, 'value', k)) == str(getattr(source.platform, 'value', source.platform))), None)
    if adapter is None or not runtime.enabled or not ctx._run_still_current():
        return False
    scope = _scope(adapter, source)
    if scope not in runtime.configured_scopes:
        return False
    # The private audit ledger, not model output, owns the original candidate.
    root = Path('/root/ultron-local/reviews/history')
    task_id, fingerprint = review.get('task_id'), review.get('fingerprint')
    if not task_id or not fingerprint:
        return False
    paths = list(root.glob(sha(str(task_id).encode()) + '-r*-' + fingerprint[:12] + '.json'))
    if len(paths) != 1:
        return False
    record = json.loads(paths[0].read_text())
    if record.get('task_id') != task_id or record.get('fingerprint') != fingerprint:
        return False
    if sha(record['candidate'].encode()) != review.get('output_sha256'):
        return False
    save(runtime, scope, record)
    return True


def review_package(payload, identity, attempt):
    if '/root/ultron-local' not in sys.path:
        sys.path.insert(0, '/root/ultron-local')
    import model_review
    check_files(payload)
    evidence = payload['evidence'] + [dict(kind='artifact_snapshot', **f) for f in payload['files']]
    revision = sha(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())[:16]
    return model_review.review_output(task_id='delivery:' + identity + ':' + revision + ':' + str(attempt),
        producer=payload['producer'], output=payload['text'], request=payload['request'],
        evidence=evidence, task_kind='answer', context={'delivery_mode': 'interactive'})


async def send_document(adapter, scope, item):
    from .gateway_adapter import _transport_preflight
    bot = _transport_preflight(adapter, scope, 'document')
    check_files({'files': [item]})
    async with asyncio.timeout(60):
        async with adapter._chat_send_lock(scope.chat_id):
            if adapter._send_flood_cooldown_remaining(scope.chat_id) is not None:
                from .gateway_adapter import TransportNotSent
                raise TransportNotSent('Document cooldown')
            delay = adapter._chat_outbound_slot_remaining(scope.chat_id)
            if delay > 0:
                await asyncio.sleep(delay)
            adapter._hold_chat_outbound_slot(scope.chat_id)
            kwargs = adapter._thread_kwargs_for_send(scope.chat_id, scope.thread_id,
                                                     reply_to_message_id=None, reply_to_mode='all')
            with Path(item['path']).open('rb') as stream:
                receipt = await bot.send_document(chat_id=int(scope.chat_id), document=stream,
                    filename=Path(item['path']).name, **kwargs,
                    read_timeout=45, write_timeout=45, connect_timeout=10, pool_timeout=10)
    if type(receipt.message_id) is not int or str(receipt.chat.id) != scope.chat_id:
        raise RuntimeError('Missing document receipt')
    return str(receipt.message_id)


async def process(runtime, adapter, scope, row):
    try:
        from .runtime import format_parts
        from .gateway_adapter import send_part, TransportNotSent
    except ImportError:
        from runtime import format_parts
        from gateway_adapter import send_part, TransportNotSent
    key, payload = row['id'], json.loads(row['payload'])
    try:
        if row['state'] == 'review_pending':
            attempt = row['attempts'] + 1
            with runtime.store._transaction() as db:
                db.execute('UPDATE host_native_delivery SET attempts=?,due=? WHERE id=?',
                           (attempt, time.time() + 600, key))
            verdict = await asyncio.to_thread(review_package, payload, key, attempt)
            approved = (verdict.get('completed') is True and
                        verdict.get('status') in ('approved', 'not_required') and
                        verdict.get('output_sha256') == sha(payload['text'].encode()))
            with runtime.store._transaction() as db:
                if db.execute('SELECT state FROM host_native_delivery WHERE id=?', (key,)).fetchone()[0] == 'cancelled':
                    return
                if not approved:
                    state = 'needs_revision' if verdict.get('status') == 'revision_required' else (
                        'review_pending' if attempt < 3 else 'blocked')
                    db.execute('UPDATE host_native_delivery SET state=?,review=?,reason=?,due=? WHERE id=?',
                        (state, json.dumps(verdict), verdict.get('reason'), time.time() + 60 * attempt, key))
                    return
                parts = [('text', p) for p in format_parts(payload['text'])]
                parts += [('document', json.dumps(f)) for f in payload['files']]
                db.executemany('INSERT OR IGNORE INTO host_native_parts(delivery_id,ordinal,kind,payload) VALUES(?,?,?,?)',
                               [(key, i, kind, value) for i, (kind, value) in enumerate(parts)])
                db.execute('UPDATE host_native_delivery SET state=?,review=?,reason=NULL WHERE id=?',
                           ('approved', json.dumps(verdict), key))
        await asyncio.to_thread(check_files, payload)
        with runtime.store._transaction() as db:
            parts = [dict(r) for r in db.execute('SELECT * FROM host_native_parts WHERE delivery_id=? ORDER BY ordinal', (key,))]
        for part in parts:
            if part['state'] == 'sent':
                continue
            if part['state'] != 'pending':
                return
            with runtime.store._transaction() as db:
                state = db.execute('SELECT state FROM host_native_delivery WHERE id=?', (key,)).fetchone()[0]
                if state != 'approved':
                    return
                db.execute('UPDATE host_native_parts SET state=? WHERE delivery_id=? AND ordinal=?',
                           ('sending', key, part['ordinal']))
            try:
                receipt = (await send_part(adapter, scope, part['payload']) if part['kind'] == 'text'
                           else await send_document(adapter, scope, json.loads(part['payload'])))
            except TransportNotSent:
                with runtime.store._transaction() as db:
                    db.execute('UPDATE host_native_parts SET state=? WHERE delivery_id=? AND ordinal=?',
                               ('pending', key, part['ordinal']))
                    db.execute('UPDATE host_native_delivery SET due=? WHERE id=?', (time.time()+30, key))
                return
            except Exception:
                with runtime.store._transaction() as db:
                    db.execute('UPDATE host_native_delivery SET state=? WHERE id=?', ('uncertain', key))
                raise
            with runtime.store._transaction() as db:
                db.execute('UPDATE host_native_parts SET state=?,message_id=? WHERE delivery_id=? AND ordinal=?',
                           ('sent', receipt, key, part['ordinal']))
        with runtime.store._transaction() as db:
            db.execute('UPDATE host_native_delivery SET state=? WHERE id=? AND state=?', ('sent', key, 'approved'))
    except Exception as exc:
        LOG.warning('Native delivery retained (%s)', type(exc).__name__)
        with runtime.store._transaction() as db:
            db.execute('UPDATE host_native_delivery SET reason=?,due=? WHERE id=?',
                       (type(exc).__name__, time.time()+120, key))
            db.execute("UPDATE host_native_delivery SET state='blocked' WHERE id=? AND attempts>=3 AND state='review_pending'", (key,))


async def kick(runtime, adapter, scope):
    key = (str(runtime.home), scope.key())
    if key in _jobs and not _jobs[key].done():
        return
    with runtime.store._transaction() as db:
        schema(db)
        row = db.execute("SELECT * FROM host_native_delivery WHERE scope=? AND state IN ('review_pending','approved') "
                         'AND due<=? ORDER BY rowid LIMIT 1', (scope.key(), time.time())).fetchone()
    if row:
        _jobs[key] = asyncio.create_task(process(runtime, adapter, scope, dict(row)))
    else:
        await notify_blocked(runtime, adapter, scope)


async def notify_blocked(runtime, adapter, scope):
    try:
        from .gateway_adapter import send_part
    except ImportError:
        from gateway_adapter import send_part
    with runtime.store._transaction() as db:
        schema(db)
        row = db.execute("SELECT d.id,d.state FROM host_native_delivery d LEFT JOIN host_native_notices n "
            "ON n.delivery_id=d.id WHERE d.scope=? AND d.state IN ('blocked','needs_revision','uncertain') "
            'AND n.delivery_id IS NULL ORDER BY d.rowid LIMIT 1', (scope.key(),)).fetchone()
        if not row:
            return
        db.execute('INSERT INTO host_native_notices VALUES(?,?,NULL)', (row['id'], 'sending'))
    reason = {'blocked': 'A revisao ficou indisponivel apos as tentativas automaticas.',
              'needs_revision': 'A revisao encontrou pontos que precisam de correcao.',
              'uncertain': 'Nao consegui confirmar o envio de um dos itens; nao vou repeti-lo automaticamente.'}[row['state']]
    text = ('Ultron: O pacote completo ainda nao foi entregue. ' + reason +
            ' O texto e os arquivos continuam salvos. Audio nao conta como entrega do relatorio.')
    try:
        receipt = await send_part(adapter, scope, text)
    except Exception as exc:
        LOG.warning('Native delivery status receipt uncertain (%s)', type(exc).__name__)
        return
    with runtime.store._transaction() as db:
        db.execute('UPDATE host_native_notices SET state=?,message_id=? WHERE delivery_id=?',
                   ('sent', receipt, row['id']))


def cancel(runtime, scope):
    with runtime.store._transaction() as db:
        schema(db)
        db.execute("UPDATE host_native_delivery SET state='cancelled' WHERE scope=? AND state NOT IN ('sent','uncertain')", (scope.key(),))
