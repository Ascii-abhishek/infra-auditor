# Architecture

## Goals

`infra-auditor` collects deterministic operational evidence about infrastructure and databases, starting with AWS RDS PostgreSQL. The evidence is meant for deterministic rules first and safe LLM-assisted analysis later.

The V1 architecture optimizes for production safety, least privilege, correctness, evidence traceability, and developer comprehension.

## System Shape

```text
Typer CLI
  -> Pydantic Settings
  -> validated resource registry
  -> AWS read-only discovery and operational evidence
  -> Secrets Manager credential provider
  -> psycopg PostgreSQL connection factory
  -> deterministic collectors
  -> deterministic rules
  -> typed snapshot
  -> S3 JSON snapshot
  -> split raw S3 artifacts by service/heuristic boundary
  -> snapshot/fleet report summary
  -> local FastAPI report console
  -> MCP read tools plus controlled latest/today-data sync

Future:
typed snapshot/report -> optional LLM analyst
```

## Component Boundaries

- `infra_auditor.config`: settings and non-secret YAML registry validation.
- `collectors.aws`: read-only AWS API boundaries for RDS discovery, attached
  security group ingress, CloudWatch RDS metrics, RDS recommendations, pending
  maintenance, and parameter groups.
- `secrets`: credential-provider boundary, currently AWS Secrets Manager.
- `collectors.postgres`: PostgreSQL connection and fixed SQL collectors.
- `models`: versioned evidence, snapshot, and future finding contracts.
- `storage`: snapshot persistence, currently S3 JSON.
- `rules`: deterministic finding logic over normalized evidence.
- `reports`: deterministic snapshot and fleet report summaries over raw
  snapshots.
- `ui`: local FastAPI/Bootstrap report console with separate templates/static
  assets.
- `mcp`: tool interface over approved snapshot/report data, plus controlled
  latest/today-data sync that calls the existing read-only collector workflow.
- `llm`: future explanatory analyst layer only.

## Collection Architecture

Collectors collect observed facts. They do not decide severity, apply remediation, or hide partial failures. A missing permission, missing extension, timeout, or unavailable database is captured as a structured collection gap.

The current PostgreSQL collector only reads:

```sql
SELECT datname, datallowconn, datistemplate
FROM pg_catalog.pg_database
ORDER BY datname
```

It classifies system/template databases separately from application databases
without querying application schemas or tables.

The current PostgreSQL security collector also reads role attributes from
`pg_catalog.pg_roles` and role membership edges from `pg_catalog.pg_auth_members`.
It does not query `pg_authid` or collect password-bearing fields.

The current PostgreSQL activity collector reads aggregated metadata from
`pg_catalog.pg_stat_activity`, including connection counts, application names,
states, wait event types, and bounded age summaries. It intentionally does not
collect SQL query text.

## Normalized Evidence

Snapshots are Pydantic models with:

- application and snapshot schema versions,
- run ID,
- UTC timestamps,
- environment and region,
- per-instance AWS metadata,
- AWS network, metric, and operational evidence,
- database inventory,
- PostgreSQL activity summary evidence,
- collector statuses,
- collection gaps.

Snapshot schema versioning is separate from application semantic versioning.

## Rule Engine

The first deterministic AWS/RDS, PostgreSQL activity, and PostgreSQL security
rules are implemented. They read normalized evidence and produce findings with
evidence references.
Rules must keep observed facts, organization policy, vendor/default context,
thresholds, and recommendations separate.

## Reporting

The first reporting layer produces JSON-friendly snapshot and fleet report
models over raw snapshots. The local FastAPI report console renders those
reports, raw JSON, and Markdown/JSON exports for development review. SES email
summaries remain deferred.

## Future LLM Layer

The LLM analyst is deferred. It may receive normalized evidence, deterministic findings, sanitized query metadata, and configuration context. It must not receive credentials, AWS keys, raw secrets, application rows, unrestricted query text, or arbitrary live database access.

Pydantic AI is the preferred framework to evaluate when this phase begins, using current official docs and skills at that time.

## MCP Layer

The first MCP layer is implemented as a local stdio server:

```bash
uv run infra-auditor mcp
```

It exposes read tools over configured instances, S3 snapshot listings, latest
deterministic reports, filtered finding summaries, and latest split raw
artifacts. It also exposes `sync_latest_audit_data`, which calls the existing
read-only collector workflow for configured aliases and writes immutable S3
audit artifacts, and `sync_today_audit_data`, which skips aliases that already
have a snapshot for the current UTC day. MCP tools must not expose generic SQL,
arbitrary AWS API calls, arbitrary S3 key reads, secret values, query text,
shell bridges, or remediation.

## Storage

V0.1 writes raw JSON snapshots to S3:

```text
s3://infra-audit-rl-<SYS_ENV>/raw/snapshots/snapshot_schema=<version>/env=<dev-or-prod>/region=<region>/service=<service>/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

`SYS_ENV` is `dev` or `prod` and defaults to `dev` when unset. The writer uses
conditional `PutObject` so an existing snapshot object is not overwritten.
The current implemented service partition is `rds-postgres`.

Collections also write service/subservice raw artifacts in parallel under:

```text
s3://infra-audit-rl-<SYS_ENV>/raw/snapshots/artifact_schema=<version>/snapshot_schema=<version>/env=<dev-or-prod>/region=<region>/service=<service>/subservice=<subservice>/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

The current split services/subservices are:

- `rds/instance` for RDS DB instance discovery evidence.
- `rds/operations` for RDS maintenance, recommendations, and parameter groups.
- `postgres/database-inventory` for database inventory.
- `postgres/activity-summary` for PostgreSQL activity summaries.
- `postgres/role-security` for PostgreSQL role attributes and memberships.
- `rds/ec2-security-groups` for attached EC2 security group ingress.
- `rds/cloudwatch-rds-metrics` for CloudWatch RDS metric summaries.
- `audit-heuristics/deterministic-findings` for deterministic findings.

Expected future historical storage:

```text
S3 -> Parquet -> Glue Catalog -> Athena
```

A DynamoDB latest-state cache may be evaluated later. A separate PostgreSQL database solely to monitor PostgreSQL is not the default direction.

## Deployment Evolution

Local CLI comes first. Expected future deployment direction is Docker, ECR, ECS Fargate, EventBridge Scheduler, Secrets Manager, CloudWatch Logs, S3, and SES.

Terraform adoption is deferred until deployment requirements are finalized.

## Extensibility Model

The project is `infra-auditor`, not `postgres-mcp`. Future collectors may live under service-specific packages such as `collectors/opensearch`, `collectors/qdrant`, or `collectors/airflow`. Use small protocols at external boundaries; do not force every service into a single inheritance hierarchy.
