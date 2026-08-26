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
-> Secrets Manager GetSecretValue
-> PostgresCredentials model
-> PostgresConnectionFactory
-> DatabaseDiscoveryCollector
-> AuditSnapshot model
-> LocalSnapshotWriter
-> data/snapshots/<run_id>/<alias>.json
```

### Inputs

- Process settings: environment, AWS region/profile, log level/format, registry path, snapshot output path, bootstrap database, PostgreSQL SSL mode, connect timeout.
- Resource registry: logical alias, RDS DB instance identifier, secret ID, optional per-instance region.
- AWS APIs: RDS DB instance metadata and Secrets Manager secret values.
- PostgreSQL catalog: `pg_catalog.pg_database`.

### Outputs

- CLI summary with run ID, instance alias, collector status, database count, snapshot path, and overall status.
- Structured logs to stdout/stderr.
- Local JSON snapshot containing run metadata, RDS metadata, database inventory, collector statuses, and gaps.

### Failure Paths

- Settings or YAML validation failure exits before AWS access.
- AWS discovery failure records an `aws.rds.describe_db_instances` gap and the instance snapshot is `FAILED`.
- Secret resolution failure keeps AWS evidence, records a `secrets.postgres_credentials` gap, skips database inventory, and returns `PARTIAL_SUCCESS`.
- PostgreSQL connection or database inventory failure keeps AWS evidence, records a `postgres.database_inventory` gap, and returns `PARTIAL_SUCCESS`.
- Snapshot write failure raises `SnapshotValidationError`.

### Diff Context

Added V0.1 config, logging, AWS discovery, Secrets Manager, PostgreSQL database inventory, snapshot, and local storage boundaries.

Bypassed/deferred: deterministic rules, findings, S3, Parquet, Athena, SES, CloudWatch metrics/log collection, RDS recommendations, LLM, MCP, and remediation.

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
