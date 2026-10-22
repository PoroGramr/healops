# Roadmap

- [x] Docker allowlist event subscription plus periodic reconciliation, health/exit detection, incident persistence and deduplication
- [x] React dashboard with API-backed containers, incidents, rule-based and optional OpenAI-compatible diagnosis
- [x] LangGraph diagnostic subgraph stopping at human approval
- [x] Approval-gated, default-off Docker restart and basic stability verification
- [x] Exact-container policy auto-approval after repeated failure; isolated executor, Actuator verification, hourly circuit limit
- [x] Backend/worker unit tests, frontend smoke test, local broken-app demo, CI
- [ ] Metrics, deployment history, external alerting and broader HTTP endpoint assertions
- [ ] Fine-grained Docker socket authorization and durable queue/leases
- [x] Opt-in Codex worktree/allowlist/networkless test/PR adapter; real synthetic PW3 Java patch → green Gradle suite → staging image deployed (PR path locally mocked)
- [x] Isolated PW3 MySQL/MinIO staging, networkless Gradle/Playwright candidate build, health-gated staging deployment and tested image rollback
- [x] PW3's separate Actions deploy script backs up image/env/Compose, restores on failed health checks, and marks planned deploys as HealOps maintenance (failure path offline-tested)
- [ ] Grounded production patch with sanitized evidence, real PR and CI review
- [ ] HealOps-managed production artifact tracking, canary/promotion and rollback (separate PW3 deploy script already has image/env/Compose rollback, not DB rollback)
- [ ] Kubernetes plugin implementation

The raw-socket disposable demo worker is not suitable for production. The separate PW3 repair profile has a narrow executor but still carries Docker host-level risk; see [security](security.md).
