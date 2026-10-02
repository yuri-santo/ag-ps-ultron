"""Trusted gateway bridge; native Kanban remains the only work scheduler.

Only this host module writes authoritative proofs. Models receive task/context
data, never a proof-writing tool, delivery callback or completion capability.
"""
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

try:
    from .admission import Scope, TopicStore
    from .contract import canonical, require, QueueError
    from .delivery import Delivery
    from .native_cards import NativeCards
    from .triage import NativeCompletion, plan_ingress, parse_proposal
    from .profile_selection import Selection
except ImportError:
    from admission import Scope, TopicStore
    from contract import canonical, require, QueueError
    from delivery import Delivery
    from native_cards import NativeCards
    from triage import NativeCompletion, plan_ingress, parse_proposal
    from profile_selection import Selection

BOARD = 'ultron-topics'


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def format_parts(text):
    text = re.sub('[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f\u200d]', '', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text).strip()
    parts = []
    while text:
        end, units = 0, 0
        for char in text:
            size = len(char.encode('utf-16-le')) // 2
            if units + size > 3900:
                break
            end, units = end + 1, units + size
        if end < len(text):
            split = text.rfind('\n', 0, end)
            if split > end // 2:
                end = split + 1
        parts.append(text[:end])
        text = text[end:]
    return parts


