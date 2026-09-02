# Current Project Status

## Current Phase

V0.1 repository bootstrap and minimal read-only collection foundation.

## What Works

- `uv run infra-auditor config validate` validates settings and `config/environments.example.yaml`.
- `uv run infra-auditor discover aws --instance <alias>` can call read-only RDS discovery when AWS credentials/permissions exist.
- `uv run infra-auditor collect --instance <alias>` builds a minimal snapshot path: RDS discovery, Secrets Manager credential resolution, PostgreSQL database inventory, and local JSON persistence.
- Unit tests use fakes and do not touch production AWS/RDS.
- The PostgreSQL auditor roles/users have been created on both target RDS PostgreSQL instances, according to owner handoff.
- Local AWS authentication is ready to use IAM Identity Center or other temporary credentials through boto3's standard provider chain. `INFRA_AUDITOR_AWS_PROFILE` remains optional for local development and must not be required in production.
- Local `.env` exists outside git with `INFRA_AUDITOR_AWS_PROFILE=infra-auditor`.
- The `infra-auditor` local AWS profile is logged in and can call STS, RDS discovery, and Secrets Manager for both configured instances.
- Live V0.1 collection now succeeds for both `udb` and `raptor-catalog`, including PostgreSQL database inventory and local JSON snapshot persistence.
- The PostgreSQL auditor permission boundary has been checked with fixed catalog queries and mostly matches the intended read-only posture.

## What Is Partially Implemented

- Snapshot model contains run metadata, RDS metadata, database inventory, collector statuses, and collection gaps.
- Secrets Manager boundary validates `username` and `password`; live secrets now use the credential-only schema and were verified without printing values.
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
- AWS permission sets, IAM roles, Secrets Manager secrets, S3 buckets, ECS tasks, EventBridge schedules, and CI/CD identities are not created by this repository.

## Known Findings

- Raptor Catalog has effective role paths to `rds_superuser`, including `usr_rl_abhishek_pathak -> raptorsupplies24 -> rds_superuser` and `role_cleanup -> raptorsupplies24 -> rds_superuser`.
- Login-to-login inheritance exists and should be reviewed.
- `PubliclyAccessible=true` exists on both RDS instances, but this must be evaluated with actual ingress rules before severity is assigned.
- The auditor cannot connect to `unified_db_live` on `udb` or `raptor_db` on `raptor-catalog`; decide whether future collectors should require those databases.
- On `raptor-catalog`, `pg_stat_statements` extension views are selectable in `datalyze_db`, `ptm_flow_prod`, and `raptor_catalog`. This is not application table access, but future query/stat collectors must not read query text without a documented minimization design.

## Open Decisions

- S3 encryption mode and object layout remain deferred until after complete local AWS/PostgreSQL collection is validated.
- No unresolved code changes are required before correcting the current secret JSON values.

## Blockers

- No current blocker for the V0.1 local live collection path.
- Future S3 persistence, broader collectors, deterministic rules, reports, and ECS/EventBridge deployment remain unimplemented.

## Next Recommended Task

Start the next session by reviewing the successful local snapshots and the
permission-boundary notes, then discuss the S3 persistence design before any
implementation.

## Last Validation

2026-09-02 repository/architecture review:

- Read project guardrails, architecture, runtime/config/security docs, runbooks, code, tests, `.env.example`, and git status/diff.
- Current git worktree was clean before documentation updates.
- Verified current code uses optional local AWS profile selection and otherwise relies on boto3 provider behavior.
- Added AWS identity/access bootstrap documentation and recorded official AWS research sources.
- Local validation passed: `uv run infra-auditor config validate`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` with 13 tests.
- No live AWS or PostgreSQL commands were run.

2026-09-02 local AWS profile follow-up:

- Created local-only `.env` with non-secret settings and `INFRA_AUDITOR_AWS_PROFILE=infra-auditor`.
- Verified the profile is logged in without recording account details in docs.
- `uv run infra-auditor collect --instance udb` reached RDS discovery successfully, then returned `PARTIAL_SUCCESS` because Secrets Manager credential resolution was denied.
- `uv run infra-auditor collect --instance raptor-catalog` reached RDS discovery successfully, then returned `PARTIAL_SUCCESS` because Secrets Manager credential resolution was denied.
- Local partial snapshots were written under gitignored `data/snapshots/`.

2026-09-02 Secrets Manager follow-up:

- Verified `infra-auditor` can read both configured Secrets Manager entries without printing secret values.
- At that time, both secret payloads included extra RDS-template fields: `engine`, `host`, `port`, `dbname`, and `dbInstanceIdentifier`.
- `uv run infra-auditor collect --instance udb` and `uv run infra-auditor collect --instance raptor-catalog` still return `PARTIAL_SUCCESS` because `PostgresCredentials` forbids those extra fields by design.

2026-09-02 successful live V0.1 collection:

- Rechecked both secret payload key sets; each contains only `username` and `password`.
- `uv run infra-auditor collect --instance udb` succeeded with 6 databases discovered and wrote `data/snapshots/0bbc9ceb-38dd-454c-bbc9-2a29b258d127/udb.json`.
- `uv run infra-auditor collect --instance raptor-catalog` succeeded with 12 databases discovered and wrote `data/snapshots/562af0a7-bc1a-4c90-9ea2-9cdab3e1721d/raptor-catalog.json`.
- No secret values were printed or recorded in project docs.

2026-09-02 PostgreSQL permission-boundary check:

- Used fixed catalog queries only; no application table rows were read.
- Both instances use `prj_rl_rds_auditor_prod`, connection limit `2`, read-only transaction settings, expected timeouts, and `application_name=infra-auditor`.
- Both instances have `pg_read_all_settings` and `pg_read_all_stats`; neither has `pg_monitor`, `pg_stat_scan_tables`, `pg_read_all_data`, `pg_write_all_data`, `pg_signal_backend`, or `rds_superuser`.
- Checked database-level `CREATE`; it was false on connectable databases.
- `udb`: `postgres` and `udb_airflow_metadata_db` were connectable; `unified_db_live` was not connectable.
- `raptor-catalog`: all non-template databases except `raptor_db` were connectable.
- No application table privileges were observed. The only selectable non-system relations were extension-owned `pg_stat_statements` views on selected `raptor-catalog` databases.

2026-08-26 local validation:

- `uv sync` passed.
- `uv run ruff check .` passed.
- `uv run ruff format --check .` passed.
- `uv run mypy src` passed.
- `uv run pytest` passed: 13 tests.
- `uv run infra-auditor config validate` passed: 2 configured instances, default region `ap-south-1`.

No live AWS or PostgreSQL collection was run in this bootstrap session.
