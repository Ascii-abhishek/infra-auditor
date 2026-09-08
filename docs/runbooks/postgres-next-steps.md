# Practical next steps

## 1. Review the local configuration

Edit `config/environments.yaml` or your local registry selected through
`INFRA_AUDITOR_RESOURCE_CONFIG_PATH`. Version 3 groups services by region and instance, with explicit dependency and
Secrets Manager references; see [the adjacent config guide](../../config/README.md).
Keep production database passwords in Secrets Manager, not `.env` or YAML.

```bash
uv run infra-auditor config validate
```

Validation prints each instance's effective coverage without secrets or secret
IDs. Existing version-1 local registries still enable all current collectors.
Set a PostgreSQL instance's `subservices: []` to deliberately collect only its RDS evidence.

## 2. Extend only the auditor's S3 artifact access

If Sync all reports AccessDenied, use the [diagnosis and exact S3 policy](s3-access-denied.md).

The runtime still performs no infrastructure mutations. An AWS administrator
must update the existing auditor permission set/policy for the intended bucket.
In the **existing** S3 statements, allow these prefix patterns:

```text
raw/snapshots/schema=3/*
reports/snapshots/schema=3/*
runs/schema=3/*
```

Use each pattern in `s3:prefix` for `s3:ListBucket` on the bucket ARN, and as the
suffix of bucket object ARNs for `s3:GetObject` / `s3:PutObject`. Reader-only
identities need no PutObject. No DeleteObject, bucket-wide object access, or AWS
service mutation is required. The AWS identity runbook includes the updated dev
policy example. Preserve any separately needed historical access deliberately.

## 3. Validate the storage cutover

Restart `./run.sh` after changing configuration. Use **Sync all** (or CLI collect
once for each alias), because today's old snapshot does not validate the new
layout. Check both RDS and Database (PG), Raw Data, Reports and collector gaps.
A committed instance has seven raw objects, two report objects and one `runs/`
manifest. A partial collection is still useful but needs gap review.

Old schema-2 data remains untouched. Do not remove it as part of these steps.
The implementation session used fake external clients; it did not run live AWS
or PostgreSQL collection or verify your current IAM grants.

## 4. Update the existing group and project login

Use `grp_rl_infra_auditor` as the NOLOGIN permission group and
`prj_rl_infra_auditor` as the single project LOGIN. They are two roles, but only
one database login. Roles apply across databases on one PostgreSQL server;
the same names on another RDS server are separate server-local roles. You do
not need a separate auditor login for each database or subservice.

Run the **single block below separately on each RDS server**, using an administrator
with permission to manage these roles, grant the two monitoring memberships, and
grant database CONNECT. The existing inventory recorded PostgreSQL 15; the block
also handles PostgreSQL 16+ membership inheritance options. No new roles/passwords
are created. It grants all currently required monitoring permissions, not ALL
PRIVILEGES. It includes CONNECT to all current connectable non-template databases
except `rdsadmin`, covering `unified_db_live` / `raptor_db` where they exist.

The block is transactional: a missing role, forbidden membership, or permission
failure aborts setup. Stop on errors (in psql, enable ON_ERROR_STOP); if your client
leaves a failed transaction open, roll it back before retrying. It does not
silently remove unrelated memberships, ownership, PUBLIC privileges or table ACLs.
The last query inspects only the database you are currently connected to; repeat
that metadata check in each application database before treating data isolation
as verified. A CONNECT grant itself does not grant application-row SELECT.