class Evidence:
    """Separate durable store: a send receipt must commit outside outbox txn."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.path = runtime.root / 'evidence.db'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS proofs (kind TEXT, id TEXT, payload TEXT NOT NULL, '
                       'PRIMARY KEY(kind,id))')
            for op in ('UPDATE', 'DELETE'):
                db.execute(f'CREATE TRIGGER IF NOT EXISTS no_{op} BEFORE {op} ON proofs BEGIN '
                           "SELECT RAISE(ABORT,'Immutable host evidence'); END")

    @contextmanager
    def connect(self):
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.close(fd)
        db = sqlite3.connect(self.path, timeout=20)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, kind, identity, record):
        payload = canonical(record)
        with self.connect() as db:
            row = db.execute('SELECT payload FROM proofs WHERE kind=? AND id=?', (kind, identity)).fetchone()
            require(row is None or row[0] == payload, 'Evidence collision')
            db.execute('INSERT OR IGNORE INTO proofs VALUES(?,?,?)', (kind, identity, payload))
        return identity

    def get(self, kind, identity):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM proofs WHERE kind=? AND id=?', (kind, identity)).fetchone()
        return json.loads(row[0]) if row else None

    def execution(self, identity):
        return self.get('execution', identity)

    def review(self, identity):
        return self.get('review', identity)

    def outcome(self, identity):
        return self.get('outcome', identity)

    def control(self, scope, topic_id, version):
        if not self.runtime.enabled or scope not in self.runtime.configured_scopes:
            return 'paused'
        from hermes_cli import kanban_db as kb
        try:
            from gateway.kanban_watchers_common import _kanban_dispatch_allowed
            if not _kanban_dispatch_allowed():
                return 'paused'
        except ImportError:
            pass
        with sqlite3.connect(f'file:{self.runtime.store.path}?mode=ro', uri=True) as db:
            row = db.execute('SELECT state FROM host_controls WHERE scope=?', (scope.key(),)).fetchone()
        return row[0] if row else 'active'

    def policy(self, scope, topic_id, version, contract):
        domain = contract['profile']
        reviewers = {domain: [domain], 'tanos': ['audit']}
        if domain == 'tanos':
            reviewers['ironman'] = ['audit', domain]
        return dict(id='local-committee', version='1', required_competencies=[domain, 'audit'],
                    required_reviewers=sorted(reviewers), reviewers=reviewers)


class Runtime:
    def __init__(self, home, config):
        self.home = Path(home).resolve()
        self.config = config
        self.enabled = config.get('enabled') is True
        self.configured_scopes = [Scope(**item) for item in config.get('scopes', [])]
        self.roster = config.get('roster', {})
        self.root = self.home / 'topic-queue'
        self.store = TopicStore(self.root / 'queue.db', allowed_profiles=set(self.roster))
        self.board_path = self.home / 'kanban' / 'boards' / BOARD / 'kanban.db'
        from hermes_cli import kanban_db as kb, kanban_db_connect as kbc
        self.kb, self.kbc = kb, kbc
        with self.store._transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS host_controls(scope TEXT PRIMARY KEY, state TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS host_stages(card_id TEXT PRIMARY KEY, '
                       'started_run INTEGER, attempts INTEGER NOT NULL DEFAULT 0, due REAL, reason TEXT)')
        self.proofs = Evidence(self)
        self.delivery = Delivery(self.store, proofs=self.proofs, formatter=format_parts)
        with self.delivery._transaction():
            pass
        with self.connect():
            pass

    @classmethod
    def from_home(cls, home=None):
        home = Path(home or os.environ.get('ULTRON_BASE_HOME', '/root/.hermes'))
        path = home / 'topic-queue' / 'config.json'
        config = json.loads(path.read_text()) if path.is_file() else {'enabled': False, 'roster': {'cerebro': 'Triagem'}}
        return cls(home, config)

    def connect(self):
        return self.kbc.connect_closing(self.board_path)

    def control_scope(self, scope, state):
        require(scope in self.configured_scopes and state in ('active', 'paused', 'cancelled'), 'Invalid control')
        with self.store._transaction() as db:
            if state == 'cancelled':
                db.execute("UPDATE versions SET valid=0,invalid_reason='owner_cancelled' "
                           'WHERE topic_id IN(SELECT id FROM topics WHERE scope=?)', (scope.key(),))
                db.execute("UPDATE ingress SET plan=?,result=? WHERE scope=? AND plan IS NULL",
                           (canonical({'cancelled': True}), '[]', scope.key()))
                # Cancel current work, not future messages.
                state = 'active'
            db.execute('INSERT INTO host_controls VALUES(?,?) ON CONFLICT(scope) '
                       'DO UPDATE SET state=excluded.state', (scope.key(), state))

    def _scope(self, value):
        scope = Scope(**json.loads(value))
        require(self.enabled and scope in self.configured_scopes, 'Scope is not enabled')
        return scope

    def knows_reply(self, scope, message_id):
        with self.store._transaction() as db:
            return db.execute('SELECT 1 FROM delivery_references WHERE scope=? AND message_id=?',
                              (scope.key(), str(message_id))).fetchone() is not None

    def admit(self, scope, text, message_id, reply_to=None):
        require(self.enabled and scope in self.configured_scopes, 'Scope is not enabled')
        require(isinstance(text, str) and text.strip() and not text.lstrip().startswith('/'), 'Text request required')
        if self.config.get('persistent_profiles'):
            Selection(self.home, self.roster).snapshot(scope, message_id)
        # Telegram quote entities/forwarding are excluded by the adapter. Full
        # user-authored text remains visible; models cannot authorize tools from
        # embedded content (worker boundary enforces this separately).
        if reply_to:
            with self.store._transaction() as db:
                known = db.execute('SELECT 1 FROM delivery_references WHERE scope=? AND message_id=?',
                                   (scope.key(), str(reply_to))).fetchone()
            require(known is not None, 'Reply context is not in topic history')
        ingress_id = self.store.admit(scope, str(message_id), text,
                                     request_spans=[[0, len(text)]], authorized=True,
                                     reply_to=str(reply_to) if reply_to else None)
        return self._ingress_card(scope, ingress_id)

    def _ingress_card(self, scope, ingress_id):
        key = 'topic-ingress:' + ingress_id
        body = canonical(dict(adapter='topic_queue', kind='ingress', ingress_id=ingress_id, scope=scope.key()))
        with self.connect() as db, self.kb.write_txn(db):
            rows = db.execute('SELECT * FROM tasks WHERE idempotency_key=?', (key,)).fetchall()
            require(len(rows) <= 1, 'Ambiguous ingress card')
            if rows:
                require(rows[0]['body'] == body and rows[0]['created_by'] == 'topic_queue', 'Ingress card mismatch')
                identity = rows[0]['id']
            else:
                identity = self.kb.create_task(db, title='Triagem de mensagem', body=body,
                    created_by='topic_queue', tenant='topic-queue:' + digest(scope.key()),
                    idempotency_key=key, assignee='cerebro', initial_status='blocked', workspace_kind='scratch')
        with self.connect() as db:
            task = self.kb.get_task(db, identity)
            with self.store._transaction() as private:
                attempted = private.execute('SELECT 1 FROM host_stages WHERE card_id=?', (identity,)).fetchone()
            if task.status == 'blocked' and task.current_run_id is None and not attempted:
                self.kb.unblock_task(db, identity)
        return dict(ingress_id=ingress_id, card_id=identity)

    def _binding(self, task):
        require(task.created_by == 'topic_queue', 'Not a managed card')
        data = json.loads(task.body)
        if data.get('kind') == 'ingress':
            return self._scope(data['scope']), data
        with self.store._transaction() as db:
            row = db.execute('SELECT t.scope,l.topic_id,l.version FROM card_links l '
                             'JOIN topics t ON t.id=l.topic_id WHERE native_board=? AND native_card_id=?',
                             (str(self.board_path), task.id)).fetchone()
            require(row is not None, 'Unknown native card binding')
        scope = self._scope(row['scope'])
        contract = self.store.get_topic(scope, row['topic_id'])['contract']
        require(data['contract_hash'] == digest(canonical(contract)) and
                data['topic_id'] == row['topic_id'] and data['version'] == row['version'], 'Card contract changed')
        return scope, dict(kind='final', topic_id=row['topic_id'], version=row['version'], contract=contract)

    def mark_started(self, card_id, run_id):
        with self.store._transaction() as db:
            row = db.execute('SELECT started_run FROM host_stages WHERE card_id=?', (card_id,)).fetchone()
            require(row is None or row[0] is None, 'Execution outcome is uncertain; no automatic replay')
            db.execute('INSERT INTO host_stages(card_id,started_run) VALUES(?,?) '
                       'ON CONFLICT(card_id) DO UPDATE SET started_run=excluded.started_run', (card_id, run_id))

    def _defer(self, task, reason, *, retry):
        with self.store._transaction() as db:
            db.execute('INSERT OR IGNORE INTO host_stages(card_id) VALUES(?)', (task.id,))
            row = db.execute('SELECT attempts FROM host_stages WHERE card_id=?', (task.id,)).fetchone()
            attempt = row[0] + 1
            retry = retry and attempt < int(self.config.get('max_stage_attempts', 4))
            due = time.time() + min(900, 30 * 2 ** min(attempt - 1, 5)) if retry else None
            db.execute('UPDATE host_stages SET attempts=?,due=?,reason=? WHERE card_id=?',
                       (attempt, due, reason, task.id))
        with self.connect() as conn:
            if retry:
                self.kb.schedule_task(conn, task.id, reason=reason, expected_run_id=task.current_run_id)
            else:
                self.kb.block_task(conn, task.id, reason=reason, kind='needs_input', expected_run_id=task.current_run_id)

    def _finish(self, task, result, approval):
        with self.connect() as db:
            require(self.kb.complete_task(db, task.id, result=result, expected_run_id=task.current_run_id,
                                         fire_lifecycle_hook=False), 'Native completion ownership changed')

    def _release(self, scope):
        adapter = NativeCards(self.store, connect=self.connect, create_task=self.kb.create_task,
                              write_txn=self.kb.write_txn)
        pending = [r for r in self.store.card_intents(scope) if r['valid'] and not r['native_card_id']]
        while pending:
            linked = {(r['topic_id'], r['version']) for r in self.store.card_intents(scope) if r['native_card_id']}
            ready = [r for r in pending if all((d['topic_id'], d['version']) in linked
                     for d in self.store.get_topic(scope, r['topic_id'])['contract']['depends_on'])]
            require(ready, 'No reconcilable dependency frontier')
            for row in ready:
                adapter.reconcile(scope, row['topic_id'], row['version'])
                pending.remove(row)
        for row in self.store.card_intents(scope):
            if not row['valid'] or not row['native_card_id']:
                continue
            topic = self.store.get_topic(scope, row['topic_id'])
            with self.delivery._transaction() as db:
                try:
                    self.delivery._dependencies(db, scope, topic['contract'])
                    self.delivery._active(scope, row['topic_id'], row['version'])
                except QueueError:
                    continue
            with self.connect() as conn:
                task = self.kb.get_task(conn, row['native_card_id'])
                if task.status == 'blocked' and task.assignee is None:
                    profile = topic['contract']['profile']
                    self.kb.assign_task(conn, task.id, 'default' if profile == 'ultron' else profile)
                    self.kb.unblock_task(conn, task.id)

    def maintain(self, now=None):
        if not self.enabled:
            return
        now = time.time() if now is None else now
        for scope in self.configured_scopes:
            for message in self.store.pending(scope):
                self._ingress_card(scope, message['id'])
            self._release(scope)
        with self.store._transaction() as db:
            due = db.execute('SELECT card_id FROM host_stages WHERE due IS NOT NULL AND due<=?', (now,)).fetchall()
            for row in due:
                with self.connect() as conn:
                    task = self.kb.get_task(conn, row['card_id'])
                    if task and task.status == 'scheduled':
                        self.kb.unblock_task(conn, task.id)
                db.execute('UPDATE host_stages SET due=NULL WHERE card_id=?', (row['card_id'],))
        self._reconcile_receipts(now)

    def _reconcile_receipts(self, now):
        with self.proofs.connect() as db:
            receipts = [json.loads(row[0]) for row in db.execute("SELECT payload FROM proofs WHERE kind='outcome'")]
        for proof in receipts:
            if proof.get('retry_after', 0) > now:
                continue
            scope = self._scope(proof['scope'])
            with self.store._transaction() as db:
                row = db.execute('SELECT a.approval_id,a.part_index,a.state FROM delivery_attempts a '
                                 'JOIN delivery_parts p ON p.attempt_id=a.id '
                                 "WHERE a.id=? AND p.state IN ('uncertain','deferred')",
                                 (proof['attempt_id'],)).fetchone()
            if row and row['state'] in ('uncertain', 'not_sent'):
                self.delivery.reconcile(scope, row['approval_id'], row['part_index'], proof['id'])

    def _request_context(self, scope, data):
        contract = data['contract']
        request = '\n'.join(s['text'] for s in contract['spans'] if s['kind'] == 'request')
        context = [s['text'] for s in contract['spans'] if s['kind'] == 'context']
        with self.store._transaction() as db:
            history = db.execute('SELECT contract FROM versions WHERE topic_id=? AND version<? ORDER BY version',
                                 (data['topic_id'], data['version'])).fetchall()
            for row in history:
                context.append(canonical(json.loads(row['contract'])['spans']))
            answers = db.execute('SELECT a.version,p.payload FROM delivery_approvals a '
                                 'JOIN delivery_prepared p ON p.id=a.prepared_id '
                                 'WHERE a.scope=? AND a.topic_id=? AND a.version<? ORDER BY a.version',
                                 (scope.key(), data['topic_id'], data['version'])).fetchall()
            for answer in answers:
                context.append(canonical({'previous_approved_answer': answer['version'],
                    'historical_context_only': True, 'text': json.loads(answer['payload'])['parts']}))
            for parent in contract['depends_on']:
                approval = db.execute('SELECT prepared_id FROM delivery_approvals WHERE topic_id=? AND version=?',
                                      (parent['topic_id'], parent['version'])).fetchone()
                require(approval is not None, 'Dependency not approved')
                payload = json.loads(db.execute('SELECT payload FROM delivery_prepared WHERE id=?', (approval[0],)).fetchone()[0])
                context.append(canonical({'approved_dependency': parent, 'text': payload['parts']}))
        return request, '\n\n'.join(context)

    def _execution(self, task, scope, data, worker, rewriter=None):
        saved = self.proofs.get('candidate', task.id)
        if saved is not None:
            with self.proofs.connect() as db:
                revisions = [json.loads(r[0]) for r in db.execute(
                    "SELECT payload FROM proofs WHERE kind='candidate_revision' AND id LIKE ? ORDER BY rowid", (task.id + ':%',))]
            if revisions:
                saved = revisions[-1]
            feedback = self.proofs.get('feedback', task.id + ':' + digest(saved['result']['answer']))
            if feedback:
                require(len(revisions) < 2, 'Text revision budget exhausted')
                if rewriter is None:
                    from .reviewer import rewrite_candidate
                    rewriter = rewrite_candidate
                rewrite = rewriter(saved, feedback, profile=data['contract']['profile'], home=self.home)
                require(rewrite.get('answer', '').strip() and rewrite.get('served_identity'), 'Invalid text revision')
                require(rewrite['answer'] != saved['result']['answer'], 'Revision did not change rejected text')
                result = dict(saved['result'], answer=rewrite['answer'],
                              response_sha256=digest(rewrite['answer']),
                              model_review={'status': 'pending_review', 'completed': False},
                              producer=dict(saved['result']['producer'], served_model=rewrite['served_identity']))
                saved = dict(saved, result=result, run_id=str(task.current_run_id), revision=len(revisions) + 1)
                self.proofs.put('candidate_revision', task.id + ':' + str(saved['revision']), saved)
            return saved
        self.mark_started(task.id, task.current_run_id)
        request, context = self._request_context(scope, data)
        profile = data['contract']['profile']
        result = worker(profile, request, context=context, parent_session_id='topic:' + data['topic_id'])
        require(result.get('status') == 'ok' and result.get('profile') == profile and
                result.get('completed') is True and not result.get('failed'), 'Worker did not complete')
        answer = result.get('answer', '')
        require(answer.strip() and digest(answer) == result.get('response_sha256'), 'Candidate proof mismatch')
        initial = result.get('model_review') or {}
        require(initial.get('completed') is True and initial.get('status') in ('approved', 'not_required')
                and initial.get('output_sha256') == digest(answer), 'Worker review incomplete')
        served = (result.get('producer') or {}).get('served_model')
        require(isinstance(served, str) and served.strip(), 'Actual served model is unavailable')
        # Do not label a provider exemption as approval. The final-text domain
        # and audit reviews below must succeed before execution proof is issued.
        record = dict(result=result, run_id=str(task.current_run_id), request=request, context=context)
        self.proofs.put('candidate', task.id, record)
        return record

    def run(self, task_id, run_id, *, complete=None, worker=None, reviewer=None, rewriter=None):
        with self.connect() as conn:
            task = self.kb.get_task(conn, task_id)
        require(task and task.status == 'running' and task.current_run_id == int(run_id), 'Not the native claim owner')
        data = {'kind': 'unknown'}
        try:
            scope, data = self._binding(task)
            if data['kind'] == 'ingress':
                with self.store._transaction() as db:
                    ingress = db.execute('SELECT plan FROM ingress WHERE id=?', (data['ingress_id'],)).fetchone()
                    require(ingress is not None and not (ingress[0] and json.loads(ingress[0]).get('cancelled')),
                            'Ingress was cancelled')
                with self.store._transaction() as db:
                    topics = [r[0] for r in db.execute('SELECT id FROM topics WHERE scope=? ORDER BY rowid', (scope.key(),))]
                completion = complete or NativeCompletion()
                if self.config.get('persistent_profiles'):
                    with self.store._transaction() as db:
                        message_id = db.execute('SELECT message_id FROM ingress WHERE id=?',
                                                (data['ingress_id'],)).fetchone()[0]
                    selected = Selection(self.home, self.roster).pinned(scope, message_id)
                    if selected:
                        original_completion = completion
                        def completion(**kwargs):
                            envelope = json.loads(kwargs['user'])
                            envelope['roster'] = {selected: self.roster[selected]}
                            kwargs['user'] = canonical(envelope)
                            kwargs['system'] += '\nPerfil escolhido pelo titular: ' + selected + '. Todos os assuntos devem usar esse perfil.'
                            proposal = parse_proposal(original_completion(**kwargs))
                            require(all(t['profile'] == selected for t in proposal['topics']), 'Selected profile changed by triage')
                            return canonical(proposal)
                result = plan_ingress(self.store, scope, data['ingress_id'], roster=self.roster,
                                      complete=completion, context_ids=topics)
                require(result['status'] in ('planned', 'not_pending'), result.get('reason', 'triage_pending'))
                self._release(scope)
                self._finish(task, 'Triagem persistida; entregas no outbox aprovado.', data['ingress_id'])
                return
            require(self.store.revision_is_current(scope, data['topic_id'], data['version']), 'Stale topic')
            with self.delivery._transaction() as db:
                self.delivery._dependencies(db, scope, data['contract'])
                self.delivery._active(scope, data['topic_id'], data['version'])
            if worker is None:
                import sys
                sys.path.insert(0, str(self.home / 'plugins'))
                from ultron_team.bridge import Bridge
                from .specialist import run_specialist
                bridge = Bridge(self.home, runner=run_specialist)
                from .orchestrator_worker import dispatch_ultron
                worker = lambda profile, request, **kw: (
                    dispatch_ultron(self.home, request, **kw) if profile == 'ultron'
                    else bridge.dispatch(profile, request, **kw))
            candidate = self._execution(task, scope, data, worker, rewriter)
            result = candidate['result']
            profile = data['contract']['profile']
            author = self.config.get('authors', {}).get(profile, profile)
            parts = format_parts(author + ': ' + result['answer'])
            frozen = dict(parts=parts, profile=profile, author=author,
                          served_identity=result['producer']['served_model'],
                          evidence=result.get('evidence', []), contract=data['contract'])
            final_hash = digest(canonical(frozen))
            policy = self.proofs.policy(scope, data['topic_id'], data['version'], data['contract'])
            verdicts = {}
            for reviewer_profile in policy['required_reviewers']:
                key = task.id + ':' + final_hash + ':' + reviewer_profile
                vote = self.proofs.get('final-review', key)
                if vote is None:
                    if reviewer is None:
                        try:
                            from .reviewer import review_final
                        except ImportError:
                            from reviewer import review_final
                        call = review_final
                    else:
                        call = reviewer
                    with self.store._transaction() as db:
                        attempts = db.execute('SELECT attempts FROM host_stages WHERE card_id=?', (task.id,)).fetchone()[0]
                    vote = call(frozen, candidate['request'], profile=reviewer_profile,
                                home=self.home, proof_id=key, context=candidate['context'], attempt=attempts)
                    if vote.get('completed') is True and vote.get('verdict') == 'revise':
                        require(isinstance(vote.get('issues'), list) and bool(vote['issues']), 'Revision needs concrete findings')
                        self.proofs.put('feedback', task.id + ':' + digest(result['answer']), vote)
                        raise QueueError('Text correction required')
                    require(vote.get('completed') is True and vote.get('verdict') == 'approved'
                            and vote.get('checks') and vote.get('issues') == []
                            and vote.get('served_identity'), 'Final review pending or rejected')
                    self.proofs.put('final-review', key, vote)
                verdicts[reviewer_profile] = (key, vote)
            execution_id = task.id + ':' + candidate['run_id']
            execution = dict(scope=scope.key(), topic_id=data['topic_id'], version=data['version'],
                run_id=execution_id, native_board=str(self.board_path), native_card_id=task.id,
                profile=profile, contract_hash=digest(canonical(data['contract'])),
                completed=True, model_review='approved', candidate=result['answer'], author=author,
                served_identity=result['producer']['served_model'], candidate_hash=digest(result['answer']),
                evidence_hashes=[item['result_sha256'] for item in result.get('evidence', [])])
            self.proofs.put('execution', execution_id, execution)
            prepared = self.delivery.prepare(scope, data['topic_id'], data['version'], run_id=execution_id)
            require(prepared['parts'] == parts, 'Final text changed after review')
            review_ids = []
            for name, (key, vote) in verdicts.items():
                identity = digest(key + prepared['id'])
                self.proofs.put('review', identity, dict(id=identity, prepared_id=prepared['id'],
                    binding_hash=prepared['id'], run_id=key, profile=name,
                    served_identity=vote['served_identity'], completed=True, verdict='approved',
                    source_hash=digest(canonical(vote))))
                review_ids.append(identity)
            approval = self.delivery.approve(scope, prepared['id'], review_ids)
            try:
                from .speech import enqueue
            except ImportError:
                from speech import enqueue
            enqueue(self, approval['id'], result['answer'], candidate['request'])
            self._finish(task, '\n'.join(parts), approval['id'])
            self._release(scope)
        except Exception as exc:
            # No tool/model text in board failure messages. Review retries keep
            # the same candidate; uncertain execution never invokes it again.
            retry = data['kind'] == 'ingress' or self.proofs.get('candidate', task.id) is not None
            self._defer(task, 'topic_stage_' + type(exc).__name__, retry=retry)

    def record_outcome(self, attempt, message_id):
        identity = uuid.uuid4().hex
        self.proofs.put('outcome', identity, dict(id=identity, scope=attempt['scope'].key(),
            attempt_id=attempt['attempt_id'], text_hash=digest(attempt['text']),
            status='sent', message_id=str(message_id)))
        return identity

    async def drain(self, gateway):
        if not self.enabled:
            return
        await asyncio.to_thread(self.maintain)
        loop = asyncio.get_running_loop()
        try:
            from .gateway_adapter import send_part, TransportNotSent
        except ImportError:
            from gateway_adapter import send_part, TransportNotSent
        for scope in self.configured_scopes:
            adapters = getattr(gateway, 'adapters', {})
            adapter = next((a for key, a in adapters.items()
                            if str(getattr(key, 'value', key)) == scope.platform
                            and str(getattr(getattr(a, '_bot', None), 'id', '')) == scope.account_id), None)
            if adapter is None:
                continue
            def send(origin, attempt_id, text):
                attempt = dict(scope=origin, attempt_id=attempt_id, text=text)
                future = asyncio.run_coroutine_threadsafe(send_part(adapter, scope, text), loop)
                try:
                    message_id = future.result(timeout=50)
                except TransportNotSent:
                    identity = uuid.uuid4().hex
                    return self.proofs.put('outcome', identity, dict(id=identity, scope=origin.key(),
                        attempt_id=attempt_id, text_hash=digest(text), status='not_sent', message_id=None,
                        retry_after=time.time() + 30))
                except Exception:
                    future.cancel()
                    raise
                return self.record_outcome(attempt, message_id)
            await asyncio.to_thread(self.delivery.dispatch_next, scope, send)
            try:
                from .speech import kick
            except ImportError:
                from speech import kick
            await kick(self, adapter, scope)
