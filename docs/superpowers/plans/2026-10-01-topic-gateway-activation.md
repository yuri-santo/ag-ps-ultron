# Local Gateway Activation

The owner requested implementation of the already approved topic-queue design.
This plan does not change profile personalities, external authorizations or the
owner's TikTok Shop block.

## Tasks

1. Add a trusted runtime bridge in `agent/topic_queue/runtime.py`, with private
   execution/review/transport evidence, native Kanban ingress and final cards,
   native claims/spawn/capacity, bounded persistent retries and final approvals.
   Test using temporary homes/boards and injected workers/reviewers/transport.
2. Add `gateway_adapter.py`: authorized per-original text admission before the
   platform batcher; preserve native commands, stop and approval intercepts;
   one-attempt text delivery with actual Telegram message IDs and no previews.
3. Add an exact-source, fail-closed native installer/patcher. Route managed
   cards through restricted workers, require approval before native completion,
   suppress managed subscriptions and run outbox maintenance on native ticks.
4. Test independent completion order, dependency/revision fences, duplicates,
   ambiguous sends, restart recovery, command passthrough and profile boundaries.
5. Back up affected local runtime/config, install while stopped, verify imports,
   enable only the owner's authorized Telegram scope, restart and run controlled
   local integration probes. No unsolicited production test messages or posts.
6. Record actual activation, remaining limits and rollback in public/private
   documentation. Preserve unrelated repository/runtime modifications.

## Acceptance

Implemented and activated on 2026-10-01 for the owner's authorized text DM.
Native dispatcher/provider probe: two done cards, one final approval; no real
Telegram send. Regression: 434 passed, 7 skipped, 163 subtests passed. Operational
scope, provider limits and rollback: `docs/GATEWAY-POR-ASSUNTO.md`.

- Native Kanban owns scheduling and worker claims. No additional daemon or bot.
- Final text is frozen before independent, domain-aware validation.
- No candidate, review status or ambiguous retry leaks as a user answer.
- Tool execution is never blindly repeated after an uncertain process outcome.
- Owner/chat/account/thread and dependency versions remain bound to evidence.
- A failed or uncertain part cannot duplicate delivery or interleave multipart.
- Secrets and personal content remain only in private local state.
