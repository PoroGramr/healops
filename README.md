# HealOps

AI-powered self-healing infrastructure for Docker (MVP). Kubernetes is a future adapter, not implemented. [한국어](README.ko.md)

> Status: early development. Do not attach the worker to a production Docker daemon. Monitoring is read-only by default; no automatic deployment.

## Architecture

React dashboard → authenticated FastAPI/SQLite API ← authenticated worker → Docker daemon. Only the isolated worker receives Docker socket access. Docker operations are limited to an explicit container allowlist. An optional OpenAI-compatible diagnosis provider is isolated from execution.

## Quick start

See [deployment guide](docs/deployment.md). Set distinct API and worker tokens in a private `.env` copied from `.env.example`; use Docker Compose only on a development Docker daemon. No public ports should be opened.

## Security

The Docker socket grants host-level control: never put untrusted containers on its daemon. An allowlist is application-level protection, not Docker socket privilege reduction. No LLM is permitted to run commands. See [security](docs/security.md).

## Roadmap

Monitor and incident tracking → rule-based and optional LLM diagnosis → approval-gated restart → worktree patch/PR and redeployment → Kubernetes adapter. Consult the docs and tests for actual status.

## Contributing

Open an issue before large changes. Run pytest and frontend tests; do not include secrets. Apache-2.0 licensed (see LICENSE).
