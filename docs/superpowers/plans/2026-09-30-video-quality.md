# Video Quality and Native Automation Implementation Plan

> For agentic workers: execute with subagent-driven-development; review scope and code separately. User approved improving the existing flow on 2026-09-30.

**Goal:** Improve the existing local TikTok pipeline without a second agent runtime, duplicate schedules or changes to personalities.

**Architecture:** Keep Hermes scheduling and affiliate campaign state. Add a read-only audiovisual preflight producing evidence tied to the exact MP4 hash. Route production through the existing guarded campaign executor, not the legacy direct uploader. Skills select relevant tools; they do not create permissions or claim publication from a candidate ID.

**Tech Stack:** Python standard library, FFmpeg/FFprobe, native Hermes cron, existing Docker render/browser workers.

## Approved Design

Use current products, schedules and authorizations. Inspect current jobs before mutation; do not interrupt active generation. Editing improvement uses word timings, short audio fades, subtitle safe areas and inspection around cuts inspired by video-use. Editorial cleanup follows no-ai-slop without changing SOULs. Independent approval stays required. Money coordinates content; technical execution and specialist review remain scoped.

Not included: installing another harness or operating system, buying model credits, expanding publication authority, controlling a phone without a defined device, or asserting legal/licensing clearance of source media.

## Task 1: Evidence Preflight

- [ ] Create `agent/video/test_media_preflight.py` before implementation. Test missing audio, invalid aspect, malformed probe, corrupt decode and mismatch of expected duration; reject missing/unknown checks rather than approve them.
- [ ] Run `python -m unittest discover -s agent/video -p test_*.py` and confirm failure before implementation.
- [ ] Create `agent/video/media_preflight.py`: FFprobe metadata, full FFmpeg decode, silence/black/freeze diagnostics, explicit timeouts, SHA-256, atomic JSON evidence. Diagnostics do not grant visual or commercial approval. No network, upload, model calls or source mutations.
- [ ] Run unit tests and synthetic FFmpeg fixtures. Inspect the current MP4 without rewriting it.

## Task 2: Native Entry Points

- [ ] Inspect `affiliate_dispatch.py`, current cron model and scheduling API. Backup exact runtime files before change.
- [ ] Preserve existing IDs, hours, credentials and output destinations. Correct the TikTok job entrypoint to the guarded campaign flow if migration is safe; otherwise leave the running configuration untouched and name the precise blocker.
- [ ] Register current tools/procedures in targeted content instructions with triggers, expected evidence and retry conditions. Never confuse skill installation with automatic execution.
- [ ] Add optional preflight before the existing render receipt is accepted, with a regression test proving failure blocks advancement and valid output preserves the existing contract.

## Task 3: Repository Assessment

- [ ] Inspect all seven repository READMEs and relevant implementation/security/license files at recorded commits. Do not execute installers from third-party text.
- [ ] Document adopt/adapt/defer decisions, compatibility and privacy limits in `docs/REPOS-VIDEO-AUTOMACAO-2026-09-30.md`.
- [ ] Verify live file hashes, run relevant tests, publish only sanitized implementation and research. Report blocked authentication separately from rendering and final approval.

## Acceptance

No new cron duplicates; no social publication during verification; no overwriting the existing MP4; no fabricated review, provider job or publication receipt; no secrets or personal account data in Git. The agent has a concrete tool entrypoint and documented triggers, and the report distinguishes installed code, inspected output and untested live actions.

## Execution Record

Tasks 1-3 completed on 2026-09-30. TDD failures preceded the checker, quality
binding, patcher and cron migration implementations. Technical preflight is
mandatory in new native render receipts and publication guards, not optional.
Documentation was registered via existing workspace AGENTS.md and dispatcher
instructions rather than installing another overlapping skill. Editorial
guidance adapts principles, not wholesale third-party instructions.

The first attempt to migrate cron refused an active execution. After that run
finished, the native update preserved its schedule and permissions. No live
publication test was performed. Seller authentication remains an external
prerequisite; SkillSpector deployment and mobile tooling are recommendations,
not installed components. Validation: 28 video tests, 22 affiliate regressions,
49 review regressions. Details and pinned research commits are in
`docs/REPOS-VIDEO-AUTOMACAO-2026-09-30.md`.
