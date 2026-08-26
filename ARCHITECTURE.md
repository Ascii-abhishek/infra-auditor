# Architecture

## Goals

`infra-auditor` collects deterministic operational evidence about infrastructure and databases, starting with AWS RDS PostgreSQL. The evidence is meant for deterministic rules first and safe LLM-assisted analysis later.

The V1 architecture optimizes for production safety, least privilege, correctness, evidence traceability, and developer comprehension.

## System Shape

```text
Typer CLI
  -> Pydantic Settings
  -> validated resource registry
  -> AWS read-only discovery
  -> Secrets Manager credential provider
  -> psycopg PostgreSQL connection factory
  -> deterministic collectors
  -> typed snapshot
  -> local JSON snapshot

Future:
typed snapshot -> deterministic rules -> findings -> reports -> optional LLM analyst
```

## Component Boundaries

- `infra_auditor.config`: settings and non-secret YAML registry validation.
- `collectors.aws`: read-only AWS API boundaries, currently RDS `DescribeDBInstances`.
- `secrets`: credential-provider boundary, currently AWS Secrets Manager.
- `collectors.postgres`: PostgreSQL connection and fixed SQL collectors.
- `models`: versioned evidence, snapshot, and future finding contracts.
- `storage`: snapshot persistence, currently local JSON.
- `rules`: future deterministic rule engine.
- `reports`: future JSON/HTML/SES reporting.
- `llm`: future explanatory analyst layer only.
- `mcp`: future query interface to audit data only.

## Collection Architecture

Collectors collect observed facts. They do not decide severity, apply remediation, or hide partial failures. A missing permission, missing extension, timeout, or unavailable database is captured as a structured collection gap.

The current PostgreSQL collector only reads:

```sql
SELECT datname, datallowconn, datistemplate
FROM pg_catalog.pg_database
ORDER BY datname
```

It classifies system/template databases separately from application databases without querying application schemas or tables.

## Normalized Evidence

Snapshots are Pydantic models with:

- application and snapshot schema versions,
- run ID,
- UTC timestamps,
- environment and region,
- per-instance AWS metadata,
- database inventory,
- collector statuses,
- collection gaps.

Snapshot schema versioning is separate from application semantic versioning.

## Rule Engine

The deterministic rule engine is deferred. When added, it must read normalized evidence and produce findings with evidence references. Rules must keep observed facts, organization policy, vendor/default context, thresholds, and recommendations separate.

## Reporting

Reporting is deferred. Expected future outputs are JSON reports, HTML reports, and SES email summaries. Reports should emphasize changed/new/resolved and critical/high findings instead of dumping raw metrics.

## Future LLM Layer

The LLM analyst is deferred. It may receive normalized evidence, deterministic findings, sanitized query metadata, and configuration context. It must not receive credentials, AWS keys, raw secrets, application rows, unrestricted query text, or arbitrary live database access.

Pydantic AI is the preferred framework to evaluate when this phase begins, using current official docs and skills at that time.

## Future MCP Layer

MCP is deferred. Future MCP tools should query the audit system, for example `get_instance_summary(instance)` or `get_fleet_findings(severity=None)`. A generic `execute_sql(sql)` tool is forbidden.

## Storage Evolution

V0.1 writes local JSON under gitignored `data/snapshots/`.

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
