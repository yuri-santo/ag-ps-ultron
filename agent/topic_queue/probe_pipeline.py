"""Explicit real-provider probe in a private disposable home; no Telegram send."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-dispatch', action='store_true')
    args = parser.parse_args()
    live = Path('/root/.hermes')
    home = Path(tempfile.mkdtemp(prefix='.topic-probe-', dir='/root'))
    os.chmod(home, 0o700)
    os.environ.update(HERMES_HOME=str(home), ULTRON_BASE_HOME=str(home), HERMES_KANBAN_HOME=str(home))
    for key in ('HERMES_KANBAN_DB', 'HERMES_KANBAN_BOARD', 'HERMES_PROFILE'):
        os.environ.pop(key, None)
    shutil.copy2(live / 'config.yaml', home / 'config.yaml')
    for name in ('cerebro', 'tanos'):
        profile = home / 'profiles' / name
        profile.mkdir(parents=True, mode=0o700)
        for filename in ('config.yaml', 'SOUL.md', 'profile.yaml'):
            if (live / 'profiles' / name / filename).is_file():
                shutil.copy2(live / 'profiles' / name / filename, profile / filename)
    shutil.copytree(live / 'plugins', home / 'plugins')
    # Adoption tooling is read-only here; no tool is requested by this probe.
    if (live / 'integrations/adoption').is_dir():
        shutil.copytree(live / 'integrations/adoption', home / 'integrations/adoption')
    queue = home / 'topic-queue'
    queue.mkdir(mode=0o700)
    config = json.loads((live / 'topic-queue/config.json').read_text())
    config['enabled'] = True
    config['scopes'] = [dict(platform='telegram', account_id='probe', owner_id='probe', chat_id='probe', thread_id='')]
    (queue / 'config.json').write_text(json.dumps(config))
    from ultron_topic_queue.runtime import Runtime
    runtime = Runtime.from_home(home)
    scope = runtime.configured_scopes[0]
    entry = runtime.admit(scope, 'Oi! Responda uma frase curta, sem chamar ferramentas.', 'probe-message')
    if args.native_dispatch:
        from hermes_cli import kanban_db_dispatch as dispatch
        deadline = time.monotonic() + 600
        last = None
        while time.monotonic() < deadline:
            runtime.maintain()
            with runtime.connect() as db:
                dispatch.dispatch_once(db, board='ultron-topics', max_spawn=2,
                    max_in_progress=2, max_in_progress_per_profile=1)
                statuses = dict(db.execute('SELECT status,count(*) FROM tasks GROUP BY status'))
            if statuses != last:
                print(json.dumps({'native_dispatch': statuses, 'private_home': str(home)}), flush=True)
                last = statuses
            with runtime.store._transaction() as db:
                approvals = db.execute('SELECT COUNT(*) FROM delivery_approvals').fetchone()[0]
            if approvals and set(statuses) == {'done'}:
                print(json.dumps({'native_pipeline': 'approved', 'approvals': approvals, 'telegram_sent': False}))
                return
            if statuses.get('blocked') and not (statuses.get('running') or statuses.get('scheduled') or statuses.get('ready')):
                raise SystemExit('Probe blocked; inspect the private home')
            time.sleep(3)
        raise SystemExit('Probe deadline exceeded; private workers were not replayed')
    with runtime.connect() as db:
        task = runtime.kb.claim_task(db, entry['card_id'])
    runtime.run(task.id, task.current_run_id)
    rows = runtime.store.card_intents(scope)
    print(json.dumps({'stage': 'triage', 'topics': len(rows), 'private_home': str(home)}), flush=True)
    for row in rows:
        with runtime.connect() as db:
            task = runtime.kb.claim_task(db, row['native_card_id'])
        if task:
            runtime.run(task.id, task.current_run_id)
        with runtime.connect() as db:
            result = runtime.kb.get_task(db, row['native_card_id'])
            print(json.dumps({'stage': 'final', 'status': result.status,
                              'result_present': bool(result.result)}), flush=True)
    with runtime.store._transaction() as db:
        print(json.dumps({'approvals': db.execute('SELECT COUNT(*) FROM delivery_approvals').fetchone()[0],
                          'stage_reasons': [row[0] for row in db.execute('SELECT reason FROM host_stages')]}), flush=True)
    # Retained privately for diagnosis; never print task text, SOUL or credentials.


if __name__ == '__main__':
    main()
