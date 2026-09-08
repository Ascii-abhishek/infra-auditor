# RDS

RDS is the infrastructure side of the PostgreSQL target. All enabled operations
are read-only AWS calls. YAML selects subservices; region comes from the instance
override or the AWS default. AWS discovery supplies endpoints and capacity facts.

| Subservice | Collected evidence | API / dependency | Current analysis |
| --- | --- | --- | --- |
| `instance` | Engine/version/class, status, storage, availability, network, backups, encryption, deletion protection, monitoring flags, windows, certificates, parameter groups | `rds:DescribeDBInstances`; mandatory for endpoint discovery | Public exposure review CFG009; pending parameter apply CFG002 |
| `ec2-security-groups` | Attached groups, normalized IPv4/IPv6 ingress and database-port exposure | `ec2:DescribeSecurityGroups` | Public RDS plus unrestricted ingress SEC001 |
| `cloudwatch-rds-metrics` | CPU, connections, freeable memory, free storage, read/write latency and IOPS, disk queue, burst balance | `cloudwatch:GetMetricData` | Free storage OPS001, CPU OPS007, memory OPS008 |
| `operations` | Pending maintenance, recommendations, current parameter values | `rds:DescribePendingMaintenanceActions`, `rds:DescribeDBRecommendations`, `rds:DescribeDBParameters` | Maintenance OPS012; recommendations OPS013 |

CloudWatch stores count/min/max/average/latest summaries over the configured
window (default 24 hours, 300-second samples), not a historical time series.
Missing or unsupported metric data is not a zero observation. Threshold rules
are currently code-owned; YAML controls coverage, not rule severities/thresholds.

Each subservice produces its own `raw/` artifact, including status and gaps.
RDS findings are stored under `reports/.../service=rds/...`. The console combines
these with the same run's metadata and reports severity/rule counts, selected
metric summaries, exposure, operations, and collector status. Collection of a
field does not imply a policy rule exists for it; consult the audit catalog.

Deferred: account IAM posture, standalone EC2, logs, Performance/Database Insights
queries, parameter policy baselines, richer backup/certificate policies, and
historical capacity analysis. No RDS modification or recommendation application.
