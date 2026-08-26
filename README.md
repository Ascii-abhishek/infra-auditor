# infra-auditor

`infra-auditor` is a deterministic infrastructure and database auditor. V1 starts with AWS RDS PostgreSQL evidence collection and is designed to expand later to services such as OpenSearch, Qdrant, Airflow, and other infrastructure.

The first implementation deliberately avoids LLMs, MCP, live remediation, S3, SES, and Terraform. It builds the read-only evidence path first.

## Current V1 Scope

- Validate non-secret local configuration.
- Discover configured RDS PostgreSQL instance metadata through read-only AWS APIs.
- Resolve per-instance PostgreSQL auditor credentials from AWS Secrets Manager.
- Connect to PostgreSQL with psycopg 3 over TLS.
- Collect safe database inventory from `pg_catalog.pg_database`.
- Write a minimal versioned JSON snapshot under gitignored `data/snapshots/`.

## Setup

```bash
uv sync
uv run infra-auditor --help
uv run infra-auditor config validate
uv run pytest
```

Copy `.env.example` to `.env` only for local non-secret settings such as AWS profile, log format, or paths. Do not put database passwords, AWS keys, RDS endpoints, VPC IDs, subnet IDs, or security group IDs in `.env` or YAML configuration.

## Example Commands

```bash
uv run infra-auditor config validate
uv run infra-auditor discover aws --instance raptor-catalog
uv run infra-auditor collect --instance raptor-catalog
```

Live AWS/RDS commands require the owner's read-only IAM permissions and Secrets Manager secrets described in the runbooks. Unit tests do not require production AWS or PostgreSQL access.

## Architecture And Safety

Start with [AGENTS.md](/home/abhishek/projects/infra-auditor/AGENTS.md), [ARCHITECTURE.md](/home/abhishek/projects/infra-auditor/ARCHITECTURE.md), [decisions.md](/home/abhishek/projects/infra-auditor/decisions.md), and [docs/project-status.md](/home/abhishek/projects/infra-auditor/docs/project-status.md).

Security boundaries are intentionally strict:

- No production credentials go to LLMs.
- No generic SQL MCP tool will be exposed.
- No automatic remediation exists in V1.
- Collectors are read-only and must not fetch application table rows.
- Query text is minimized and treated as potentially sensitive.
