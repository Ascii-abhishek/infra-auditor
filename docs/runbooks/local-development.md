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
SYS_ENV=dev
INFRA_AUDITOR_AWS_PROFILE=your-sso-profile
INFRA_AUDITOR_LOG_FORMAT=console
INFRA_AUDITOR_WEB_HOST=127.0.0.1
INFRA_AUDITOR_WEB_PORT=8008
```

Do not put database passwords or AWS keys in `.env`.

## Live Read-Only Collection

After AWS permissions, Secrets Manager secrets, and network access are ready:

```bash
uv run infra-auditor discover aws --instance raptor-catalog
uv run infra-auditor collect --instance raptor-catalog
uv run infra-auditor collect --instance udb
```

Compatibility snapshots and split service/subservice artifacts are written
under `s3://infra-audit-rl-dev/raw/snapshots/...` unless `SYS_ENV=prod` is
explicitly set by the runtime environment.

## Local Report UI

After S3 read permissions are available:

```bash
./run.sh
```

## Local MCP Server

After S3 read permissions are available, run the MCP server with:

```bash
uv run infra-auditor mcp
```

Open `http://127.0.0.1:8008`.

The direct command is still available when dependency sync is not needed:

```bash
uv run infra-auditor serve
```

## Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```
