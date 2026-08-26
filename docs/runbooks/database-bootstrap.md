# Database Bootstrap Runbook

This runbook records intended PostgreSQL safety posture. V0.1 code does not create roles or grants.

## Intended Roles

```text
grp_rl_rds_auditor
prj_rl_rds_auditor_prod
```

## Intended Grants

```text
grp_rl_rds_auditor:
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
