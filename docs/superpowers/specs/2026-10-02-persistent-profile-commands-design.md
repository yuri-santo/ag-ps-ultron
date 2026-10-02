# Persistent Profile Commands Design

## Goal

Expose Ultron as the named default profile in the user's conversations and let
the owner persistently select a specialist with an authorized slash command.
The selected profile remains active for that conversation until another profile
command is used. `/ultron` returns the conversation to Ultron.

## Scope

- The native internal `default` profile remains the primary Hermes profile. It
  is displayed and documented as **Ultron**, avoiding a second adapter,
  duplicate credentials or a second default memory store.
- The owner can send `/ultron`, `/pink`, `/cerebro`, `/cris`, `/greg`, or any
  installed, allowlisted profile name. A command may include a question after
  the profile name; without a question it only changes the active profile.
- The active selection is durable by platform, bot account, owner, chat and
  thread, and is read before topic-queue triage. It is not shared across chats.
- `/profile` reports the visible profile name currently selected for that
  conversation. `/ultron` is always the default/fallback selection.
- Normal unprefixed messages route to the selected profile. When no explicit
  selection exists, they route to Ultron.
- The profile choice is authorized through the existing native command path;
  unknown names, non-owner commands and malformed commands do not mutate state.
- Existing native `/stop`, `/new`, approvals, media handling and profile routes
  keep their behavior. A slash profile command must never be sent to the LLM as
  ordinary text.

## Personality

- Ultron retains the current useful context, direct PT-BR conversation style,
  tools and orchestration. Its presentation adopts Jarvis: calm, exact,
  discreetly witty and occasionally dry when the context warrants it. Sarcasm
  is never used in health, crisis, sensitive personal, legal or error recovery
  responses. It does not impersonate or claim to be Marvel canon.
- Pink and Cérebro use distinct, recognizable character-inspired voices while
  retaining their existing memory and reasoning roles. Pink is warm, eager and
  concise; Cérebro is strategic, analytical and politely impatient with weak
  assumptions.
- Cris and Greg use an everyday, observational comedic cadence inspired by
  `Todo Mundo Odeia o Chris`, appropriate to professional/personal boundaries.
  Cris remains corporate; Greg remains personal. Neither quotes scripts,
  represents actors, uses slurs or makes comedy override accuracy.
- Every profile receives one short, original catchphrase guideline for moments
  where it fits. It is optional, never repeated mechanically, never used in a
  formal report or safety-sensitive response, and is not a copied famous quote.
- Personalities live only in private SOUL/profile configuration. Public docs
  describe roles and behavior, never personal context or credentials.

## Architecture

1. Add a small private profile-selection store under the existing local Hermes
   root. Its key is the canonical source scope; it stores the internal profile
   name, timestamps and a versioned schema. It accepts only the primary default
   profile or directories with required profile configuration.
2. Add an authorized gateway command interceptor before normal slash processing.
   It parses exact slash commands, resolves `ultron` to the internal `default`
   profile, saves the selection and optionally turns the trailing text into a
   normal request with the selected source profile. `/profile` is read-only.
3. Add a source-profile overlay at the existing gateway routing boundary. It
   selects the persisted profile only for the authenticated owner and only when
   no more-specific native `profile_routes` rule applies. This avoids hijacking
   dedicated integrations or secondary bots.
4. The topic queue reads the effective source profile before semantic triage.
   Explicit profile selection constrains the triage roster to that profile for
   that ingress; it cannot silently substitute Cérebro. The selected profile
   still goes through the same worker restrictions, domain review and final
   audit.
5. Use a native adapter command registration mechanism so Telegram offers the
   supported commands and routes them before LLM text handling. The interceptor
   returns concise confirmation with the visible profile name only after durable
   persistence succeeds.

## Failure Behavior

- Storage failure leaves the existing selection unchanged and returns no false
  confirmation. The native command error path remains responsible for retry.
- If a previously selected profile is removed or invalid, the store is not
  trusted; the request falls back to Ultron and the stale selection is cleared.
- A selected profile that is unavailable in the multiplex gateway does not
  invoke a generic Cérebro fallback. It reports an availability failure and
  retains the selection for a later retry.
- Commands never grant tools or cross-profile secret access. The chosen profile
  receives only its own private configuration and existing allowed tools.

## Test Plan

- Unit tests for parsing commands, scope isolation, `ultron` alias handling,
  invalid/missing profile rejection, owner authorization and stale selections.
- Gateway boundary tests show `/pink` persists selection, `/profile` reports it,
  a following normal message uses Pink, and `/ultron` restores the default.
- Tests prove a dedicated native route wins over a persistent selection and
  that commands do not reach the LLM/text batcher.
- Topic queue tests prove a selected profile pins the topic contract and does
  not allow semantic triage to replace it with Cérebro.
- Configuration tests prove personality text preserves hard safety rules,
  excludes copied catchphrases and keeps formal/sensitive contexts neutral.
- Run the relevant gateway/topic-queue suite in isolated homes, then restart
  the local gateway and verify only the authenticated owner scope is affected.

## Acceptance

- A fresh conversation says its active profile is Ultron and uses the existing
  Ultron capability set.
- `/pink` changes that conversation to Pink, `/profile` confirms Pink and a
  subsequent ordinary message is answered by Pink.
- `/ultron` restores Ultron persistently.
- No selection leaks between chats/threads or bypasses profile permissions.
- The active-profile name is visible in user-facing status without exposing
  internal paths, secrets or raw SOUL text.
