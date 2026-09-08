# AWS Identity And Access Bootstrap

This runbook describes the owner-managed AWS identity setup for `infra-auditor`.
The repository code does not create or modify AWS resources in V0.1.

## Current Repository State

Implemented code path:

```text
infra-auditor collect
-> optional boto3 profile from INFRA_AUDITOR_AWS_PROFILE
-> RDS DescribeDBInstances
-> EC2 DescribeSecurityGroups
-> CloudWatch GetMetricData
-> RDS DescribePendingMaintenanceActions, DescribeDBRecommendations, DescribeDBParameters
-> Secrets Manager GetSecretValue
-> fixed PostgreSQL pg_catalog inventory and activity summaries
-> S3 JSON snapshot
```

The code is ready for temporary AWS credentials. `INFRA_AUDITOR_AWS_PROFILE` is
optional for local development. If it is unset, boto3 uses its standard provider
chain, including ECS task credentials in production. Production must not depend
on a named local AWS profile.

The human developer permission set needs S3 `PutObject` access for dev snapshot
writes and read-only AWS describe/get permissions for each implemented evidence
collector.

## Identity Boundaries

Keep these identities separate:

- Human/developer identity: IAM Identity Center user or group assigned to an
  `InfraAuditorDeveloper` permission set for local read-only runs.
- Production workload identity: `InfraAuditorTaskRole`, the ECS task role used
  by application code inside the container.
- ECS execution identity: ECS task execution role used by ECS/Fargate for image
  pulls, CloudWatch log delivery, and ECS-required execution operations.
- EventBridge Scheduler execution identity: a scheduler role that can start only
  the approved ECS task and pass only the approved ECS roles.
- Future CI/CD identity: GitHub Actions OIDC role for deployment, restricted by
  repository and branch or environment. No GitHub access keys.

Do not collapse application AWS permissions into the ECS execution role, and do
not give the application task role `ecs:RunTask`.

## Check IAM Identity Center Status

Use an existing administrative or security-read profile for these checks. Do not
paste command output containing account IDs into chat.

First confirm AWS CLI v2 is available:

```bash
aws --version
```

Then check whether IAM Identity Center is visible to your current credentials:

```bash
aws sso-admin list-instances \
  --region <identity-center-region-or-ap-south-1> \
  --profile <existing-admin-or-read-profile> \
  --query 'Instances[].{Name:Name,Status:Status,PrimaryRegion:PrimaryRegion,Regions:Regions[].RegionName}' \
  --output table
```

Interpretation:

- `Status` is `ACTIVE`: use the `PrimaryRegion` value as the SSO region when
  configuring local profiles.
- Empty result: IAM Identity Center might not be configured, might be in another
  region, or the caller may not have permission to list instances.
- Access denied: ask an AWS administrator to check the IAM Identity Center
  dashboard and provision the permission set.

Do not create or change IAM Identity Center from this repo or from the auditor
application.

## Developer Permission Set

Create an IAM Identity Center permission set named approximately:

```text
InfraAuditorDeveloper
```

Purpose: run and debug the current V0.1 auditor locally.

