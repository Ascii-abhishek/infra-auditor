# Audit Catalog

No deterministic rules are implemented in V0.1. This catalog records planned rules and the required evidence posture.

## Security

### SEC001 - Public RDS with unrestricted PostgreSQL ingress

- Category: security
- Scope: RDS instance/security groups
- Severity: critical
- Evidence: `PubliclyAccessible`, VPC/security group ingress including IPv4 and IPv6
- Automatic remediation allowed: NO

### SEC002 - LOGIN role has effective membership path to `rds_superuser`

- Category: security
- Scope: PostgreSQL roles
- Severity: high
- Evidence: role graph and effective memberships
- Automatic remediation allowed: NO

### SEC003 - LOGIN role inherits another LOGIN role

- Category: security/review
- Scope: PostgreSQL roles
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

- OPS001 - Low free storage
- OPS002 - High connection utilization
- OPS003 - Idle-in-transaction session
- OPS004 - Maintenance window overlaps configured business hours
- OPS005 - Long-running transaction
- OPS006 - Blocking chain

## Maintenance

- VAC001 - Autovacuum falling behind
- VAC002 - Stale analyze
- VAC003 - Potential XID/freeze risk

## Indexes

- IDX001 - Invalid index
- IDX002 - Large unused index candidate
- IDX003 - Potential duplicate/overlapping indexes

Never translate `idx_scan = 0` directly into `DROP INDEX`. Index recommendations require sufficient statistics age/history and contextual evidence.
