# Current Project Status

## Current Phase

V0.1 repository bootstrap and minimal read-only collection foundation.

## What Works

- `uv run infra-auditor config validate` validates settings and `config/environments.example.yaml`.
- `uv run infra-auditor discover aws --instance <alias>` can call read-only RDS discovery when AWS credentials/permissions exist.
- `uv run infra-auditor collect --instance <alias>` builds a minimal snapshot path: RDS discovery, Secrets Manager credential resolution, PostgreSQL database inventory, and local JSON persistence.
- Unit tests use fakes and do not touch production AWS/RDS.

## What Is Partially Implemented

- Snapshot model contains run metadata, RDS metadata, database inventory, collector statuses, and collection gaps.
- Secrets Manager boundary validates `username` and `password`, but live secrets have not been created/verified in this repo session.
- PostgreSQL connection factory uses TLS and context managers, but only database inventory is collected.

## What Is Not Implemented

- Deterministic rule engine.
- Findings lifecycle/history.
- CloudWatch metrics/logs collectors.
- RDS recommendations collector.
- Performance Insights/Database Insights collectors.
- S3/Parquet/Glue/Athena storage.
- SES reports.
- Docker/ECS/EventBridge deployment.
- Terraform.
- Pydantic AI, LLM analyst, MCP server, or OpenAI/Anthropic SDKs.
- Automatic remediation.

## Known Findings

- Raptor Catalog has effective role paths to `rds_superuser`, including `usr_rl_abhishek_pathak -> raptorsupplies24 -> rds_superuser` and `role_cleanup -> raptorsupplies24 -> rds_superuser`.
- Login-to-login inheritance exists and should be reviewed.
- `PubliclyAccessible=true` exists on both RDS instances, but this must be evaluated with actual ingress rules before severity is assigned.

## Open Decisions

- None requiring owner input from the bootstrap prompt. All implemented architectural choices follow locked V1 boundaries or are documented in `decisions.md`.

## Blockers

- Live collection needs the owner's read-only AWS permission set.
- Live collection needs the two Secrets Manager secrets.
- Live PostgreSQL validation needs network access from the runner to the RDS instances.

## Next Recommended Task

Configure the owner's AWS audit/read permission set, create the two Secrets Manager secrets, then run the V0.1 collector against real `raptor-catalog` and `udb` in read-only mode and inspect generated snapshots.

## Last Validation

2026-08-26 local validation:

- `uv sync` passed.
- `uv run ruff check .` passed.
- `uv run ruff format --check .` passed.
- `uv run mypy src` passed.
- `uv run pytest` passed: 13 tests.
- `uv run infra-auditor config validate` passed: 2 configured instances, default region `ap-south-1`.

No live AWS or PostgreSQL collection was run in this bootstrap session.
