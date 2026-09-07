# Roadmap

## Phase 0.1 - Bootstrap

- Repo memory and safety docs.
- Settings and resource registry.
- RDS discovery.
- Secrets Manager credential boundary.
- PostgreSQL connection foundation.
- Database inventory collector.
- Canonical schema-2 S3 JSON artifacts and completion manifest.
- Initial role security, activity summary, AWS operations, and network/metric
  evidence collectors.
- Initial snapshot/fleet report model and local FastAPI report console.
- Service-section UI shell for RDS, Database (PG), Reports, Raw Data, planned
  services, and future Chat.
- Raw S3 artifacts for RDS, PostgreSQL, and
  deterministic-finding boundaries.
- Base MCP interface over approved snapshot/report data with controlled
  latest-data and today-data sync.

## Phase 0.2 - Live Read-Only Validation

- Create read-only AWS audit permission set.
- Create per-instance Secrets Manager secrets.
- Run collector against `raptor-catalog` and `udb`.
- Validate generated S3 artifact families and manifests.
- Verify auditor privileges do not include application table access.

## Phase 0.3 - First Deterministic Rules

- Implement security role graph collectors.
- Implement SEC001-SEC004.
- Add evidence-referenced findings.
- Embed first findings in S3 snapshots.

## Phase 0.4 - Operations Evidence

- Add CloudWatch metrics and RDS storage evidence. Initial summary collector implemented.
- Add RDS recommendations and pending maintenance evidence. Initial collector implemented.
- Add parameter group evidence and baseline comparison. Evidence collector implemented; baseline comparison remains.
- Add connection/session/lock collectors with query text minimization. Initial activity summary implemented; lock detail remains.
- Add partial failure test coverage for per-database collectors.

## Later

- Broader AWS account posture collectors: IAM Identity Center users, permission
  sets, roles, policies, access key metadata, and last-used evidence, added one
  read-only permission group at a time.
- Broader EC2 collectors: configured EC2 inventory, CPU/memory/disk/network
  metrics, health/status checks, security groups, volumes, and backup posture.
- Deeper Database (PG) collectors: table/index size, stale indexes, duplicate
  indexes, bloat indicators, permission drift, redundant users, lock detail,
  connection pressure, and safe pg_stat_statements-derived summaries without
  unrestricted query text.
- Parquet/Glue/Athena historical storage.
- Historical indexes and richer artifact-native UI/report reads.
- Hosted/authenticated MCP exposure after an approved access design.
- Richer HTML/JSON/Markdown reports and SES daily email.
- Docker/ECR/ECS/EventBridge deployment.
- Pydantic AI LLM analyst after deterministic findings exist.

## Deferred Decisions

- Terraform adoption: DEFERRED until deployment requirements are finalized.
- IAM database authentication: DEFERRED until V1 password/Secrets Manager flow is validated.
- Enhanced Monitoring and Database Insights Advanced: DEFERRED because they are cost/architecture decisions.
- Parquet/Athena: DEFERRED until raw S3 snapshots and deterministic findings are validated.
