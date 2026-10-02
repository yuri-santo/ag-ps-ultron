# Laya Isolated Evaluation

**Goal:** Install and evaluate Laya for faster local Portuguese triage, without
giving it tools, changing personas, or bypassing delivery validation.

**Approved design:** Isolated installation and synthetic benchmarks first. No
production routing unless accuracy and latency demonstrate an improvement.
Hermes remains the fallback and sole executor. User approved this design in chat.

**Architecture:** Pinned npm package and pinned ONNX model revision; no live user
messages, credentials, or gateway hooks. A bounded systemd transient process
measures latency, memory, and accuracy. Results explicitly distinguish package
installation, model loading, benchmark completion, and production activation.

**Tech Stack:** Node 24, ONNX Runtime CPU, Laya 0.1.2, native node:test.

## Tasks

- [x] Add strict evaluation-only decision policy and tests for abstention,
  malformed probabilities, ambiguous messages, and oversized inputs.
- [x] Install exact npm package in an isolated local runtime with lockfile.
- [x] Download pinned model with SHA-256 checks against Hugging Face metadata.
- [ ] Benchmark synthetic Portuguese cases including greeting, email UIDs,
  explicit SAP requests, health acknowledgment, mixed topics, and injection.
- [x] Record measured results and resource limits. Keep production disabled if
  any activation criterion fails or evaluation cannot complete.

## Activation Criteria

No observed high-confidence wrong routing on the regression fixture, no loss
of multi-topic/context-dependent requests, warm p95 below 1 second, peak memory
within the isolated allowance, and a separate held-out Portuguese evaluation
before production adoption. A small fixture is not proof of general accuracy.
The published Apple CPU benchmark is not a measurement of this Windows/WSL host.

The model benchmark was attempted but stopped during loading due to host
responsiveness degradation. Accuracy and warm latency remain unmeasured;
production activation is rejected for the current host conditions.
