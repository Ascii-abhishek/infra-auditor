# Roadmap

## Phase 0.1 - Bootstrap

- Repo memory and safety docs.
- Settings and resource registry.
- RDS discovery.
- Secrets Manager credential boundary.
- PostgreSQL connection foundation.
- Database inventory collector.
- Canonical schema-3 S3 JSON artifacts and completion manifest.
- Initial role security, activity summary, AWS operations, and network/metric
  evidence collectors.
- Initial snapshot/fleet report model and local FastAPI report console.
- Service-section UI shell for RDS, Database (PG), Reports, Raw Data, future Chat.
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

## Phase 0.5 - Deep PostgreSQL Audit (next development milestone)

Complete the schema-3 coverage/storage checkpoint and live validation first.
The owner reports the prior commit and schema-1 bucket cleanup complete.

1. Agree database scope; add sequential per-database orchestration with independent
   gaps, CONNECT checks and bounded connections.
2. Collect catalog inventory without application rows or executable source text.
3. Design validated ownership/ACL/default-privilege/RLS policy and effective
   permission analysis, distinguishing confirmed violations from review candidates.
4. Add table/vacuum/freeze and index-health evidence with observation quality.
5. Add routine/trigger security and dependency analysis.
6. Add locks/blocking and bounded query-ID performance evidence.
7. Add history/lifecycle and manual repair plans with prerequisites, validation,
   rollback and confidence. No automatic remediation.

See [PostgreSQL module plan](services/postgres.md). Cross-check each production
milestone with the owner; do not treat this list as authorization to change roles,
install extensions, or broaden data access automatically.

## Later

- LLM explanation and prioritization over approved MCP evidence after deep
  PostgreSQL collection, policy and findings are validated.
- Historical storage (Parquet/Glue/Athena) when observation requirements justify it.
- Hosted/authenticated MCP, SES summaries, Docker/ECS/EventBridge deployment.
- Additional services such as Elasticsearch and AWS account/EC2 posture only
  after the PostgreSQL milestone; each needs a reviewed adapter and permissions.

## Deferred Decisions

- Terraform adoption: DEFERRED until deployment requirements are finalized.
- IAM database authentication: DEFERRED until V1 password/Secrets Manager flow is validated.
- Enhanced Monitoring and Database Insights Advanced: DEFERRED because they are cost/architecture decisions.
- Parquet/Athena: DEFERRED until raw S3 snapshots and deterministic findings are validated.
