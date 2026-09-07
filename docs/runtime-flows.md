# Runtime Flows

## V0.1 `collect --instance`

### Entry Point

```bash
uv run infra-auditor collect --instance raptor-catalog
```

### Call Chain

```text
Typer CLI
-> AppSettings from INFRA_AUDITOR_* and optional .env
-> load_resource_config(config/environments.example.yaml)
-> boto3 Session
-> RDS DescribeDBInstances
-> RDSInstance model
-> EC2 DescribeSecurityGroups for attached groups
-> CloudWatch GetMetricData for bounded RDS metric summaries
-> RDS DescribePendingMaintenanceActions, DescribeDBRecommendations, DescribeDBParameters
-> Secrets Manager GetSecretValue
-> PostgresCredentials model
-> PostgresConnectionFactory
-> DatabaseDiscoveryCollector
-> ActivitySummaryCollector
-> RoleSecurityCollector
-> deterministic AWS/RDS, PostgreSQL activity, and PostgreSQL security rules
-> AuditSnapshot model
-> S3SnapshotWriter
-> eight canonical schema-2 service/subservice evidence artifacts
-> run manifest written last as the completion marker
-> s3://infra-audit-rl-<SYS_ENV>/raw/snapshots/schema=2/.../<YYYYMMDDTHHMMSSZ>.json
```

### Inputs

- Process settings: `SYS_ENV`, AWS region/profile, log level/format, registry path,
  bootstrap database, PostgreSQL SSL mode, connect timeout.
- Resource registry: logical alias, RDS DB instance identifier, secret ID, optional per-instance region.
- AWS APIs: RDS DB instance metadata, EC2 security group ingress, CloudWatch RDS
  metrics, RDS operations/configuration APIs, and Secrets Manager secret values.
- PostgreSQL catalog/activity: `pg_catalog.pg_database`,
  `pg_catalog.pg_stat_activity`, `pg_catalog.pg_roles`, and
  `pg_catalog.pg_auth_members`.

### Outputs

- CLI summary with run ID, instance alias, collector status, database count,
  finding count, manifest path, and overall status.
- Structured logs to stdout/stderr.
- Eight S3 JSON artifacts containing the same run identity and only their
  approved RDS, PostgreSQL, or deterministic-finding boundary fields.
- One small manifest indexing the exact artifact family. It is written only
  after all artifacts succeed and is the sole completed-run marker.

### Failure Paths

- Settings or YAML validation failure exits before AWS access.
- AWS discovery failure records an `aws.rds.describe_db_instances` gap and the instance snapshot is `FAILED`.
- EC2 security group, CloudWatch metric, or RDS operations failures keep RDS
  discovery evidence, record collector-specific gaps, and continue toward
  Secrets Manager/PostgreSQL collection.
- Secret resolution failure keeps AWS evidence, records a `secrets.postgres_credentials` gap, skips database inventory, and returns `PARTIAL_SUCCESS`.
- PostgreSQL connection failure keeps AWS evidence, records gaps for each
  PostgreSQL collector, and returns `PARTIAL_SUCCESS`.
- PostgreSQL database inventory or activity-summary failure keeps other
  available evidence, records collector-specific gaps, and returns
  `PARTIAL_SUCCESS`.
- PostgreSQL role security failure keeps earlier evidence, records a
  `postgres.role_security` gap, and returns `PARTIAL_SUCCESS`.
- Artifact or manifest write failure raises `SnapshotValidationError` and the
  CLI exits non-zero. A partial artifact family has no manifest, so readers do
  not treat it as a completed run. S3 writes are append-only and do not attempt
  cleanup or overwrite.

### Diff Context

Added V0.1 config, logging, AWS discovery, AWS security group ingress,
CloudWatch RDS metric summaries, RDS operations evidence, Secrets Manager,
PostgreSQL database inventory, PostgreSQL activity summary, PostgreSQL role
security, deterministic findings, in-memory snapshot assembly, canonical S3
artifacts, and completion manifests.

Bypassed/deferred: Parquet, Athena, SES, CloudWatch log collection,
Performance Insights, LLM analyst, hosted MCP, and remediation.

Untouched: live AWS resources, IAM, RDS configuration, PostgreSQL roles, PostgreSQL objects, application tables.

## V0.1 `discover aws`

### Entry Point

```bash
uv run infra-auditor discover aws --instance udb
```

### Call Chain

```text
Typer CLI
-> settings
-> resource registry
-> boto3 Session
-> RDS DescribeDBInstances
-> RDSInstance model
-> CLI summary
```

### Failure Paths

Invalid config exits before AWS. Missing AWS permission, missing instance, or API failure prints a failed discovery line and exits non-zero.

## V0.1 `serve`

### Entry Point

```bash
uv run infra-auditor serve
```

For local day-to-day use, the central runner performs dependency checks, loads
`.env`, and starts the same server:

```bash
./run.sh
```

### Call Chain

