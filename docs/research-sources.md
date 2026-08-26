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
