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

Canonical instance-scoped artifact keys use:

```text
raw/snapshots/schema=3/env=<SYS_ENV>/service=<service>/region=<region>/instance=<alias>/subservice=<subservice>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

Each completed instance collection writes a small manifest last:

```text
runs/schema=3/env=<SYS_ENV>/region=<region>/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

Current RDS subservices include RDS instance metadata, RDS operations, attached
security group ingress, and CloudWatch RDS metric summaries.

The manifest contains metadata and artifact keys, not duplicated evidence.
Schema-1 compatibility snapshots are unsupported. Future non-instance services
omit `instance`, use `region=global` for non-regional evidence, and use
`subservice=overview` when no narrower boundary exists.

## Resource Registry

The active file is [config/environments.yaml](../config/environments.yaml).
Registry version 3 uses `services → regions → instances`, with service-level
subservice defaults, per-instance list replacements, and explicit PostgreSQL
RDS-host references. The complete supported syntax, enums, examples, dependencies
and current adapter constraints are in the adjacent
[config/README.md](../config/README.md).

The human-managed tree is service-shaped. Reviewed code resolves it to today's
bounded paired RDS/PostgreSQL jobs. Every instance carries its actual region;
the first RDS region is used only as the legacy default display value. There is
no region fallback inside the version-3 tree. Legacy registry versions 1/2 are
still readable, but new configuration should use version 3.

RDS instance discovery is mandatory for this adapter. Omit a PostgreSQL instance
or set its `subservices: []` to skip credentials and database connections.
Disabled collectors are intentionally not checked; failure means an enabled
collector attempted work and encountered an error. Neither proves service health.

Unknown services/subservices, wrong-service names, duplicate selections, missing
host references, ambiguous aliases and missing enabled PostgreSQL secret references
fail validation before external access. YAML selects implemented capabilities;
it cannot add generic SQL, imports, API execution or unimplemented policy rules.

The console displays effective coverage; `config validate` prints it; MCP
`list_audit_instances` includes it without secret IDs. Restart UI/MCP after config
changes and use latest/Sync all; today sync checks dates, not configuration changes.
Approved historical evidence remains readable when its collector is later disabled.

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
  "username": "prj_rl_infra_auditor",
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
approved S3 artifact/report data for configured instances only and may run the
existing read-only collector workflow through `sync_latest_audit_data` or
`sync_today_audit_data`.

## Storage cutover

See [storage layout](storage-layout.md) for raw/report/manifest paths and
[practical next steps](runbooks/postgres-next-steps.md) for IAM prefix updates.
