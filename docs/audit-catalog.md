# Audit Catalog

This catalog records implemented and planned deterministic rules plus the
required evidence posture.

## Security

### SEC001 - Public RDS with unrestricted PostgreSQL ingress

- Category: security
- Scope: RDS instance/security groups
- Status: implemented
- Severity: critical
- Evidence: `PubliclyAccessible`, VPC/security group ingress including IPv4 and IPv6
- Automatic remediation allowed: NO

### SEC002 - LOGIN role has effective membership path to `rds_superuser`

- Category: security
- Scope: PostgreSQL roles
- Status: implemented
- Severity: high
- Evidence: role graph and effective memberships
- Automatic remediation allowed: NO

### SEC003 - LOGIN role inherits another LOGIN role

- Category: security/review
- Scope: PostgreSQL roles
- Status: implemented
- Severity: medium/review
- Evidence: role membership graph
- Automatic remediation allowed: NO

### SEC004 - infra-auditor has application data SELECT privilege

- Category: security
- Scope: PostgreSQL permissions
- Severity: critical
- Evidence: auditor role privilege checks
- Automatic remediation allowed: NO

## Operations

- OPS001 - Low free storage from CloudWatch/RDS storage evidence: implemented
- OPS002 - High connection utilization versus max connections
- OPS003 - Idle-in-transaction sessions: implemented
- OPS004 - Maintenance window overlaps configured business hours
- OPS005 - Long-running transactions: implemented
- OPS006 - Blocking chains and lock waits
- OPS007 - CPU sustained high utilization or anomaly: implemented for threshold checks
- OPS008 - Freeable memory sustained low or anomaly: implemented for threshold checks
- OPS009 - Read/write latency elevated or anomalous
- OPS010 - Disk queue depth elevated
- OPS011 - Burst balance or EBS IO balance risk where applicable
- OPS012 - RDS pending maintenance or pending modified values: implemented for maintenance
- OPS013 - RDS recommendation open or overdue: implemented
- OPS014 - Connection usage concentrated by user, database, client, or application: implemented
- OPS015 - Client/application names missing or unmanaged: implemented

## Configuration

- CFG001 - Parameter group differs from expected project baseline
- CFG002 - Parameter change pending reboot: implemented for parameter group apply status
- CFG003 - PostgreSQL logging settings insufficient for operations
- CFG004 - Autovacuum settings risky for observed database/table sizes
- CFG005 - Connection/timeouts baseline missing for non-auditor roles
- CFG006 - Backup retention or deletion protection below policy
- CFG007 - Certificate approaching expiry
- CFG008 - Single-AZ instance where policy requires Multi-AZ
- CFG009 - Public RDS exposure requires security group ingress review: implemented

## Maintenance

- VAC001 - Autovacuum falling behind
- VAC002 - Stale analyze
- VAC003 - Potential XID/freeze risk

## Indexes

- IDX001 - Invalid index
- IDX002 - Large unused index candidate
- IDX003 - Potential duplicate/overlapping indexes

Never translate `idx_scan = 0` directly into `DROP INDEX`. Index recommendations require sufficient statistics age/history and contextual evidence.

## Query And Session Safety

Future query/session collectors may use safe operational metadata such as user,
database, application name, state, wait event, backend age, transaction age,
connection counts, query ID where available, and bounded durations.

Do not collect unrestricted SQL text by default. Any query text evidence needs a
separate minimization/redaction design first.
