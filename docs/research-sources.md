# Research Sources

Record current official documentation used for architectural or implementation decisions.

## 2026-08-26 Bootstrap Sources

### uv

- URL: https://docs.astral.sh/uv/concepts/projects/
- Date consulted: 2026-08-26
- Conclusion: uv projects manage multi-file Python code, dependencies, commands, lockfiles, and builds. The repo uses uv with a `pyproject.toml`, `uv.lock`, and `uv run` commands.

### Pydantic v2

- URL: https://docs.pydantic.dev/latest/concepts/models/
- Date consulted: 2026-08-26
- Conclusion: Pydantic models provide validation and serialization via methods such as `model_validate`, `model_dump`, and `model_dump_json`; snapshots and evidence use Pydantic v2 contracts.

### pydantic-settings

- URL: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Date consulted: 2026-08-26
- Conclusion: `BaseSettings` reads missing fields from environment variables and supports `SettingsConfigDict(env_prefix=...)`; runtime settings use `INFRA_AUDITOR_`.

### psycopg 3

- URL: https://www.psycopg.org/psycopg3/docs/basic/usage.html
- Date consulted: 2026-08-26
- Conclusion: psycopg 3 connections support context-manager usage and connection-level `execute`; the connection factory uses context managers and fixed collector SQL.

### boto3 session/client

- URL: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html
- Date consulted: 2026-08-26
- Version: 1.43.80 documentation
- Conclusion: `boto3.session.Session` accepts `region_name` and `profile_name`; service clients are region-bound.

### boto3 RDS `describe_db_instances`

- URL: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rds/client/describe_db_instances.html
- Date consulted: 2026-08-26
- Version: 1.43.80 documentation
- Conclusion: `DescribeDBInstances` supports `DBInstanceIdentifier` for a specific instance and returns rich instance metadata used by the V0.1 RDS model.

### boto3 Secrets Manager `get_secret_value`

- URL: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager/client/get_secret_value.html
- Date consulted: 2026-08-26
- Version: 1.43.80 documentation
- Conclusion: `GetSecretValue` requires `secretsmanager:GetSecretValue`; `SecretString` is sensitive and must not be logged.

### structlog

- URL: https://www.structlog.org/en/stable/getting-started.html
- Date consulted: 2026-08-26
- Version: 26.1.0 documentation
- Conclusion: structlog supports structured event dictionaries, context, log levels, console rendering, and JSON rendering through processors.

### Typer

- URL: https://typer.tiangolo.com/tutorial/commands/
- Date consulted: 2026-08-26
- Conclusion: Typer supports multi-command CLI applications and `no_args_is_help=True`; the project exposes `config`, `discover`, and `collect` commands.

### PyYAML

- URL: https://pyyaml.org/wiki/PyYAMLDocumentation
- Date consulted: 2026-08-26
- Conclusion: safe YAML APIs exist for standard YAML tags; the registry is loaded with `yaml.safe_load` and validated with Pydantic.

### Pydantic AI coding-agent skills

- URL: https://pydantic.dev/docs/ai/overview/coding-agent-skills/
- Date consulted: 2026-08-26
- Conclusion: Pydantic documents official Pydantic AI skills through `pydantic/skills`, Claude plugin installation, cross-agent `npx skills add pydantic/skills`, and library-skills installation. Pydantic AI remains deferred in this repo.

### Anthropic Claude Code skills

- URL: https://docs.anthropic.com/en/docs/claude-code/skills
- Date consulted: 2026-08-26
- Conclusion: Project skills can grant tool access when invoked; skills checked into a repository should be reviewed before use. This supports treating skills as part of the trust boundary.

## 2026-09-02 AWS Identity Bootstrap Sources

### AWS SDK IAM Identity Center credential provider

- URL: https://docs.aws.amazon.com/sdkref/latest/guide/feature-sso-credentials.html
- Date consulted: 2026-09-02
- Conclusion: SDKs can use IAM Identity Center profiles from the shared AWS config file to obtain short-term role credentials; the SSO region can differ from the workload region.

### AWS CLI IAM Identity Center configuration

