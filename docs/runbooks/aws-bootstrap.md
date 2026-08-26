# AWS Bootstrap Runbook

This runbook describes owner-managed AWS setup. The V0.1 code does not create or modify AWS resources.

## Read Permission Categories

Expected permissions include:

- `rds:Describe*`
- `rds:ListTagsForResource`
- `cloudwatch:GetMetricData`
- `cloudwatch:GetMetricStatistics`
- `cloudwatch:ListMetrics`
- `logs:DescribeLogGroups`
- `logs:DescribeLogStreams`
- `logs:GetLogEvents`
- `logs:FilterLogEvents`
- `logs:StartQuery`
- `logs:GetQueryResults`
- Performance Insights / Database Insights read operations when collectors are implemented
- `secretsmanager:GetSecretValue` only for `infra-auditor` secrets
- future S3 writes only to an approved audit bucket/prefix
- future SES send permission only as needed for reports

Explicitly avoid mutation permissions such as `rds:ModifyDBInstance`, `rds:DeleteDBInstance`, and `rds:RebootDBInstance`.

## Secrets

Create one secret per RDS instance:

```text
infra-auditor/postgres/raptor-catalog
infra-auditor/postgres/udb
```

Expected secret JSON:

```json
{
  "username": "prj_rl_rds_auditor_prod",
  "password": "set-in-secrets-manager"
}
```

Do not store endpoints, database names, VPC IDs, subnet IDs, security groups, or application data in the secret.

## First Validation

```bash
uv run infra-auditor discover aws --instance raptor-catalog
uv run infra-auditor discover aws --instance udb
```

Then run `collect` only after PostgreSQL auditor credentials and network ingress are ready.
