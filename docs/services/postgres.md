# PostgreSQL

## Implemented coverage

All current PostgreSQL collectors share one TLS connection to the bootstrap
database (default `postgres`). Database inventory is cluster-wide discovery;
it does **not** inspect objects in each discovered database. Database eligibility
is catalog classification, not proof of a successful connection or full access.

| Subservice | Fixed source | Evidence | Current findings |
| --- | --- | --- | --- |
| `database-inventory` | `pg_database` | Names, connection allowance, templates, system/application classification and eligibility | Inventory summary; no per-database object audit |
| `activity-summary` | Aggregated `pg_stat_activity` | Counts by database/role/application/client/state/wait type, bounded session/transaction ages | Idle transaction OPS003, long transaction OPS005, concentration OPS014, missing application names OPS015 |
| `role-security` | `pg_roles`, `pg_auth_members` | Safe role attributes and membership edges, grantor, admin option | Administrative membership paths SEC002, login-to-login membership review SEC003 |

No application rows, SQL text, passwords, `pg_authid`, routine bodies, or policy
expressions are collected. Credentials are resolved through Secrets Manager only
when at least one PostgreSQL subservice is enabled. Credential resolution status
and gaps are retained with the database-inventory boundary. Disabled collectors
record `SKIPPED`; failures retain independent structured gaps. A successful run
means its selected collection completed, not that the database is fully audited.

Each subservice has its own `raw/` artifact. PostgreSQL findings live under
`reports/.../service=postgres/...`. Reports show inventory counts, activity,
role/membership counts, severity counts, findings and collector status.

## Deep PostgreSQL Audit — next milestone, not implemented

Implement in this order, with independent database/collector gaps and a bounded
sequential connection flow. Close the bootstrap connection before visiting each
eligible database; preserve the auditor login's connection limit of two.

| Stage | Evidence to design and collect | Analysis and limitations |
| --- | --- | --- |
| 1. Per-database orchestration | Explicit database include/exclude scope, CONNECT checks, per-database coverage | Unreachable databases remain visible gaps; never claim full coverage |
| 2. Catalog inventory | Schemas, relations, column metadata, constraints, extensions, ownership, dependency identifiers | Names/types only; no defaults, expressions or bodies that can embed sensitive literals without minimization review |
| 3. Permissions and RLS | ACLs, grant options, default privileges, memberships, owners, RLS flags, policy role/command metadata | Compare against owner-approved policy; PUBLIC EXECUTE or login ownership is a review candidate without that policy |
| 4. Table/index health | Sizes, live/dead tuple estimates, vacuum/analyze history, freeze age, index validity/usage and constraints | Estimates are not measured bloat; zero scans alone never justify dropping an index |
| 5. Routines/triggers | Owner, language, security-definer flag, safe search-path assessment, trigger/function/table links and enabled states | No routine bodies; function call counts need enabled statistics and sufficient observation time |
| 6. Blocking/query performance | Bounded lock relationships, query IDs and aggregate timing/call statistics | No query text; optional extension absent becomes a capability gap |
| 7. History and repair plans | Repeated observations, stats reset/window quality, evidence references, policy version | Confidence, prerequisites, proposed manual fix, validation and rollback; never automatic execution |

Before stage 3, design a separate validated policy contract for expected owner
and group roles, approved login roles, schema access, RLS expectations, languages,
extensions, default privileges, and expiring exceptions with reasons. These keys
are intentionally not accepted by the current runtime YAML: unsupported policy
must fail visibly rather than silently appear enforced.

A trigger belongs to a table/view. An unused trigger function is a possible review
candidate; an “unattached trigger” is not a useful audit category. Routine usage
statistics cannot prove redundancy when tracking is disabled. Permissions,
health, and query performance need separate evidence and policy explanations.

The LLM phase follows this milestone. It will explain approved evidence and
findings through MCP. Any future live checks must be server-owned fixed templates
with typed arguments, never SQL supplied by a model.