- URL: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html
- Date consulted: 2026-09-02
- Conclusion: AWS CLI v2 supports `aws configure sso`, `aws sso login --profile ...`, and named SSO profiles for command execution.

### boto3 credentials

- URL: https://docs.aws.amazon.com/boto3/latest/guide/credentials.html
- Date consulted: 2026-09-02
- Conclusion: boto3 supports IAM Identity Center credentials and can select an SSO profile through `AWS_PROFILE` or `boto3.Session(profile_name=...)`.

### IAM Identity Center `list-instances`

- URL: https://docs.aws.amazon.com/cli/latest/reference/sso-admin/list-instances.html
- Date consulted: 2026-09-02
- Conclusion: `aws sso-admin list-instances` lists IAM Identity Center instances visible to the caller, including status and primary region, making it a read-only status check.

### IAM least privilege

- URL: https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html
- Date consulted: 2026-09-02
- Conclusion: IAM policies should grant only permissions required for the task and start from a minimum set.

### Amazon RDS service authorization reference

- URL: https://docs.aws.amazon.com/service-authorization/latest/reference/list_rds.html
- Date consulted: 2026-09-02
- Conclusion: `rds:DescribeDBInstances` is a list-level action for returning provisioned RDS instance information and supports RDS DB resources.

### AWS Secrets Manager `create-secret`

- URL: https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/create-secret.html
- Date consulted: 2026-09-02
- Conclusion: Secrets Manager accepts JSON-like secret text in `SecretString`; AWS marks that field sensitive and does not include it in CloudTrail log entries.

### AWS Secrets Manager `get-secret-value`

- URL: https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/get-secret-value.html
- Date consulted: 2026-09-02
- Conclusion: `GetSecretValue` requires `secretsmanager:GetSecretValue`; customer-managed KMS keys also require `kms:Decrypt`.

### AWS Secrets Manager encryption key guidance

- URL: https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_update-encryption-key.html
- Date consulted: 2026-09-02
- Conclusion: Secrets Manager supports the AWS managed `aws/secretsmanager` key or customer-managed keys; AWS recommends the managed key for most cases.

### Amazon ECS task IAM role

- URL: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
- Date consulted: 2026-09-02
- Conclusion: ECS task roles vend permissions to application code in the task and are distinct from permissions needed by ECS/Fargate agents.

### Amazon ECS task execution role

- URL: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html
- Date consulted: 2026-09-02
- Conclusion: ECS task execution roles let ECS/Fargate agents pull images, send logs, and perform execution operations; these credentials are not directly available to containers.

### Amazon ECS EventBridge scheduled task role

- URL: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/CWE_IAM_role.html
- Date consulted: 2026-09-02
- Conclusion: Scheduled ECS tasks need an EventBridge role with `ecs:RunTask`, and `iam:PassRole` for the task or execution roles when those roles are used.

### GitHub OIDC role trust

- URL: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html
- Date consulted: 2026-09-02
- Conclusion: OIDC trust policies for GitHub Actions must restrict token claims such as repository or subject so repositories outside the owner's control cannot assume the role.

## 2026-09-03 S3 Snapshot Persistence Sources

### Amazon S3 bucket naming rules

- URL: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
- Date consulted: 2026-09-03
- Conclusion: General purpose bucket names must be DNS-compatible and globally
  unique in the AWS partition; predictable names may require an owner-specific
  suffix.

### Amazon S3 default server-side encryption

- URL: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html
- Date consulted: 2026-09-03
- Conclusion: New S3 objects are encrypted at rest by default with SSE-S3, and
  clients may explicitly request SSE-S3 on `PutObject` with `AES256`.

### Amazon S3 SSE-KMS permissions

- URL: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html
- Date consulted: 2026-09-03
- Conclusion: S3 `PutObject` with SSE-KMS needs `kms:GenerateDataKey`; raw
  snapshot writes currently use SSE-S3 to keep the writer permission simple.

### Amazon S3 conditional writes

- URL: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html
- Date consulted: 2026-09-03
- Conclusion: `If-None-Match: *` on `PutObject` prevents overwriting an existing
  object at the same key and only requires `s3:PutObject`.

