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
5. Run read-only RDS discovery.
6. Run local read-only PostgreSQL collection.
7. Inspect the local JSON snapshots under `data/snapshots/`.

S3 persistence, ECS Fargate, EventBridge Scheduler, SES reporting, CI/CD OIDC,
and historical Parquet/Athena analysis remain deferred until local collection is
validated.
