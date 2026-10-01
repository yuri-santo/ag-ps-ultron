# Native Topic Adapter and Publication Verification

> For agentic workers: use subagent-driven-development, with scope and quality
> review. Continue the queue and video designs already approved by the owner.

**Goal:** Connect durable topic metadata to native parked Kanban cards and close
publication paths that can ignore the existing evidence and presentation policy.

**Architecture:** Kanban remains the only scheduler. The adapter records links
and reconciles stable intent keys; every new card stays blocked and unassigned
until the approval/outbox integration exists. Semantic triage uses the native
auxiliary client, accepts only a closed validated proposal and never executes
tools. Publication changes stay in existing entry points and preserve schedules.

**Tech Stack:** Python 3.11, SQLite, Hermes native APIs, pytest/unittest.

## Task 1: Native Card Reconciliation

- [x] Inspect native create_task, write transactions, idempotency and subscriptions.
- [x] Add tests before code in agent/topic_queue/test_native_cards.py: retry after
  crash between native commit/link, concurrent duplicate calls, stale revisions,
  wrong scope, conflicting native card, archived card and dependency mapping.
- [x] Implement agent/topic_queue/native_cards.py using injected native connection
  and APIs; use a native outer write transaction around lookup and creation.
  Keep all cards blocked/unassigned, never subscribe origin or release work.
- [x] Extend admission.py with private card links and atomic current-version checks.
- [x] Run pytest in temporary HERMES_HOME with installed native source on PYTHONPATH;
  no writes to the live Kanban database and no dispatcher/model invocation.

## Task 2: Semantic Proposal Boundary

- [x] Add agent/topic_queue/test_triage.py for strict JSON, full text coverage,
  email UID/date versus SAP intention, untrusted quotes, independent topics,
  provider failure, exact reply continuation, and unknown profile rejection.
- [x] Add triage.py with an injected text-only completion function; snapshot
  same-scope context, keep source spans, parse without extracting arbitrary prose,
  and apply through TopicStore. Failure preserves pending ingress, no fallback tool.
- [x] Adapt native auxiliary client without calling native graph decomposer. Test
  the adapter using mocked client responses; do not make paid/network model calls.

## Task 3: Existing Publication Paths

- [x] Inspect live cron entry points and evidence/receipt paths for the observed
  recent product post; output only sanitized diagnostics, never account cookies.
- [x] Reproduce the bypass or presentation defect in isolated tests before fixing.
- [x] Make narrowly anchored source migrations and tests under agent/video/; reject
  unknown source versions. Preserve affiliate URLs and approved evidence.
- [x] Enforce no emojis for newly generated delivery text; do not silently strip
  unsupported factual claims or rewrite existing public posts during tests.
- [x] Back up affected live files before deployment; do not interrupt a running job.
  Never test by publishing a real post or adding an item to a marketplace.

## Verification and Status

- [x] Review each task against its approved scope, then inspect implementation.
- [x] Run topic, video and affected native regression tests and inspect staged diff.
- [x] Document installed fixes separately from disabled queue components, with the
  remaining authenticated ingress, approval barrier and outbox requirements.
- Commit/push only sanitized source, tests and public documentation. Keep private
  account observations and backup identifiers in the internal operations document.

## Verified Result

- Topic components: 103 tests passed, with temporary native boards. Semantic
  completions were mocked; no provider quality benchmark was performed.
- Video: 70 tests and 118 subtests passed after deployment, including native
  source checks and a synthetic FFmpeg render. No real publication.
- Native Kanban regression subset: 54 tests passed.
- Capture regression: 15 tests and five subtests passed against installed source.
- Independent review found and fixed invalidated context with unchanged version,
  legacy module-level side effects before rejection, and an official entrypoint
  blocking historical readback. No outstanding concrete finding in this scope.

Publication changes are installed. Topic components are not installed/enabled
in the gateway. Authenticated ingress, approval veto, outbox/receipts and the
end-to-end acceptance matrix remain required before enabling the new queue.
