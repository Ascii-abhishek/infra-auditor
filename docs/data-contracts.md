# Data Contracts

## Versioning

Application version and snapshot schema version are separate:

- `application_version`: semantic project version, currently `0.1.0`.
- `snapshot_schema_version`: evidence family version, currently `2`.

Compatibility changes to persisted models must update this document and usually `decisions.md`.
The S3 object key includes one `schema=2` partition so incompatible persisted
contracts cannot be mixed. Schema 1 is intentionally unsupported before alpha.

## Run Metadata

`RunMetadata` contains:

- `run_id`
- `application_version`
- `snapshot_schema_version`
- `environment`, currently the validated `SYS_ENV` value: `dev` or `prod`
- `region`
- timezone-aware UTC `started_at` and `completed_at`
- overall collection `status`

## Instance Snapshot

`InstanceSnapshot` contains:

- logical alias,
- RDS DB instance identifier,
- region,
- status,
- optional normalized RDS instance metadata,
- attached security group ingress evidence,
- bounded CloudWatch RDS metric summaries,
- RDS maintenance, recommendations, and parameter group evidence,
- PostgreSQL database inventory,
- PostgreSQL activity summary evidence,
- PostgreSQL role security evidence,
- collector result list,
- collection gaps,
- deterministic findings.

## RDS Instance Evidence

`RDSInstance` includes instance identity, engine/version/class/status, storage facts, Multi-AZ/public/IAM-auth state, Database/Performance Insights fields, Enhanced Monitoring interval, log exports, parameter groups, backup/deletion/encryption posture, endpoint/port, VPC/subnet/security-group metadata, windows, and certificate details.

It must not contain secret values.

## AWS Security Group Evidence

`RDSSecurityGroupEvidence` contains the database port, attached security
groups, normalized ingress rules, peers, and booleans indicating unrestricted
IPv4/IPv6 database-port ingress. It is collected through EC2 read-only APIs.

## CloudWatch RDS Metric Evidence

`RDSCloudWatchMetricsEvidence` contains the bounded metric lookback, period,
start/end timestamps, and per-metric summaries: datapoint count, minimum,
maximum, average, latest value, latest timestamp, and status code.

The first metric set includes CPU utilization, database connections, freeable
memory, free storage, read/write latency, read/write IOPS, disk queue depth, and
burst balance.

## RDS Operations Evidence

`RDSOperationsEvidence` contains pending maintenance actions, open/returned RDS
recommendations for the instance, and current DB parameter group parameter
values. This is operational/configuration evidence only; collectors do not apply
recommendations or change parameters.

## Database Inventory Evidence

`DatabaseInfo` contains:

- name,
- connection allowance,
- template status,
- `system` or `application` classification,
- connection eligibility.

Known database names may appear in fixtures, but live inventory must be discovered.

## PostgreSQL Activity Evidence

`PostgresActivityEvidence` contains aggregated `pg_stat_activity` metadata:
total connections, idle-in-transaction count, missing `application_name` count,
and grouped counts/durations by database, role, application name, client
address, state, and wait event type.

It intentionally does not contain `pg_stat_activity.query` text.

## PostgreSQL Role Security Evidence

`PostgresRoleSecurityEvidence` contains:

- role attributes from `pg_catalog.pg_roles`, excluding password/config columns,
- direct role memberships from `pg_catalog.pg_auth_members` joined to role names,
- grantor and admin option metadata for each membership edge.

This evidence is cluster-wide and collected through the bootstrap database.

## Collection Gaps

`CollectionGap` records collector, resource, status, error type, and sanitized message. Gaps are audit evidence.

## Findings

`Finding` records include rule ID, fingerprint, category, severity, resource,
title, summary, observed values, evidence references, and recommendation. Future
rules may add expected/policy values and confidence where meaningful.

## Canonical Raw Evidence Artifacts

`AuditSnapshot` is the in-memory collector and report assembly type; it is not
persisted. Each collection writes canonical service/subservice artifacts under:

```text
raw/snapshots/schema=2/env=<SYS_ENV>/service=<service>/region=<region>/instance=<alias>/subservice=<subservice>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

`SnapshotSplitArtifact` contains:

- artifact metadata with schema version, run ID, service/subservice, collector
  boundary, run/instance/boundary statuses, instance alias, DB instance
  identifier, timestamps, and collector names,
- one `SnapshotSplitInstance` containing only the fields owned by that boundary.

Current artifact boundaries:

- RDS:
  `rds/instance` includes RDS DB instance discovery evidence,
  `rds/operations` includes RDS maintenance, recommendations, and parameter
  groups, `rds/ec2-security-groups` includes attached security group ingress
  evidence for the selected RDS instance, and `rds/cloudwatch-rds-metrics`
  includes CloudWatch RDS metric summaries.
- PostgreSQL:
  `postgres/database-inventory`, `postgres/activity-summary`, and
  `postgres/role-security` separate database inventory, activity summary, and role
  security evidence.
- Audit heuristics:
  `audit-heuristics/deterministic-findings` includes deterministic findings.

Canonical artifacts must not introduce secret values, unrestricted query text,
application table rows, generic SQL, arbitrary AWS calls, or remediation data.

## Run Manifest

After every artifact write succeeds, the writer commits a small
`SnapshotRunManifest` under `service=audit/subservice=run-manifest`. It contains
the run identity, timestamps, overall status, and the exact approved artifact
keys/statuses. Readers treat a manifest as the completion marker and reconstruct
reports only from its referenced family. A failed partial write has no manifest
and cannot be mistaken for a complete report run.

## Reports

Report models are derived views over manifest-referenced raw artifacts.

`SnapshotReport` summarizes one raw snapshot: severity counts, rule counts,
collector statuses, top findings, network exposure, RDS operations, CloudWatch
metric summaries, PostgreSQL activity, and role/security inventory.

`FleetReport` summarizes the latest loaded snapshots for one service and
environment. It contains service, environment, region, generated timestamp,
combined severity counts, total findings, instance count, and the underlying
`SnapshotReport` entries.

Reports do not replace raw artifacts. They are the stable reader-facing shape
for the local UI and MCP tools.
