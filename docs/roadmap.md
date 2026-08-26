# Roadmap

## Phase 0.1 - Bootstrap

- Repo memory and safety docs.
- Settings and resource registry.
- RDS discovery.
- Secrets Manager credential boundary.
- PostgreSQL connection foundation.
- Database inventory collector.
- Local JSON snapshot.

## Phase 0.2 - Live Read-Only Validation

- Create read-only AWS audit permission set.
- Create per-instance Secrets Manager secrets.
- Run collector against `raptor-catalog` and `udb`.
- Validate generated snapshots.
- Verify auditor privileges do not include application table access.

## Phase 0.3 - First Deterministic Rules

- Implement security role graph collectors.
- Implement SEC001-SEC004.
- Add evidence-referenced findings.

## Phase 0.4 - Operations Evidence

- Add CloudWatch metrics and storage evidence.
- Add connection/session/lock collectors with query text minimization.
- Add partial failure test coverage for per-database collectors.

## Later

- S3/Parquet/Glue/Athena historical storage.
- HTML/JSON reports and SES daily email.
- Docker/ECR/ECS/EventBridge deployment.
- Pydantic AI LLM analyst after deterministic findings exist.
- MCP query interface to audit data after safe authorization design.

## Deferred Decisions

- Terraform adoption: DEFERRED until deployment requirements are finalized.
- IAM database authentication: DEFERRED until V1 password/Secrets Manager flow is validated.
- Enhanced Monitoring and Database Insights Advanced: DEFERRED because they are cost/architecture decisions.
- S3/Parquet/Athena: DEFERRED until local snapshots are validated.
