# Agent Guide

## Purpose

`infra-auditor` is a deterministic infrastructure/database auditor. V1 audits AWS RDS PostgreSQL and produces normalized evidence snapshots that deterministic rules and later LLM analysts can consume safely.

## Current Phase

V0.1 bootstrap. The repo has a small read-only collection path: settings, validated resource registry, RDS discovery, Secrets Manager credential boundary, PostgreSQL database inventory, and local JSON snapshots.

## Read First

Before meaningful work, read:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `decisions.md`
- `docs/project-status.md`
- `docs/security-boundaries.md`
- relevant nested `AGENTS.md` files or docs for touched modules

Also inspect `git status --short` before editing.

## Absolute Boundaries

- Do not give production credentials, secret values, connection strings with passwords, or AWS keys to any LLM.
- Do not add generic SQL execution APIs such as `execute_sql(sql)` or `run_query(sql)`.
- Do not implement automatic remediation in V1.
- Do not modify AWS, IAM, RDS, PostgreSQL roles, parameter groups, security groups, or database objects unless a future approved remediation design explicitly allows it.
- Do not collect application table rows.
- Do not collect unrestricted query text without a documented redaction/minimization design.
- Do not weaken `docs/security-boundaries.md` without explicit owner discussion.

## Commands

```bash
uv sync
uv run infra-auditor --help
uv run infra-auditor config validate
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Use `uv run ruff format .` when formatting is needed.

## Coding Conventions

- Use Python 3.12+ and explicit types.
- Prefer small domain modules over broad `utils.py` files.
- Keep external services behind testable boundaries.
- Use Pydantic v2 models for validated settings, configuration, evidence, snapshots, findings, and secret schemas.
- Use timezone-aware UTC timestamps.
- Keep collectors and deterministic rules separate.
- Preserve partial failures as structured collection gaps.
- Avoid hidden globals, broad mutation, large connection pools, and inheritance-heavy frameworks.

## Dependency Rules

- Prefer current official documentation for library/service behavior.
- Record important official sources in `docs/research-sources.md`.
- Do not add deferred dependencies such as SQLAlchemy, pandas, LangChain, LlamaIndex, OpenAI SDK, Anthropic SDK, MCP SDK, Pydantic AI, FastAPI, Celery, or Redis until an implemented capability needs them.
- Document non-trivial dependency changes in `decisions.md`.

## Secrets And Config

- Runtime settings use `INFRA_AUDITOR_` environment variables and optional local `.env`.
- `.env` is local-only and gitignored.
- Human-managed YAML says what to audit; AWS discovery says what resources currently look like.
- YAML must not contain passwords, endpoints, AWS account IDs, VPC IDs, subnet IDs, security group IDs, allocated storage, instance class, or engine versions.
- V1 production DB credentials come from AWS Secrets Manager, one secret per RDS instance.

## Database Access

- Use psycopg 3.
- Use TLS; never use `sslmode=disable`.
- Use context managers and avoid connection leaks.
- Keep concurrency deliberately bounded because the auditor login role has connection limit 2.
- Use fixed SQL with bound parameters; dynamic identifiers require safe psycopg composition.

## Documentation Obligations

- Update `decisions.md` for non-trivial architecture, dependency, security, data-model, persistence, or external-service decisions.
- Update `docs/runtime-flows.md` whenever execution flow changes.
- Update `docs/project-status.md` after meaningful sessions.
- Keep docs concise and useful for cross-chat/cross-agent handoff.

## Collaboration Style

- Treat the owner as a collaborating system builder, not a ticket queue.
- After meaningful investigation or setup, briefly recap what happened, what it
  means, and what remains uncertain.
- Before moving to the next production milestone, cross-check the next step and
  its rationale with the owner.
- Prefer short teaching notes that fill context gaps, especially around AWS
  identity, security boundaries, database permissions, and runtime flow.
- Do not silently skip phases from `docs/project-status.md` or
  `docs/roadmap.md` just because implementation looks easy.

## Comprehension Gate

Before marking major features or complex architectural work accepted, ask a short 2-3 question quiz covering execution flow, failure mode, security boundary, or architecture rationale.

## Deeper Docs

- Stable architecture: `ARCHITECTURE.md`
- Current handoff: `docs/project-status.md`
- Runtime flow: `docs/runtime-flows.md`
- Security: `docs/security-boundaries.md`
- Config: `docs/configuration.md`
- Data contracts: `docs/data-contracts.md`
- Planned rules: `docs/audit-catalog.md`
- Observability: `docs/observability.md`
- Testing: `docs/testing.md`
- Roadmap: `docs/roadmap.md`
