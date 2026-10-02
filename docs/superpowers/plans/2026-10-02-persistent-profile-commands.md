# Persistent Profiles Implementation

Approved behavior: Ultron is the initial visible identity, profile commands
persist in each authorized conversation, `/perfil` reports the choice, and
character voices preserve current private context and permissions.

- [x] Inspect primary/native profile identity and the topic queue's missing Ultron executor.
- [x] Add scope-isolated persistent selection and immutable message snapshots.
- [x] Add authorized commands and native source routing for subsequent messages.
- [x] Add Ultron execution using the primary home, SOUL and configured tools.
- [x] Pin triage to the selected author while retaining Ultron specialist tools.
- [x] Add optional short catchphrases and persona guidance without exporting SOULs.
- [x] Test persistence, authorization, explicit native route precedence and command menus.
- [x] Install with private backup and verify a real approved primary response.
- [x] Document source, operational limits and recovery instructions.

The implementation retains unavailable selections, rather than silently
clearing them. Native routes keep precedence. Selections survive gateway
restarts; a new conversation without a selection starts in Ultron. Pending
requests keep the author selected when admitted. Catchphrases can include
short recognizable expressions; original mottos are identified as original.