### Amazon S3 Object Ownership

- URL: https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html
- Date consulted: 2026-09-03
- Conclusion: Bucket owner enforced mode disables ACLs and uses policies for
  object access, matching the project preference for simple IAM boundaries.

## 2026-09-03 PostgreSQL Role Security Sources

### PostgreSQL 15 `pg_roles`

- URL: https://www.postgresql.org/docs/15/view-pg-roles.html
- Date consulted: 2026-09-03
- Conclusion: `pg_roles` is a publicly readable view of role attributes that
  blanks the password field, so it is the safe source for role security
  evidence instead of `pg_authid`.

### PostgreSQL 15 `pg_auth_members`

- URL: https://www.postgresql.org/docs/15/catalog-pg-auth-members.html
- Date consulted: 2026-09-03
- Conclusion: `pg_auth_members` records cluster-wide role membership edges,
  including member role, parent role, grantor, and admin option.

### PostgreSQL 15 role membership

- URL: https://www.postgresql.org/docs/15/role-membership.html
- Date consulted: 2026-09-03
- Conclusion: PostgreSQL supports direct and indirect role membership; login
  roles can `SET ROLE` to directly or indirectly granted roles, and group roles
  are typically created without `LOGIN`.

### PostgreSQL 15 `pg_stat_activity`

- URL: https://www.postgresql.org/docs/15/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW
- Date consulted: 2026-09-03
- Conclusion: `pg_stat_activity` exposes backend/session metadata used for
  bounded activity summaries. The project excludes `query` text from snapshots.

## 2026-09-03 AWS RDS Operational Evidence Sources

### CloudWatch `GetMetricData`

- URL: https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_GetMetricData.html
- Date consulted: 2026-09-03
- Conclusion: `GetMetricData` retrieves metric queries over a bounded
  `StartTime`/`EndTime`, supports pagination with `NextToken`, and returns
  metric result timestamps and values.

### Amazon RDS CloudWatch metrics

- URL: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html
- Date consulted: 2026-09-03
- Conclusion: RDS publishes operational metrics such as CPU utilization,
  database connections, freeable memory, free storage, latency, IOPS, disk queue
  depth, and burst balance to CloudWatch.

### EC2 `DescribeSecurityGroups`

- URL: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSecurityGroups.html
- Date consulted: 2026-09-03
- Conclusion: `DescribeSecurityGroups` returns security group inbound
  permissions, including IPv4, IPv6, security-group, and prefix-list peers.

### RDS `DescribePendingMaintenanceActions`

- URL: https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_DescribePendingMaintenanceActions.html
- Date consulted: 2026-09-03
- Conclusion: This API returns pending maintenance actions and details for an
  RDS resource.

### RDS `DescribeDBRecommendations`

- URL: https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_DescribeDBRecommendations.html
- Date consulted: 2026-09-03
- Conclusion: This API returns RDS recommendations that can be filtered by
  resource ARN in the collector.

### RDS `DescribeDBParameters`

- URL: https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_DescribeDBParameters.html
- Date consulted: 2026-09-03
- Conclusion: This API returns DB parameter group parameter values and metadata.

## 2026-09-04 AWS Permission Expansion Sources

### IAM credential reports

- URL: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_getting-report.html
- Date consulted: 2026-09-04
- Conclusion: IAM credential reports summarize account users and credential
  posture, including passwords, access keys, and MFA status, without collecting
  credential secret values.

### IAM `GetAccessKeyLastUsed`

- URL: https://docs.aws.amazon.com/IAM/latest/UserGuide/iam_example_iam_GetAccessKeyLastUsed_section.html
- Date consulted: 2026-09-04
- Conclusion: `GetAccessKeyLastUsed` can retrieve last-used metadata for an
  access key ID; collectors must store metadata only, never secret access keys.

### IAM service last accessed reports

- URL: https://docs.aws.amazon.com/IAM/latest/APIReference/API_GenerateServiceLastAccessedDetails.html
- Date consulted: 2026-09-04
- Conclusion: IAM can generate service-last-accessed details for identities and
  policies, with activity generally delayed and not a live authorization trace.

