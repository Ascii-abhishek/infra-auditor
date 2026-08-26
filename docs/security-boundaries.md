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
