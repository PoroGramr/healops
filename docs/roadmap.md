# Roadmap

- [x] Docker allowlist event subscription plus periodic reconciliation, health/exit detection, incident persistence and deduplication
- [x] React dashboard with API-backed containers, incidents, rule-based and optional OpenAI-compatible diagnosis
- [x] LangGraph diagnostic subgraph stopping at human approval
- [x] Approval-gated, default-off Docker restart and basic stability verification
- [x] Backend/worker unit tests, frontend smoke test, local broken-app demo, CI
- [ ] Metrics, deployment history, HTTP verification and alerting
- [ ] Fine-grained Docker socket authorization and durable queue/leases
- [ ] Codex CLI adapter with isolated worktree, patch review, sandboxed tests and PR generation
- [ ] Deployment artifact tracking, administrator redeployment, rollback and circuit breaker
- [ ] Kubernetes plugin implementation

Do not use the current worker against production containers. See [security](security.md).
