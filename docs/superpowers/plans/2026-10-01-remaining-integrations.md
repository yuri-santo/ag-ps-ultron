# Remaining Native Integrations Implementation Plan

> For agentic workers: use subagent-driven-development for bounded work and
> independent review. Continue the approved topic-queue specification; no new
> runtime, unrestricted tool access or parallel scheduler is authorized.

**Goal:** Complete verified integrations that fit the local agent, preserve the
owner's TikTok Shop hold, and advance the approved queue through delivery gates.

**Architecture:** Hermes native Kanban owns scheduling/claims. Private topic
metadata owns approval and outbound receipts. Existing tool adapters remain the
authority for permissions. External repositories are either pinned isolated
tools, adapted source/contracts, or explicitly documented references.

**Tech Stack:** Python 3.11/WSL, native Hermes APIs, SQLite, pytest, pinned tools.

## Repository Adoption

- [x] Compare prior decisions to live files/commands and source revisions.
- [x] Keep Shop mutations blocked by the existing marketplace guard and record
  the explicit owner hold in operating instructions; do not pause external ML.
- [x] Install only missing compatible tools justified by the approved adoption
  decisions. Isolate SkillSpector from Hermes Python and from credentials/network
  during scans. Fail closed when a required isolation capability is unavailable.
- [x] Verify existing marketing, transcription, video, PhoneHarness and research
  adapters. Do not install an OS, second harness, emulators or abandoned service
  solely to claim the repository was used. Record concrete blockers separately.
- [x] Add/update tests before behavioral changes and document actual executable
  commands, profile bindings and limits, not only a catalog of projects.

## Approval And Outbox

- [x] Map live review records, restricted worker results, native pre-transition
  seams and Telegram receipt behavior without reading account secrets.
- [x] Add failing tests in `agent/topic_queue/test_delivery.py` for exact
  source/version/profile/candidate binding, domain review requirements,
  independent fast-topic delivery, stale revision invalidation, duplicate
  approval, per-part receipts and uncertain-send recovery.
- [x] Implement `agent/topic_queue/delivery.py` using the existing private store
  and trusted evidence readers. No tool/CLI may manufacture approval by setting
  a boolean. Persist intent before send; unknown send outcomes never auto-repeat.
- [x] Hold the private revision lock during each bounded transport operation;
  per-conversation serialization must preserve part order. Confirm reply mappings
  only from receipts. Distinct completed topics do not wait for earlier drafts.
- [x] Run temporary-store failure-injection tests, then independent review.

## Native Gateway Integration

- [ ] Identify and test authorized ingress before busy buffering, commands,
  pause/cancel behavior, native completion capture and before-transition veto.
- [ ] Reuse the restricted worker where native execution would widen tools.
  Preserve native scheduling, per-profile capacity and resource limits.
- [ ] Connect approval/outbox only after temporary end-to-end tests demonstrate
  slow A/fast B, reopen, restart, unavailable review, and uncertain delivery.
- [ ] If an integration surface cannot yet satisfy the approved contract,
  preserve existing operation and report the exact unimplemented boundary;
  do not label disabled components as an operational queue.

## Deployment

- [x] Back up affected live files and configuration. Deploy only at idle or
  explicitly owner-authorized maintenance;
  credentials, SOULs, personal state and account cookies stay out of Git.
- [x] Validate installed entrypoints without posting, spending, changing account
  security, or sending a test message to third parties.
- [ ] Record verification evidence and unresolved boundaries; commit and push
  only source, tests and sanitized documentation.

## Verified Checkpoint

01/10/2026: 360 tests passed, 7 skipped, 163 subtests passed across adoption,
topic metadata, review, meeting, video and PhoneHarness launcher. An additional
18 worker-proof tests passed with explicit installed-source opt-in. Skip
conditions and component mocks do not imply account-level integration.

Independent review found and tests reproduced: restrictive umask, Docker pull
fallback, installation snapshot race, ambiguous service state, Docker context
mismatch and a single uncertain delivery blocking unrelated approved topics.
All have targeted fixes. Full independent review could not finish after the
reviewer's execution limit; remaining code was manually inspected and tested.

SkillSpector Docker built and real static scan run offline (partial coverage,
not approved). Maestro 2.11.0 installed and version checked on Windows. Native
adapters installed after the owner authorized interrupting the maintenance
wait. Gateway stopped via systemctl, installer backup/applied hashes verified,
then gateway restarted. Native plugin registration verified; channels connected.
Restic backup: 89fe447e. Money guide access additionally fixed via native
skill_view with preprocess=False; all ten installed guides read successfully.
No job manually marked complete, claim cleared or
publication retried. Shop owner hold is explicit. No new cron or publication.
