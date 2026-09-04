# Configuration

## Runtime Settings

Runtime settings use Pydantic Settings with the `INFRA_AUDITOR_` prefix.
`SYS_ENV` is the one unprefixed environment selector. It may be `dev` or `prod`;
when unset it defaults to `dev`.

Supported settings:

- `SYS_ENV`
- `INFRA_AUDITOR_AWS_REGION`
- `INFRA_AUDITOR_AWS_PROFILE`
- `INFRA_AUDITOR_LOG_LEVEL`
- `INFRA_AUDITOR_LOG_FORMAT`
- `INFRA_AUDITOR_RESOURCE_CONFIG_PATH`
- `INFRA_AUDITOR_BOOTSTRAP_DATABASE`
- `INFRA_AUDITOR_POSTGRES_SSL_MODE`
- `INFRA_AUDITOR_POSTGRES_CONNECT_TIMEOUT_SECONDS`
- `INFRA_AUDITOR_CLOUDWATCH_METRIC_LOOKBACK_HOURS`
- `INFRA_AUDITOR_CLOUDWATCH_METRIC_PERIOD_SECONDS`
- `INFRA_AUDITOR_WEB_HOST`
- `INFRA_AUDITOR_WEB_PORT`

Environment variables override values from local `.env`. Production should use
ECS environment configuration, task IAM role, and Secrets Manager rather than
production `.env` files.

## Snapshot Bucket

Raw JSON snapshots are written to the bucket derived from `SYS_ENV`:

```text
infra-audit-rl-<SYS_ENV>
```

Examples:

```text
SYS_ENV=dev  -> infra-audit-rl-dev
SYS_ENV=prod -> infra-audit-rl-prod
```

Snapshot keys use:

```text
raw/snapshots/snapshot_schema=<version>/env=<SYS_ENV>/region=<region>/service=rds-postgres/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

Each collection also writes split raw artifacts for approved RDS, PostgreSQL,
and deterministic-finding boundaries:

```text
raw/snapshots/artifact_schema=<version>/snapshot_schema=<version>/env=<SYS_ENV>/region=<region>/service=<service>/subservice=<subservice>/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

Current RDS subservices include RDS instance metadata, RDS operations, attached
security group ingress, and CloudWatch RDS metric summaries.

## Resource Registry

The non-secret resource registry is YAML:

```yaml
version: 1

aws:
  default_region: ap-south-1

instances:
  raptor-catalog:
    db_instance_identifier: cleancatalograptorsupplies
    secret_id: infra-auditor/postgres/raptor-catalog
```

The registry answers: what resources should be audited?

AWS discovery answers: what do those resources currently look like?

## Prohibited Config Values

Do not put these in `.env`, `.env.example`, or YAML:

- database passwords,
- RDS endpoints,
- AWS account IDs,
- VPC IDs,
- subnet IDs,
- security group IDs,
- allocated storage,
- instance class,
- engine version,
- connection strings.

## Secrets

Secrets Manager values are expected to be JSON:

```json
{
  "username": "prj_rl_rds_auditor_prod",
  "password": "replace-at-creation-time"
}
```

Do not include endpoints, database names, VPC metadata, or application data in the secret.

## PostgreSQL Connection Defaults

The connection factory uses:

- discovered endpoint and port,
- secret username/password,
- bootstrap database, default `postgres`,
- application name, default `infra-auditor`,
- TLS with `sslmode=require` by default,
- bounded connect timeout.

Future production collectors should evaluate `verify-full` with the trusted AWS RDS CA bundle.

## CloudWatch Metric Window

RDS CloudWatch metrics default to a 24-hour lookback and 300-second period:

```text
INFRA_AUDITOR_CLOUDWATCH_METRIC_LOOKBACK_HOURS=24
INFRA_AUDITOR_CLOUDWATCH_METRIC_PERIOD_SECONDS=300
```

The first metric collector stores bounded summaries, not every raw datapoint.

## Local Report UI

The local FastAPI report console defaults to localhost on port `8008`:

```text
INFRA_AUDITOR_WEB_HOST=127.0.0.1
INFRA_AUDITOR_WEB_PORT=8008
```

Run it directly with:

```bash
uv run infra-auditor serve
```

For local development, prefer the central runner:

```bash
./run.sh
```

The runner checks for Python 3.12+, installs `uv` if missing, runs `uv sync`,
loads local `.env`, and starts the server from the configured host/port.

## Local MCP Server

Run the MCP server over stdio with:

```bash
uv run infra-auditor mcp
```

The MCP server uses the same settings and resource registry as the UI. It reads
approved S3 snapshot/report data for configured instances only and may run the
existing read-only collector workflow through `sync_latest_audit_data` or
`sync_today_audit_data`.
