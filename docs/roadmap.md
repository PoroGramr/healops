# Roadmap

- [x] Docker allowlist event subscription plus periodic reconciliation, health/exit detection, incident persistence and deduplication
- [x] React dashboard with API-backed containers, incidents, rule-based and optional OpenAI-compatible diagnosis
- [x] LangGraph diagnostic subgraph stopping at human approval
- [x] Approval-gated, default-off Docker restart and basic stability verification
- [x] Exact-container policy auto-approval after repeated failure; isolated executor, Actuator verification, hourly circuit limit
- [x] Backend/worker unit tests, frontend smoke test, local broken-app demo, CI
- [ ] Metrics, deployment history, external alerting and broader HTTP endpoint assertions
- [ ] Fine-grained Docker socket authorization and durable queue/leases
- [ ] Codex CLI adapter with isolated worktree, patch review, sandboxed tests and PR generation
- [ ] Deployment artifact tracking, administrator redeployment and rollback (restart circuit limit exists; deployment circuit does not)
- [ ] Kubernetes plugin implementation

The raw-socket disposable demo worker is not suitable for production. The separate PW3 repair profile has a narrow executor but still carries Docker host-level risk; see [security](security.md).
