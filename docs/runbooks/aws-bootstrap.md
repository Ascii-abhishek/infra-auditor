# AWS Bootstrap Runbook

This runbook is now an index for AWS bootstrap tasks. The V0.1 code does not
create or modify AWS resources.

Start with [AWS Identity And Access Bootstrap](aws-identity-access.md) before
creating secrets or running live collection.

Expected order:

1. Confirm IAM Identity Center status.
2. Create and assign the `InfraAuditorDeveloper` permission set.
3. Configure the local `infra-auditor-dev` SSO profile.
4. Create the two PostgreSQL Secrets Manager entries.
5. Create the `infra-audit-rl-dev` and `infra-audit-rl-prod` S3 buckets.
6. Grant S3 `PutObject` to the approved `raw/snapshots/*` prefix.
7. Grant read-only EC2 security group, CloudWatch metric, and RDS operations
   permissions used by the implemented collectors.
8. Grant S3 `ListBucket` and `GetObject` for `raw/snapshots/*` to identities
   that need the local report UI, MCP, or future read APIs.
9. Run read-only RDS discovery.
10. Run local read-only PostgreSQL collection.
11. Confirm the S3 JSON snapshot URI printed by the CLI.
12. Run the local report UI.

ECS Fargate, EventBridge Scheduler, SES reporting, CI/CD OIDC, and historical
Parquet/Athena analysis remain deferred until S3-backed collection is validated.
