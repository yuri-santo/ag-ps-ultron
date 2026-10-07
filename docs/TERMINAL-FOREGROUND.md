# Terminal foreground compatibility

On 2026-10-07, both the Shorts noon job and a direct spreadsheet request
stopped on identical terminal calls. Stored tool results showed an argument
error before command execution: background=false, notify=false, heartbeat=60
or 120. The loop guard correctly stopped repeated errors.

The narrow runtime patch ignores heartbeat only for foreground calls with
explicit notify=false and no legacy notification/watch request. It does not
change the command, authorization, execution mode, PTY rules or loop limits.
Background heartbeat and genuine conflicting notification requests retain
native behavior. No model upgrade or review queue was introduced.

Patch: `agent/transport/terminal-foreground.patch`. Apply to the matching
Hermes source with `git apply --check` before `git apply`; do not blindly
apply after an upstream update. Back up the runtime file first and restart
the gateway when idle. The local backup is the adjacent
`terminal_tool.py.before-foreground-20261007`.

Regression: 2 failing reproductions before the patch, then 5 passing focused
tests plus 23 native heartbeat/watch-pattern tests. Run the focused file with
the installed Hermes directory on PYTHONPATH. A harmless real terminal probe
is required after installation; unit tests do not prove the old workbook
was delivered or a video published. Do not replay publication outside its
authorized window or fabricate a successful delivery.
