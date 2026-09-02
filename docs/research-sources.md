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
