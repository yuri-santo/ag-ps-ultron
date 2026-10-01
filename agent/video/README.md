# Video quality tooling

Local evidence for the existing Ultron affiliate pipeline. Python 3.11+ and
FFmpeg/FFprobe on PATH are sufficient; no model key, browser or paid service.

```sh
python media_preflight.py /path/to/video.mp4 --output /path/to/preflight.json
python -m unittest discover -s . -p 'test_*.py'
```

`technical_pass` checks portrait display aspect, audio metadata, duration and
full decoding. Black, silence and frozen sections are warnings requiring
inspection. The report always leaves `visual_approval=not_reviewed`. It is not
a claim of product identity, subtitle quality, originality, legal clearance,
medical accuracy or permission to publish. Input files are not modified.

## Existing Local Installation

`affiliate_quality.py` adds 30 ms fades to voice segments and binds the report
hash to the render receipt. `patch_affiliate.py` stages scoped patches for the
existing private runtime without copying account data to this repository:

```sh
python patch_affiliate.py /root/tools/tiktok /path/to/independent-staging
```

This command only stages source. Before deployment, back up current files,
verify there is no active render, compare the staged diff and run tests.
Install the two helper modules and `VIDEO-QUALITY.md` beside the existing
renderer, then the staged files. Preserve file ownership/access boundaries.
Point the workspace's existing AGENTS.md at `VIDEO-QUALITY.md` for script,
assembly and review requests, retaining its other instructions.
The private affiliate pipeline and credentials are not bundled; this is not
a complete TikTok installation from a fresh clone.

The native integration test is opt-in because it requires the local renderer:

```sh
ULTRON_NATIVE_RENDER_TEST=1 python -m unittest discover -s . -p 'test_native_render.py'
```

It renders only temporary synthetic test footage and generated sine audio;
no real TTS, account, browser or publication is invoked. Its fixture bypasses
brief validation only inside test mocks, never in installed runtime code.

## Cron Payload

`cron_migration.updates_for(job)` returns only `prompt` and `context_from`.
Use the native Hermes `cron.jobs.update_job` API after inspecting the actual
job and confirming no active claim. Keep the existing ID, hours, permissions,
skills, delivery settings and execution history. Clearing `context_from`
prevents replaying old execution text containing legacy uploader instructions;
it does not delete history. Do not create another scheduler or duplicate job.

## Marketplace Channels

`marketplace_channels.py` preserves the owner's original affiliate URLs and
separates Mercado Livre external campaigns from native TikTok Shop products.
Classification never proves commission, product identity or creator eligibility.
`patch_marketplace_channels.py` provides scoped, idempotent transformations for
the existing autonomy and publication guard. The deployment helper also updates
the existing pool and dispatcher after an encrypted backup; it is not a clean
installation of the private pipeline. See [channel policy](MARKETPLACE-CHANNELS.md).

The external executor rejects all Shop requests, even with a supplied product
ID. A separate native Shop executor with actual eligibility, SKU verification
and a receipt is still required. No marketplace mutation is performed by tests.

## Publication Entry Points

`publication_policy.py` rejects emojis in new captions, narration, comments and
subtitles. It also rejects a limited set of unsupported promises (such as free
shipping, approved lab reports, exclusive discounts or guaranteed results).
This is not a general factual verifier. There is no evidence override yet:
generic approval flags cannot validate a current offer or a pinned comment.
Rejected text must be revised and reviewed again, never silently rewritten.

`patch_publication.py` stages version-pinned changes to existing entry points:
the legacy TikTok uploader refuses `TIKTOK_PUBLISH=1`; the official campaign
path keeps its review guards; historical comment reconciliation remains
read-only and preserves exact old text. YouTube affiliate templates no longer
add emojis, and its uploader validates text before account authentication.
Affiliate URLs, schedules, campaign state and historical posts are untouched.

```sh
python patch_publication.py /root/tools /path/to/independent-staging
ULTRON_NATIVE_PUBLICATION_TEST=1 python -m pytest agent/video/test_patch_publication.py -q
```

The native test accepts the supported original or exactly migrated source; it extracts
pure validators/text factories and never imports or invokes a publisher. Stage
and review the diff, back up affected files, verify publishers are idle, install
the policy helper beside each publisher, then the staged source. This migration
does not install the private account pipeline from scratch. Its exact hash
checks deliberately reject unrelated source changes.

Installed locally on 2026-10-01 after an encrypted backup: seven patched sources
and two policy helpers. The gateway was idle, stopped briefly during replacement
and restarted. No real post or marketplace item was created during validation.

## Rollback

Restore only affected code/payload from the private backup after draining the
relevant execution. Do not restore old campaign databases, repeat a post or
rewrite approval receipts. The 30/09 deployment backup is Restic `80266082`.

Research and adoption decisions: [repository assessment](../../docs/REPOS-VIDEO-AUTOMACAO-2026-09-30.md).
