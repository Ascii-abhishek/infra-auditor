# Project Context

The team operates production data and infrastructure services where permissions, parameters, session behavior, table/index health, AWS recommendations, and maintenance posture can drift over time.

`infra-auditor` exists to collect deterministic evidence that humans and later constrained LLM analysts can use without relying on memory or ad hoc production queries.

## Current AWS Context

- One primary AWS account is in scope.
- The human owner has broad AWS management capability.
- Teammates generally use more limited IAM roles for CLI/service access.
- AWS resources exist in multiple regions.
- RDS V1 is currently in `ap-south-1`.

## RDS Instance: raptor-catalog

- Logical alias: `raptor-catalog`
- AWS DB instance identifier: `cleancatalograptorsupplies`
- Engine: PostgreSQL 15.17
- Class: `db.m6g.xlarge`
- Storage: gp3, 1200 GiB allocated, 12000 IOPS, throughput 500
- Storage autoscaling: not configured
- Multi-AZ: false
- PubliclyAccessible: true
- IAM DB authentication: false
- Database Insights: standard
- Performance Insights: enabled, 7 day retention
- Enhanced Monitoring: disabled
- PostgreSQL log export: enabled
- Backup retention: 7 days
- Deletion protection: enabled
- Encryption: enabled
- Parameter group: `raptor-catalog-optimization`, in sync

Known database names and sizes are bootstrap context only. Actual inventory must be discovered dynamically.

## RDS Instance: udb

- Logical alias: `udb`
- AWS DB instance identifier: `udb`
- Engine: PostgreSQL 15.17
- Class: `db.m6g.xlarge`
- Storage: gp3, 1000 GiB allocated, 12000 IOPS, throughput 500
- Storage autoscaling: not configured
- Multi-AZ: false
- PubliclyAccessible: true
- IAM DB authentication: false
- Database Insights: standard
- Performance Insights: enabled, 7 day retention
- Enhanced Monitoring: disabled
- PostgreSQL log export: enabled
- Backup retention: 7 days
- Deletion protection: enabled
- Encryption: enabled
- Parameter group: `raptor-catalog-optimization`, in sync

Known database names are bootstrap context only. Actual inventory must be discovered dynamically.

## Network Context

Both RDS instances currently live in the same VPC/subnet set. Do not hard-code VPC, subnet, or security group IDs in source code or normal configuration. Discover them through AWS APIs.

Future production deployment may run an `infra-auditor` ECS task inside the VPC with SG-to-SG PostgreSQL rules and no inbound Internet access. This is not implemented in V0.1.

## Known Bootstrap Findings

- Effective administrative role paths exist on Raptor Catalog, including login membership paths to `rds_superuser`.
- Some login roles inherit other login roles. This should be reviewed against the preferred `LOGIN -> NOLOGIN group role` pattern.
- Both current instances are Single-AZ. Treat this as an observed fact until policy is defined, not an automatic recommendation.
