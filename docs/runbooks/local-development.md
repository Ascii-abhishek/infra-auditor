# Local Development Runbook

## Setup

```bash
uv sync
uv run infra-auditor --help
uv run infra-auditor config validate
uv run pytest
```

## Local Settings

Use `.env` for non-secret local settings only:

```bash
INFRA_AUDITOR_AWS_PROFILE=your-sso-profile
INFRA_AUDITOR_LOG_FORMAT=console
```

Do not put database passwords or AWS keys in `.env`.

## Live Read-Only Collection

After AWS permissions, Secrets Manager secrets, and network access are ready:

```bash
uv run infra-auditor discover aws --instance raptor-catalog
uv run infra-auditor collect --instance raptor-catalog
uv run infra-auditor collect --instance udb
```

Snapshots are written under `data/snapshots/`, which is gitignored.

## Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```