```text
Typer CLI
-> AppSettings from INFRA_AUDITOR_* and optional .env
-> FastAPI app on INFRA_AUDITOR_WEB_HOST:INFRA_AUDITOR_WEB_PORT
-> load_resource_config(config/environments.example.yaml)
-> GET / returns lightweight Bootstrap shell and loader
-> browser fetches GET /view for selected section
-> boto3 Session
-> S3 ListBucket/GetObject for canonical manifests and artifacts
-> manifest-constrained artifact validation and in-memory AuditSnapshot assembly
-> report builder
-> selected RDS/Database (PG)/Reports/Raw content, JSON APIs, and Markdown/JSON exports
```

The UI uses separate HTML, CSS, and JavaScript assets. It exposes controlled
background sync jobs through `POST /sync-jobs`, with status polling at
`GET /api/sync-jobs/{job_id}`. The terminal CLI remains the direct collection
entrypoint; the web UI uses background jobs so slow collection shows per-alias
progress.

The left pane holds project branding, the current `SYS_ENV` value, the derived
snapshot bucket name, a full-width global `Sync all` action, and navigation.
Current live sections are RDS, Database (PG),
Reports, Raw Data, and Chat. AWS, EC2, Elasticsearch, and Bitbucket are planned
standalone domains. Runtime selectors live in the right pane, while instance
`Sync now` sits at the right edge of the service heading row. RDS
owns current RDS instance metadata, RDS operations, RDS-attached security group
ingress, and CloudWatch RDS metric evidence. Database (PG) owns PostgreSQL
database inventory, activity summaries, and role security evidence. Raw Data can
show a selected canonical artifact.

Service navigation chooses the domain; the control row selects server, subservice,
date, timestamp (UTC), then Apply. Server/subservice/date changes fetch
`GET /api/filter-options` to refresh dependent options, with inline loaders,
disabled Apply during loading or empty/error states, cancelled stale requests,
no-store responses, and restoration of the last visible options after transient
errors. Versioned static asset URLs prevent an older filter script from surviving
a console update.
Apply loads the selected report; changing options alone does not reload it.
The API validates configured aliases and approved section/subservice combinations.
RDS/Database/Raw history reads the selected artifact partition directly. Report
views resolve the corresponding run manifest and reassemble the coherent
in-memory snapshot from its exact artifact references. Before any referenced
object is fetched, every key must match the canonical key calculated from the
manifest and the complete approved boundary set.
History retains the reader's existing newest-50-object limit per partition.

`Sync now` collects the selected server through the existing full read-only
workflow; `Sync all` collects all configured servers. Today sync remains available
through MCP but is no longer a visible UI action. Sync completion returns to the
shell with fresh filter context.

The sidebar collapse state and light/dark theme preference are stored in browser
local storage. These are client-only UI preferences.

Snapshot reads are boundary-aware and scope S3 listing to:

```text
raw/snapshots/schema=2/env=<env>/service=<service>/region=<region>/instance=<alias>/subservice=<subservice>/
```

### Outputs

- HTML dashboard at `/`.
- JSON APIs at `/api/runs`, `/api/latest-report`, `/api/fleet-report`, and
  `/api/run`.
- JSON/Markdown exports at `/exports/fleet.*` and `/exports/instance.*`.
- Health check at `/healthz`.

### Failure Paths

Missing S3 read permissions or missing snapshots render an error in the UI.
Collection failures through the UI follow the same partial-success snapshot
semantics as the CLI.

The Chat section is a placeholder until an approved MCP/LLM design exists. It
does not send report data to an external model.

## V0.1 `mcp`

### Entry Point

```bash
uv run infra-auditor mcp
```

### Call Chain

```text
Typer CLI
-> infra_auditor.mcp.server
-> official MCP Python SDK server over stdio
-> AppSettings from INFRA_AUDITOR_* and optional .env
-> load_resource_config(config/environments.example.yaml)
-> boto3 Session
-> S3 ListBucket/GetObject for approved manifest/artifact prefixes
-> SnapshotRunManifest and canonical artifact validation
-> in-memory AuditSnapshot assembly where requested
-> deterministic report builder where requested
-> structured MCP tool result
```

### Tools

- `describe_audit_data_boundary`
- `list_audit_instances`
- `list_audit_runs`
- `get_latest_instance_report`
- `get_fleet_report`
- `get_instance_findings`
- `list_audit_artifacts`
- `get_latest_audit_artifact`
- `sync_latest_audit_data`
- `sync_today_audit_data`

### Inputs

- Process settings and non-secret resource registry.
- Stored manifests and artifacts under fixed `raw/snapshots/schema=2/...`
  service/subservice partitions.

### Outputs

- MCP structured tool responses containing approved configuration summaries,
  completed-run metadata, deterministic report models, finding summaries,
  canonical raw artifacts, and controlled sync results.

### Failure Paths

- Invalid settings or registry values fail startup.
- Unknown instance aliases fail the tool call.
- Missing S3 read permission, missing objects, or schema validation failures
  return tool errors from the read-service boundary.

### Safety Boundary

The MCP server does not expose generic SQL, arbitrary AWS APIs, arbitrary S3 key
reads, Secrets Manager reads, query text retrieval, shell command bridges, or
remediation tools. `sync_latest_audit_data` and `sync_today_audit_data` are
constrained live collection entrypoints over configured aliases only; they call
the existing read-only collector workflow and write immutable S3 audit
artifacts. The today mode checks the latest completed-run manifest for each
alias and skips collection when one is already partitioned under the current
UTC day.