Attach an inline policy shaped like this, replacing placeholders outside the
repository:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ValidateCaller",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    },
    {
      "Sid": "DescribeConfiguredRdsInstances",
      "Effect": "Allow",
      "Action": "rds:DescribeDBInstances",
      "Resource": [
        "arn:aws:rds:ap-south-1:<account-id>:db:cleancatalograptorsupplies",
        "arn:aws:rds:ap-south-1:<account-id>:db:udb"
      ]
    },
    {
      "Sid": "ReadConfiguredPostgresSecrets",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:ap-south-1:<account-id>:secret:infra-auditor/postgres/raptor-catalog-*",
        "arn:aws:secretsmanager:ap-south-1:<account-id>:secret:infra-auditor/postgres/udb-*"
      ]
    },
    {
      "Sid": "WriteDevInfraAuditSnapshots",
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": [
        "arn:aws:s3:::infra-audit-rl-dev/raw/snapshots/schema=3/*",
        "arn:aws:s3:::infra-audit-rl-dev/reports/snapshots/schema=3/*",
        "arn:aws:s3:::infra-audit-rl-dev/runs/schema=3/*"
      ]
    },
    {
      "Sid": "ListDevInfraAuditSnapshotsForReports",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::infra-audit-rl-dev",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "raw/snapshots/schema=3/*",
            "reports/snapshots/schema=3/*",
            "runs/schema=3/*"
          ]
        }
      }
    },
    {
      "Sid": "ReadDevInfraAuditSnapshotsForReports",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::infra-audit-rl-dev/raw/snapshots/schema=3/*",
        "arn:aws:s3:::infra-audit-rl-dev/reports/snapshots/schema=3/*",
        "arn:aws:s3:::infra-audit-rl-dev/runs/schema=3/*"
      ]
    },
    {
      "Sid": "ReadAttachedSecurityGroups",
      "Effect": "Allow",
      "Action": "ec2:DescribeSecurityGroups",
      "Resource": "*"
    },
    {
      "Sid": "ReadRdsCloudWatchMetrics",
      "Effect": "Allow",
      "Action": "cloudwatch:GetMetricData",
      "Resource": "*"
    },
    {
      "Sid": "ReadRdsOperationalRecommendations",
      "Effect": "Allow",
      "Action": "rds:DescribeDBRecommendations",
      "Resource": "*"
    },
    {
      "Sid": "ReadConfiguredRdsMaintenance",
      "Effect": "Allow",
      "Action": "rds:DescribePendingMaintenanceActions",
      "Resource": [
        "arn:aws:rds:ap-south-1:<account-id>:db:cleancatalograptorsupplies",
        "arn:aws:rds:ap-south-1:<account-id>:db:udb"
      ]
    },
    {
      "Sid": "ReadConfiguredRdsParameterGroups",
      "Effect": "Allow",
      "Action": "rds:DescribeDBParameters",
      "Resource": "arn:aws:rds:ap-south-1:<account-id>:pg:*"
    }
  ]
}
```

Notes:

- Do not grant `AdministratorAccess`, `PowerUserAccess`, `ReadOnlyAccess`,
  `rds:*`, `secretsmanager:*`, `s3:*`, `iam:*`, or `ec2:*`.
- Snapshot writers do not need `s3:GetObject`, `s3:ListBucket`, or
  `s3:DeleteObject`.
- The local report UI does need `s3:ListBucket` and `s3:GetObject` for raw
  snapshots. Keep that reader permission separate from unattended collection
  roles if the production collector should remain write-only.
- If the secrets use the AWS managed `aws/secretsmanager` key, no explicit
  `kms:Decrypt` statement is expected. If a customer-managed KMS key is chosen,
  add narrowly scoped `kms:Decrypt` for that key.
- CloudWatch Logs, Performance Insights/Database Insights, and SES are deferred
  until collectors or reports actually use those APIs.
- Current code does not require `ec2:DescribeSecurityGroupRules`,
  `cloudwatch:ListMetrics`, `rds:Modify*`, or any `pi:*` permissions.

## Gradual Permission Expansion

Add permissions only when the matching collector and report contract are being
implemented. The preferred loop is:

1. Add the smallest read-only action set for one collector family.
2. Update `docs/security-boundaries.md`, `docs/runtime-flows.md`, and
   `docs/data-contracts.md`.
3. Add fixed collector code and fake-client unit tests.
4. Run one live dev collection and inspect snapshots for accidental secrets,
   raw query text, and excessive identity data.
5. Promote the new data into reports and MCP only after the snapshot boundary is
   accepted.

Recommended expansion order:

1. RDS metrics depth:
   extend the fixed CloudWatch RDS metric list through `cloudwatch:GetMetricData`
   before adding a new permission. Keep dimensions fixed to configured RDS DB
   instances.
2. RDS performance context:
   evaluate Performance Insights or Database Insights read APIs only after a
   minimization design exists for SQL-like dimensions and wait/event data.
3. Database (PG) depth:
   prefer PostgreSQL catalog/statistics grants already allowed by the auditor
   role. Do not add `pg_read_all_data`, `pg_stat_scan_tables`, `pg_monitor`, or
   unrestricted query text.
4. AWS identity posture:
   consider `iam:GenerateCredentialReport`, `iam:GetCredentialReport`,
   `iam:GetAccessKeyLastUsed`, and
   `iam:GenerateServiceLastAccessedDetails`/`iam:GetServiceLastAccessedDetails`.
   Store last-used and credential-state metadata only, never access key secret
   values.
5. IAM Identity Center:
   consider read-only `sso-admin` and `identitystore` list/describe APIs such as
   permission-set and user/group listing. Minimize personal data in snapshots.
6. EC2 fleet posture:
   consider `ec2:DescribeInstances`, `ec2:DescribeVolumes`,
   `ec2:DescribeInstanceStatus`, and fixed EC2 CloudWatch metric reads for
   configured instances only.

After assigning the permission set to your user or group, configure the local
profile. These examples use `infra-auditor-dev`; use the actual local profile
name if your workstation uses a different one.

```bash
aws configure sso --profile infra-auditor-dev
aws sso login --profile infra-auditor-dev
aws sts get-caller-identity --profile infra-auditor-dev
```

Then use either:

```bash
AWS_PROFILE=infra-auditor-dev uv run infra-auditor discover aws --instance raptor-catalog
```

or local `.env` only for the non-secret profile setting:

```bash
INFRA_AUDITOR_AWS_PROFILE=infra-auditor-dev
SYS_ENV=dev
```

Never store `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or
`AWS_SESSION_TOKEN` in project `.env` files as the normal authentication path.

## Secrets Manager Setup

Create one secret per configured RDS instance:

```text
infra-auditor/postgres/raptor-catalog
infra-auditor/postgres/udb
```

Each secret value must contain only:

```json
{
  "username": "prj_rl_infra_auditor",
  "password": "set-in-secrets-manager"
}
```

Do not include endpoints, account IDs, engine versions, VPCs, subnet IDs,
security groups, ports unless nonstandard, database inventory, or connection
strings.

Preferred console procedure:

1. Open AWS Secrets Manager in `ap-south-1`.
2. Choose `Store a new secret`.
3. Choose `Other type of secret`.
4. Use key/value or plaintext JSON with only `username` and `password`.
5. Use the AWS managed `aws/secretsmanager` encryption key unless there is a
   concrete cross-account, key-policy, or rotation requirement.
6. Name the secret exactly as listed above.
7. Leave rotation disabled for this bootstrap unless a rotation design is
   approved separately.

CLI procedure that avoids putting the password in shell history:

```bash
umask 077
tmp_secret_file="$(mktemp)"
read -r -s IA_DB_PASSWORD
export IA_DB_PASSWORD
python3 - <<'PY' > "$tmp_secret_file"
import json
import os

print(json.dumps({
    "username": "prj_rl_infra_auditor",
    "password": os.environ["IA_DB_PASSWORD"],
}))
PY
aws secretsmanager create-secret \
  --region ap-south-1 \
  --profile <setup-profile> \
  --name infra-auditor/postgres/raptor-catalog \
  --secret-string "file://$tmp_secret_file"
rm -f "$tmp_secret_file"
unset IA_DB_PASSWORD
```

Repeat for `infra-auditor/postgres/udb`. Do not paste the password into chat,
docs, tests, snapshots, or issue trackers.

## First Validation

After the permission set and secrets exist:

```bash
aws sso login --profile infra-auditor-dev
aws sts get-caller-identity --profile infra-auditor-dev
AWS_PROFILE=infra-auditor-dev uv run infra-auditor discover aws --instance raptor-catalog
AWS_PROFILE=infra-auditor-dev uv run infra-auditor discover aws --instance udb
```

Run `collect` only after the Secrets Manager entries exist, S3 snapshot write
access exists, and the runner has network access to PostgreSQL:

```bash
AWS_PROFILE=infra-auditor-dev uv run infra-auditor collect --instance raptor-catalog
AWS_PROFILE=infra-auditor-dev uv run infra-auditor collect --instance udb
```

If RDS discovery succeeds but both collections return `PARTIAL_SUCCESS` with
`secrets.postgres_credentials` failed, update the assigned permission set to
allow `secretsmanager:GetSecretValue` for the two configured secret ARNs. Then
re-login with `aws sso login` so the local session receives the updated
permissions.

If `GetSecretValue` succeeds but collection still returns `PARTIAL_SUCCESS` with
`secret schema validation failed`, edit the secret JSON to contain only
`username` and `password`. Do not use the Secrets Manager RDS template shape
with `engine`, `host`, `port`, `dbname`, or `dbInstanceIdentifier`.

## Future Production Roles

`InfraAuditorTaskRole` will eventually hold application permissions:

- RDS describe/read APIs used by implemented collectors.
- Secrets Manager `GetSecretValue` for `infra-auditor/postgres/*`.
- CloudWatch metric reads used by implemented collectors.
- EC2 security group describe reads used by implemented collectors.
- RDS recommendations, pending maintenance, and parameter group reads used by
  implemented collectors.
- CloudWatch logs reads only when collectors use them.
- Performance Insights/Database Insights reads only when collectors use them.
- S3 `PutObject` to the approved schema-3 raw, reports and runs prefixes in the production
  audit bucket.
- SES send permissions only when reports are implemented.

The ECS task execution role will hold ECS/Fargate execution permissions:

- pull the auditor image from ECR,
- write task logs to CloudWatch Logs,
- retrieve ECS execution-time secrets only if the task definition requires them.

The EventBridge Scheduler execution role will eventually allow only:

- `ecs:RunTask` for the approved cluster and task definition,
- `iam:PassRole` for the approved task role and execution role.

The future GitHub Actions role will use OIDC and a trust policy restricted to
the approved repository plus branch or GitHub environment. Do not create CI/CD
AWS access keys.