```sql
-- Run this SAME block as a role/database administrator on EACH RDS server.
-- Connect to postgres (or another writable admin database), not as the auditor.
-- Uses existing roles; does not create users, change passwords, or grant table access.
BEGIN;
SET LOCAL statement_timeout = '20s';
SET LOCAL lock_timeout = '2s';

DO $audit_setup$
DECLARE
    role_name text;
    db_name text;
    setting_name text;
    parent_name text;
    member_name text;
BEGIN
    IF current_setting('server_version_num')::integer < 150000 THEN
        RAISE EXCEPTION 'This runbook supports PostgreSQL 15 and later';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['grp_rl_infra_auditor', 'prj_rl_infra_auditor'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            RAISE EXCEPTION 'Expected existing role % is missing on this server', role_name;
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname = role_name AND (rolsuper OR rolreplication OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'Role % has privileged attributes; review before setup', role_name;
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname IN (
                'pg_monitor', 'pg_stat_scan_tables', 'pg_read_all_data',
                'pg_write_all_data', 'pg_signal_backend', 'rds_superuser',
                'pg_read_server_files', 'pg_write_server_files', 'pg_execute_server_program'
            ) AND pg_has_role(role_name, oid, 'MEMBER')
        ) THEN
            RAISE EXCEPTION 'Role % has a forbidden membership path; review before setup', role_name;
        END IF;
    END LOOP;

    ALTER ROLE grp_rl_infra_auditor NOLOGIN INHERIT NOCREATEDB NOCREATEROLE;
    ALTER ROLE prj_rl_infra_auditor LOGIN INHERIT NOCREATEDB NOCREATEROLE CONNECTION LIMIT 2;

    FOR parent_name, member_name IN
        SELECT * FROM (VALUES
            ('pg_read_all_settings', 'grp_rl_infra_auditor'),
            ('pg_read_all_stats', 'grp_rl_infra_auditor'),
            ('grp_rl_infra_auditor', 'prj_rl_infra_auditor')
        ) AS grants(parent_role, member_role)
    LOOP
        EXECUTE format('GRANT %I TO %I', parent_name, member_name);
        -- PostgreSQL 16+ stores inheritance and SET options on each membership.
        IF current_setting('server_version_num')::integer >= 160000 THEN
            EXECUTE format('GRANT %I TO %I WITH INHERIT TRUE', parent_name, member_name);
            EXECUTE format('GRANT %I TO %I WITH SET FALSE', parent_name, member_name);
        END IF;
        EXECUTE format('REVOKE ADMIN OPTION FOR %I FROM %I', parent_name, member_name);
    END LOOP;

    -- Defaults belong on the LOGIN role; group defaults are not inherited at login.
    ALTER ROLE prj_rl_infra_auditor SET default_transaction_read_only = 'on';
    ALTER ROLE prj_rl_infra_auditor SET statement_timeout = '20s';
    ALTER ROLE prj_rl_infra_auditor SET lock_timeout = '2s';
    ALTER ROLE prj_rl_infra_auditor SET idle_in_transaction_session_timeout = '60s';
    ALTER ROLE prj_rl_infra_auditor SET idle_session_timeout = '10min';
    ALTER ROLE prj_rl_infra_auditor SET application_name = 'infra-auditor';

    -- Scope: all CURRENT connectable non-template databases except AWS rdsadmin.
    -- Includes postgres plus application DBs; future databases need another run.
    FOR db_name IN
        SELECT datname FROM pg_catalog.pg_database
        WHERE datallowconn AND NOT datistemplate AND datname <> 'rdsadmin'
        ORDER BY datname
    LOOP
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO grp_rl_infra_auditor', db_name);
        -- Remove only overrides of our six defaults, so a DB-specific old setting
        -- cannot override the new login defaults. Other role settings stay intact.
        FOREACH setting_name IN ARRAY ARRAY[
            'default_transaction_read_only', 'statement_timeout', 'lock_timeout',
            'idle_in_transaction_session_timeout', 'idle_session_timeout', 'application_name'
        ] LOOP
            EXECUTE format('ALTER ROLE prj_rl_infra_auditor IN DATABASE %I RESET %I',
                           db_name, setting_name);
        END LOOP;
    END LOOP;

    IF NOT pg_has_role('prj_rl_infra_auditor', 'pg_read_all_stats', 'USAGE')
       OR NOT pg_has_role('prj_rl_infra_auditor', 'pg_read_all_settings', 'USAGE') THEN
        RAISE EXCEPTION 'Monitoring privileges are not inherited by the login';
    END IF;
END
$audit_setup$;

COMMIT;

-- Expected: group cannot log in; project can; privileged attributes all false;
-- project connection limit is 2. These checks never read password-bearing fields.
SELECT rolname, rolcanlogin, rolinherit, rolconnlimit,
       rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname IN ('grp_rl_infra_auditor', 'prj_rl_infra_auditor');

-- Review every direct membership: only the intended monitoring/group grants
-- should be needed. Extra memberships require review; this script does not remove them.
SELECT member.rolname AS member, parent.rolname AS granted_role, membership.admin_option
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
JOIN pg_catalog.pg_roles AS parent ON parent.oid = membership.roleid
WHERE member.rolname IN ('grp_rl_infra_auditor', 'prj_rl_infra_auditor');

-- can_connect should be true for every listed DB; unexpected can_create needs review.
SELECT datname,
       has_database_privilege('prj_rl_infra_auditor', oid, 'CONNECT') AS can_connect,
       has_database_privilege('prj_rl_infra_auditor', oid, 'CREATE') AS can_create
FROM pg_catalog.pg_database
WHERE datallowconn AND NOT datistemplate AND datname <> 'rdsadmin'
ORDER BY datname;

-- Metadata-only privilege check for the CURRENT database; repeat this block in
-- each application DB if you want this last query to inspect each DB's objects.
-- Expected: no application relations. Extension views may appear for review.
SELECT n.nspname AS schema_name, c.relname AS relation_name,
       has_table_privilege('prj_rl_infra_auditor', c.oid, 'SELECT') AS table_select,
       has_any_column_privilege('prj_rl_infra_auditor', c.oid, 'SELECT') AS column_select
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
  AND (has_table_privilege('prj_rl_infra_auditor', c.oid, 'SELECT')
       OR has_any_column_privilege('prj_rl_infra_auditor', c.oid, 'SELECT'))
ORDER BY n.nspname, c.relname;
```

Afterward, reconnect **as `prj_rl_infra_auditor` over TLS** and verify the six
session defaults and connection access to intended databases. `SET ROLE` is not
an equivalent login-default test. Read-only defaults are defense in depth; actual
privilege isolation must also pass the metadata checks. Do not grant application
SELECT, pg_monitor, pg_read_all_data or administrative memberships to resolve gaps.

Update the `username` field in each existing Secrets Manager secret to
`prj_rl_infra_auditor`, with that server's existing login password, through your
normal secret-management workflow. Retain one secret per RDS instance; using the
same login name does not require sharing passwords. The code already obtains the
username from the secret, so there is no username/password YAML field to update.

Sources: [PostgreSQL role defaults](https://www.postgresql.org/docs/15/sql-alterrole.html),
[monitoring roles](https://www.postgresql.org/docs/15/predefined-roles.html), and
[PostgreSQL 16 membership options](https://www.postgresql.org/docs/16/sql-grant.html).
This SQL is provided for your manual review/execution; it was not run against AWS.

## 5. Agree the next implementation milestone

Next: sequential per-database orchestration and safe catalog inventory, with
explicit scope and independent gaps. Before implementation, provide the intended
database include/exclude list and confirm the two databases above. Next after
that: ownership/permission policy, then table/index health. See the modular
[PostgreSQL plan](../services/postgres.md). This phase deliberately precedes LLM
integration or additional infrastructure services.
