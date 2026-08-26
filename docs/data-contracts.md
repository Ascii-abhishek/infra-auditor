# Data Contracts

## Versioning

Application version and snapshot schema version are separate:

- `application_version`: semantic project version, currently `0.1.0`.
- `snapshot_schema_version`: persisted snapshot contract version, currently `1`.

Compatibility changes to persisted models must update this document and usually `decisions.md`.

## Run Metadata

`RunMetadata` contains:

- `run_id`
- `application_version`
- `snapshot_schema_version`
- `environment`
- `region`
- timezone-aware UTC `started_at` and `completed_at`
- overall collection `status`

## Instance Snapshot

`InstanceSnapshot` contains:

- logical alias,
- RDS DB instance identifier,
- region,
- status,
- optional normalized RDS instance metadata,
- PostgreSQL database inventory,
- collector result list,
- collection gaps.

## RDS Instance Evidence

`RDSInstance` includes instance identity, engine/version/class/status, storage facts, Multi-AZ/public/IAM-auth state, Database/Performance Insights fields, Enhanced Monitoring interval, log exports, parameter groups, backup/deletion/encryption posture, endpoint/port, VPC/subnet/security-group metadata, windows, and certificate details.

It must not contain secret values.

## Database Inventory Evidence

`DatabaseInfo` contains:

- name,
- connection allowance,
- template status,
- `system` or `application` classification,
- connection eligibility.

Known database names may appear in fixtures, but live inventory must be discovered.

## Collection Gaps

`CollectionGap` records collector, resource, status, error type, and sanitized message. Gaps are audit evidence.

## Future Findings

Future `Finding` records should include rule ID, fingerprint, category, severity, resource, title, summary, observed values, expected/policy values, evidence references, recommendation, and confidence where meaningful.
