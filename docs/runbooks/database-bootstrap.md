# Database Bootstrap Runbook

This runbook records intended PostgreSQL safety posture. V0.1 code does not create roles or grants.
The current manual setup SQL is in [PostgreSQL next steps](postgres-next-steps.md#4-update-the-existing-group-and-project-login).
One NOLOGIN group holds permissions; one project LOGIN connects across databases.
The dated checks below refer to the previous role names and must be revalidated.

## Intended Roles

```text
grp_rl_infra_auditor
prj_rl_infra_auditor
```

## Intended Grants

```text
grp_rl_infra_auditor:
    pg_read_all_settings
    pg_read_all_stats
```

Do not grant:

```text
pg_monitor
pg_stat_scan_tables
pg_read_all_data
pg_write_all_data
pg_signal_backend
rds_superuser
```

## Login Role Safety Defaults

```text
default_transaction_read_only = on
statement_timeout = 20s
lock_timeout = 2s
idle_in_transaction_session_timeout = 60s
idle_session_timeout = 10min
application_name = infra-auditor
connection limit = 2
```

## Post-Creation Verification

Verify that the auditor role has the expected predefined role posture:

```text
pg_read_all_stats       true
pg_read_all_settings    true
pg_read_all_data        false
rds_superuser           false
```

Also verify the role cannot select from application tables. Do not run broad application table queries through the auditor.

## 2026-09-02 Boundary Check Result

The live auditor role was checked using fixed catalog queries only; no
application table rows were read.

Both configured instances showed:

- login role `prj_rl_rds_auditor_prod`,
- connection limit `2`,
- `default_transaction_read_only=on`,
- active `transaction_read_only=on`,
- `statement_timeout=20s`,
- `lock_timeout=2s`,
- `idle_in_transaction_session_timeout=1min`,
- `idle_session_timeout=10min`,
- membership in `pg_read_all_settings` and `pg_read_all_stats`,
- no membership in `pg_monitor`, `pg_stat_scan_tables`, `pg_read_all_data`,
  `pg_write_all_data`, `pg_signal_backend`, or `rds_superuser`,
- no database-level `CREATE` privilege on checked databases.

The auditor cannot connect to `unified_db_live` on `udb` or `raptor_db` on
`raptor-catalog`. All other non-template databases were connectable.

No application table privileges were observed. On `raptor-catalog`, the only
selectable non-system relations found were extension-owned
`pg_stat_statements` views in `public` on `datalyze_db`, `ptm_flow_prod`, and
`raptor_catalog`. The current V0.1 collector does not read those views; future
query/stat collectors must follow the query-text minimization boundary before
using `pg_stat_statements`.
