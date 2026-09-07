# Security Boundaries

This file contains safety rules for the project. Any change that weakens these boundaries requires explicit owner discussion.

## No Production Credentials To LLMs

GPT, Claude, or any future model must never receive PostgreSQL passwords, AWS secret keys, Secrets Manager secret values, IAM credentials, or database connection strings containing secrets.

## No Generic SQL MCP Tool

Never expose tools such as:

```text
execute_sql(sql)
run_query(sql)
query_database(sql)
```

Future live checks must use audited server-owned query templates such as `run_live_check(check_id="connection_details", instance="raptor-catalog", arguments={...})`.

## MCP Boundary

The base MCP server is local. Most tools are read-only over approved stored
audit data:

```bash
uv run infra-auditor mcp
```

Allowed MCP tools may read only approved audit artifacts:

- configured instance summaries without secret IDs,
- completed-run manifest listings for configured aliases,
- latest deterministic snapshot/fleet reports,
- filtered deterministic finding summaries,
- canonical raw artifact listings for approved service/subservice boundaries,
- latest canonical raw artifacts for approved service/subservice boundaries.

The only live MCP entrypoints are `sync_latest_audit_data` and
`sync_today_audit_data`. They may call the existing read-only collector workflow
for configured aliases and write immutable audit artifacts to S3. The today
mode may list the latest approved completed-run manifest for a configured alias
and skip collection when it is already under the current UTC day. The tools
must not accept AWS action names, SQL text, secret
IDs, raw S3 keys, or remediation instructions.

MCP tools must derive S3 prefixes from runtime settings, configured instance
aliases, and hard-coded approved service/subservice choices. Do not expose an MCP
tool that accepts arbitrary S3 keys, S3 prefixes, AWS service/action names,
SQL strings, shell commands, Secrets Manager secret IDs, or remediation actions.
Manifest references must match the complete hard-coded boundary set and the
canonical key derived from that manifest before any referenced S3 object read.

## No Automatic Remediation In V1

The system may recommend actions, but V1 must not automatically create/drop indexes, alter roles, grant/revoke permissions, alter tables/systems/databases, terminate sessions, reboot or resize RDS, change parameter groups, modify security groups, or apply RDS recommendations.

## Read-Only Collector

The intended PostgreSQL collector roles are:

```text
grp_rl_rds_auditor
prj_rl_rds_auditor_prod
```

Current intended grants:

```text
pg_read_all_settings
pg_read_all_stats
```

Current PostgreSQL catalog collection uses fixed queries against:

```text
pg_catalog.pg_database
pg_catalog.pg_stat_activity
pg_catalog.pg_roles
pg_catalog.pg_auth_members
```

Do not collect from `pg_authid` because it is password-bearing; use `pg_roles`
for role attributes.

Explicitly not allowed:

```text
pg_monitor
pg_stat_scan_tables
pg_read_all_data
pg_write_all_data
pg_signal_backend
rds_superuser
```

The login role should retain defense-in-depth defaults: `default_transaction_read_only=on`, `statement_timeout=20s`, `lock_timeout=2s`, `idle_in_transaction_session_timeout=60s`, `idle_session_timeout=10min`, `application_name=infra-auditor`, and connection limit 2.

## No Application Table Rows

Collectors must not intentionally retrieve application row data. Use catalog metadata, statistics, activity metadata, configuration, AWS metrics, and operational evidence.

## Query Text Minimization

V1 should not collect unrestricted `pg_stat_activity.query` text. Prefer query identifiers and operational metadata. Any future query text support needs explicit justification, redaction, length limits, PII/secret protection, and runtime-flow documentation.

`pg_stat_statements` query text is also potentially sensitive.

## AWS Read-Only Evidence Boundary

Current AWS collection is read-only and may call:

```text
rds:DescribeDBInstances
ec2:DescribeSecurityGroups
cloudwatch:GetMetricData
rds:DescribePendingMaintenanceActions
rds:DescribeDBRecommendations
rds:DescribeDBParameters
secretsmanager:GetSecretValue
s3:PutObject
```

The collector must not call AWS mutating APIs such as `ModifyDBInstance`,
`ModifyDBParameterGroup`, `AuthorizeSecurityGroupIngress`,
`RevokeSecurityGroupIngress`, or `ApplyPendingMaintenanceAction`.

Artifact writers may use `s3:PutObject` only for approved immutable audit
artifact prefixes such as `raw/snapshots/*`.

## Report Console Boundary

The local FastAPI report console is an internal control surface over audit
artifacts and reports. It may list/read canonical S3 manifests and artifacts for
reporting and may trigger the existing read-only collection workflow, which
only writes new immutable artifact families to S3.

It must not expose generic SQL, arbitrary AWS API calls, automatic remediation,
secret reads beyond the collector workflow, or application table data.

Bind the local UI to `127.0.0.1` by default. Exposing it beyond localhost needs
a separate authentication and network-access design.

The Chat view is currently inert. Future LLM chat must use approved MCP/data
tools over snapshots and reports, not live generic SQL, shell command bridges,
or arbitrary AWS API execution.

The async `/view` route is a read/report rendering boundary over the same S3
snapshots and collector actions. It must not become a generic live execution
endpoint.

## Secret Handling

- Secrets Manager is the V1 source for production DB credentials.
- Do not store real secrets in YAML, `.env`, snapshots, docs, tests, or logs.
- Logging redacts common sensitive key names, but code must still avoid passing secret values into logs.

## Skill Trust Boundary

Agent skills are instruction-bearing and may include commands or broader tool permissions. Treat downloaded skills like software dependencies:

- Prefer official vendor-maintained sources.
- Inspect `SKILL.md`, scripts, shell commands, network access, filesystem access, and allowed tools.
- Record source/version/commit in `docs/research-sources.md`.
- Do not run untrusted installers with elevated privileges.
- Do not install skills that request production credentials.
- Do not let skills weaken this file.