### IAM Identity Center CLI namespaces

- URL: https://docs.aws.amazon.com/cli/latest/reference/sso-admin/
- Date consulted: 2026-09-04
- Conclusion: IAM Identity Center APIs use the `sso` and `identitystore`
  namespaces for permission-set and identity-store reads.

### Identity Store `ListUsers`

- URL: https://docs.aws.amazon.com/cli/latest/reference/identitystore/list-users.html
- Date consulted: 2026-09-04
- Conclusion: `identitystore list-users` returns paginated user objects for an
  identity store; future collectors must minimize personally identifying fields.

### IAM Identity Center `ListPermissionSets`

- URL: https://docs.aws.amazon.com/cli/latest/reference/sso-admin/list-permission-sets.html
- Date consulted: 2026-09-04
- Conclusion: `sso-admin list-permission-sets` lists permission sets for an IAM
  Identity Center instance and is a candidate for a future read-only collector.

## 2026-09-03 Local Report UI Sources

### FastAPI first steps

- URL: https://fastapi.tiangolo.com/tutorial/first-steps/
- Date consulted: 2026-09-03
- Conclusion: FastAPI apps are created with `FastAPI()` and expose path
  operations with decorators such as `@app.get`.

### Uvicorn settings

- URL: https://uvicorn.dev/settings/
- Date consulted: 2026-09-03
- Conclusion: Uvicorn can run ASGI apps programmatically with host and port
  keyword arguments.

### Bootstrap 5.3 introduction

- URL: https://getbootstrap.com/docs/5.3/getting-started/introduction/
- Date consulted: 2026-09-03
- Conclusion: Bootstrap can be used through CDN CSS for responsive layouts
  without a frontend build step.

## 2026-09-04 UI Asset Sources

### Bootstrap current version

- URL: https://getbootstrap.com/docs/versions/
- Date consulted: 2026-09-04
- Conclusion: Bootstrap 5 is the current major release and the latest 5.3 update
  is `5.3.8`, so the local report console pins the CDN CSS to `5.3.8`.

### Bootstrap Icons current version

- URL: https://icons.getbootstrap.com/
- Date consulted: 2026-09-04
- Conclusion: Bootstrap Icons currently reports version `1.13.1`, so the local
  report console pins the CDN icon font to `1.13.1`.

## 2026-09-04 MCP Read Layer Sources

### Model Context Protocol SDK index

- URL: https://modelcontextprotocol.io/docs/2026-07-28/sdk
- Date consulted: 2026-09-04
- Conclusion: Python is a Tier 1 official MCP SDK and all listed SDKs support
  servers, clients, local/remote transports, and protocol compliance.

### MCP Python SDK installation

- URL: https://py.sdk.modelcontextprotocol.io/get-started/installation/
- Date consulted: 2026-09-04
- Version: v2 stable release line, `mcp==2.1.1` resolved locally.
- Conclusion: The official Python SDK is installed from PyPI as `mcp`, requires
  Python 3.10+, and v2 is the current stable line with breaking changes from
  v1.

### MCP Python SDK tools

- URL: https://py.sdk.modelcontextprotocol.io/servers/tools/
- Date consulted: 2026-09-04
- Conclusion: `@mcp.tool()` exposes typed Python functions as MCP tools,
  derives input schemas from type hints/Pydantic `Field`, supports read-only
  annotations, and treats annotations as client hints rather than security.

### MCP Python SDK structured output

- URL: https://py.sdk.modelcontextprotocol.io/servers/structured-output/
- Date consulted: 2026-09-04
- Conclusion: Return annotations define structured output schemas and returned
  values are validated before leaving the server; Pydantic models and lists are
  appropriate for the audit report contracts.

### MCP Python SDK running servers

- URL: https://py.sdk.modelcontextprotocol.io/run/
- Date consulted: 2026-09-04
- Conclusion: `mcp.run()` defaults to stdio for local servers; stdout is the
  transport channel, so the project MCP command must avoid user-facing stdout
  output before the server starts.
