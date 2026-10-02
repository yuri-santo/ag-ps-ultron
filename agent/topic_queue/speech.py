"""Optional speech follows successful text delivery; never gates its approval."""
import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

LOG = logging.getLogger(__name__)
_tasks = {}


def schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS host_speech ('
               'approval_id TEXT PRIMARY KEY, text TEXT NOT NULL, request TEXT NOT NULL, '
               'state TEXT NOT NULL, message_id TEXT)')


def enqueue(runtime, approval_id, text, request):
    with runtime.store._transaction() as db:
        schema(db)
        db.execute('INSERT OR IGNORE INTO host_speech VALUES(?,?,?,?,NULL)',
                   (approval_id, text, request, 'pending'))


def claim(runtime, scope):
    with runtime.store._transaction() as db:
        schema(db)
        row = db.execute('SELECT s.*,a.topic_id,a.version,p.message_id AS reply_id '
            'FROM host_speech s JOIN delivery_approvals a ON a.id=s.approval_id '
            'JOIN delivery_outbox o ON o.approval_id=a.id '
            'JOIN delivery_parts p ON p.approval_id=a.id AND p.part_index=0 '
            'JOIN versions v ON v.topic_id=a.topic_id AND v.version=a.version '
            'JOIN topics t ON t.id=a.topic_id '
            "WHERE a.scope=? AND s.state='pending' AND o.state='sent' "
            'AND v.valid=1 AND t.current_version=a.version ORDER BY a.sequence LIMIT 1',
            (scope.key(),)).fetchone()
        if not row or runtime.proofs.control(scope, row['topic_id'], row['version']) != 'active':
            return None
        # A crash/ambiguous receipt must not replay an audio upload.
        db.execute('UPDATE host_speech SET state=? WHERE approval_id=?', ('claimed', row['approval_id']))
        return dict(row)


def render(home, item):
    env = dict(os.environ, HERMES_HOME=str(home), ULTRON_BASE_HOME=str(home),
               ULTRON_HOST_HANDLES_SPEECH='1', HERMES_SESSION_PLATFORM='telegram')
    for key in list(env):
        if key.startswith('HERMES_KANBAN_') or key in ('HERMES_PROFILE', 'HERMES_TENANT'):
            env.pop(key, None)
    result = subprocess.run([sys.executable, '-m', 'ultron_topic_queue.speech'],
        input=json.dumps({'home': str(home), **item}), capture_output=True, text=True,
        env=env, cwd=str(home), timeout=90)
    if result.returncode:
        raise RuntimeError('Speech rendering failed')
    return json.loads(result.stdout)


async def deliver(runtime, adapter, scope, item):
    state, message_id = 'failed', None
    try:
        media = await asyncio.to_thread(render, runtime.home, item)
        if not media:
            state = 'skipped'
            return
        try:
            from .gateway_adapter import _transport_preflight, SEND_TIMEOUT_SECONDS
        except ImportError:
            from gateway_adapter import _transport_preflight, SEND_TIMEOUT_SECONDS
        bot = _transport_preflight(adapter, scope, item['text'][:100])
        path = Path(media['path']).resolve(strict=True)
        if not path.is_relative_to((runtime.home / 'audio_cache').resolve()) or not 0 < path.stat().st_size <= 20000000:
            raise ValueError('Invalid speech artifact')
        with runtime.store._transaction() as db:
            current = db.execute('SELECT current_version FROM topics WHERE id=?', (item['topic_id'],)).fetchone()
        if not current or current[0] != item['version'] or runtime.proofs.control(scope, item['topic_id'], item['version']) != 'active':
            state = 'skipped'
            return
        async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
            async with adapter._chat_send_lock(scope.chat_id):
                if adapter._send_flood_cooldown_remaining(scope.chat_id) is not None:
                    raise RuntimeError('Audio cooldown')
                delay = adapter._chat_outbound_slot_remaining(scope.chat_id)
                if delay > 0:
                    await asyncio.sleep(delay)
                adapter._hold_chat_outbound_slot(scope.chat_id)
                kwargs = adapter._thread_kwargs_for_send(scope.chat_id, scope.thread_id,
                    reply_to_message_id=int(item['reply_id']), reply_to_mode='all')
                state = 'uncertain'
                with path.open('rb') as stream:
                    method = bot.send_voice if media['voice'] else bot.send_audio
                    field = 'voice' if media['voice'] else 'audio'
                    receipt = await method(chat_id=int(scope.chat_id), **{field: stream},
                        reply_to_message_id=int(item['reply_id']), **kwargs,
                        read_timeout=30, write_timeout=30, connect_timeout=10, pool_timeout=10)
                if type(receipt.message_id) is not int or str(receipt.chat.id) != scope.chat_id:
                    raise RuntimeError('Invalid audio receipt')
                message_id, state = str(receipt.message_id), 'sent'
    except Exception as exc:
        LOG.warning('Optional topic speech %s (%s); text is unaffected', state, type(exc).__name__)
    finally:
        with runtime.store._transaction() as db:
            db.execute('UPDATE host_speech SET state=?,message_id=? WHERE approval_id=?',
                       (state, message_id, item['approval_id']))


async def kick(runtime, adapter, scope):
    key = (str(runtime.home), scope.key())
    if key in _tasks and not _tasks[key].done():
        return
    item = await asyncio.to_thread(claim, runtime, scope)
    if item:
        _tasks[key] = asyncio.create_task(deliver(runtime, adapter, scope, item))


def main():
    import importlib.util
    from hermes_cli.config import load_config_readonly
    request = json.load(sys.stdin)
    home = Path(request['home']).resolve()
    cfg = load_config_readonly() or {}
    settings = cfg.get('plugins', {}).get('entries', {}).get('ultron_team', {}).get('settings', {})
    if not settings.get('voice_enabled', False):
        print('null')
        return
    spec = importlib.util.spec_from_file_location('_speech_plan', home / 'plugins/ultron_team/delivery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = module.speech_plan(request['text'], request['request'])
    if not text:
        print('null')
        return
    from tools.tts_tool import text_to_speech_tool
    cache = home / 'audio_cache'
    cache.mkdir(mode=0o700, exist_ok=True)
    result = json.loads(text_to_speech_tool(text, output_path=str(cache / (request['approval_id'] + '.mp3'))))
    if not result.get('success'):
        raise RuntimeError('Speech generation unavailable')
    print(json.dumps({'path': result['file_path'], 'voice': result.get('voice_compatible') is True}))


if __name__ == '__main__':
    main()
