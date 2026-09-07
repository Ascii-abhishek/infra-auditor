# infra-auditor

`infra-auditor` is a deterministic infrastructure and database auditor. V1 starts with AWS RDS PostgreSQL evidence collection and is designed to expand later to services such as OpenSearch, Qdrant, Airflow, and other infrastructure.

The first implementation deliberately avoids LLM analysts, live remediation,
SES, and Terraform. It builds the read-only evidence path first, persists raw
snapshots to S3, and exposes a constrained MCP read layer over approved
snapshot/report data with controlled latest-data and today-data sync.

## Current V1 Scope

- Validate non-secret local configuration.
- Discover configured RDS PostgreSQL instance metadata through read-only AWS APIs.
- Collect attached security group ingress, CloudWatch RDS metric summaries, RDS
  recommendations, pending maintenance, and parameter group evidence.
- Resolve per-instance PostgreSQL auditor credentials from AWS Secrets Manager.
- Connect to PostgreSQL with psycopg 3 over TLS.
- Collect safe database inventory from `pg_catalog.pg_database`.
- Collect safe PostgreSQL activity summaries from `pg_stat_activity` without
  query text.
- Collect PostgreSQL role attributes and role memberships.
- Produce deterministic findings for public exposure, RDS operations, resource
  pressure, connection hygiene, and risky role membership paths.
- Write canonical schema-2 JSON artifacts for RDS, PostgreSQL, and
  deterministic-finding boundaries under `raw/snapshots/schema=2/...`.
- Write a small completion manifest last so reports consume one coherent run
  without duplicating the full evidence payload.
- Build deterministic snapshot/fleet report summaries and serve a local
  FastAPI report console with RDS, Database (PG), Reports, Raw Data, and planned
  service sections.
- Expose local MCP tools over configured instances, latest reports, findings,
  completed-run listings, canonical artifacts, and controlled latest/today-data sync.

## Setup

```bash
uv sync
uv run infra-auditor --help
uv run infra-auditor config validate
uv run pytest
```

Use `.env` only for local non-secret settings such as `SYS_ENV=dev`, AWS profile, log format, or paths. Do not put database passwords, AWS keys, RDS endpoints, VPC IDs, subnet IDs, or security group IDs in `.env` or YAML configuration.

## Example Commands

```bash
uv run infra-auditor config validate
uv run infra-auditor discover aws --instance raptor-catalog
uv run infra-auditor collect --instance raptor-catalog
uv run infra-auditor mcp
./run.sh
```

Live AWS/RDS commands require the owner's read-only IAM permissions and Secrets Manager secrets described in the runbooks. Unit tests do not require production AWS or PostgreSQL access.

## Architecture And Safety

Start with [AGENTS.md](/home/abhishek/projects/infra-auditor/AGENTS.md), [ARCHITECTURE.md](/home/abhishek/projects/infra-auditor/ARCHITECTURE.md), [decisions.md](/home/abhishek/projects/infra-auditor/decisions.md), and [docs/project-status.md](/home/abhishek/projects/infra-auditor/docs/project-status.md).

Security boundaries are intentionally strict:

- No production credentials go to LLMs.
- No generic SQL MCP tool is exposed.
- No automatic remediation exists in V1.
- Collectors are read-only and must not fetch application table rows.
- Query text is minimized and treated as potentially sensitive.
