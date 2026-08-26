# Configuration

## Runtime Settings

Runtime settings use Pydantic Settings with the `INFRA_AUDITOR_` prefix.

Supported settings:

- `INFRA_AUDITOR_ENVIRONMENT`
- `INFRA_AUDITOR_AWS_REGION`
- `INFRA_AUDITOR_AWS_PROFILE`
- `INFRA_AUDITOR_LOG_LEVEL`
- `INFRA_AUDITOR_LOG_FORMAT`
- `INFRA_AUDITOR_RESOURCE_CONFIG_PATH`
- `INFRA_AUDITOR_SNAPSHOT_OUTPUT_DIR`
- `INFRA_AUDITOR_BOOTSTRAP_DATABASE`
- `INFRA_AUDITOR_POSTGRES_SSL_MODE`
- `INFRA_AUDITOR_POSTGRES_CONNECT_TIMEOUT_SECONDS`

Environment variables override values from local `.env`. Production should use ECS environment configuration, task IAM role, and Secrets Manager rather than production `.env` files.

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
