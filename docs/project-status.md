# Current Project Status

## Latest diagnosis — 2026-09-08 S3 access

Owner reports database permissions updated and Sync all attempted. Screenshot
shows PutObject AccessDenied at `reports/snapshots/schema=3/`. Live read-only
probes using profile `infra-auditor` (permission set `prm_rl_infra_auditor`) confirm
raw listing/GetObject work, while exact report/manifest listings fail for both
aliases. IAM policy inspection is denied, so the exact policy source is unverified.
Likely old raw-only prefix coverage. No local evidence fallback exists.

The manual fix and reusable S3-only JSON are in
[the S3 access runbook](runbooks/s3-access-denied.md). Owner must merge S3 statements,
provision the permission set, refresh/restart and retry Sync all. No IAM/S3 writes
or database collection were performed during diagnosis. Earlier raw objects can
remain; failed runs have no completion manifest. DB collection success remains to
be checked after the S3 fix.

## Current checkpoint — 2026-09-08

- Owner reports prior changes committed and schema-1 removed from dev bucket.
- Added version-3 service/region/instance YAML with explicit host dependencies;
  disabled PostgreSQL coverage skips secrets and database access.
- Schema 3 separates seven raw artifacts, two service finding reports, and one
  completion manifest under sibling raw/reports/runs prefixes. Only RDS and
  PostgreSQL service partitions remain. Old schema-2 objects are not modified.
- CLI/UI/MCP expose effective safe coverage; future service navigation hidden.
- Modular service docs, storage explanation, manual permission/setup runbook and
  Deep PostgreSQL Audit roadmap added. No new per-database collectors yet.
- Local checks: Ruff, mypy and pytest (66 tests) passed. No live AWS/PG collection,
  IAM/grant changes or bucket cleanup in this session. Owner comprehension/live
  validation remain pending before accepting this architecture checkpoint.

Follow-up: the owner uses `grp_rl_infra_auditor` (NOLOGIN group) and
`prj_rl_infra_auditor` (one LOGIN per server). Current role instructions and secret
examples now use those names. `postgres-next-steps.md` contains one transactional
manual SQL block for each server's monitoring memberships, login defaults,
CONNECT grants and metadata-only privilege checks. No SQL was executed on AWS.
The actual renamed file is `config/environments.yaml`; defaults/references and
the local dotenv registry-path value were updated. `config/README.md` documents
all supported strings, dependencies, overrides and multiple-region examples.

Owner comprehension responses clarified: manifests commit stored families even
with collector gaps; disabled means intentionally uncollected, not healthy or a
broken collector. Live validation and next database-scope cross-check remain.

Older entries below record historical implementations and live observations;
this checkpoint supersedes their storage layout and next-task recommendations.

## Current Phase

V0.1 repository bootstrap and minimal read-only collection foundation.

## What Works

- `uv run infra-auditor config validate` validates settings and `config/environments.yaml`.
- `uv run infra-auditor discover aws --instance <alias>` can call read-only RDS discovery when AWS credentials/permissions exist.
- `uv run infra-auditor collect --instance <alias>` builds a minimal snapshot path:
  RDS discovery, AWS security group ingress, CloudWatch RDS metric summaries,
  RDS operations/configuration evidence, Secrets Manager credential resolution,
  PostgreSQL database inventory, PostgreSQL activity summary, PostgreSQL role
  security evidence, deterministic findings, and S3 JSON persistence.
- Unit tests use fakes and do not touch production AWS/RDS.
- The PostgreSQL auditor roles/users have been created on both target RDS PostgreSQL instances, according to owner handoff.
- Local AWS authentication is ready to use IAM Identity Center or other temporary credentials through boto3's standard provider chain. `INFRA_AUDITOR_AWS_PROFILE` remains optional for local development and must not be required in production.
- Local `.env` exists outside git with `INFRA_AUDITOR_AWS_PROFILE=infra-auditor`.
- The `infra-auditor` local AWS profile is logged in and can call STS, RDS discovery, and Secrets Manager for both configured instances.
- Live V0.1 collection succeeds for both `raptor-catalog` and `udb`, including
  AWS discovery, attached security group ingress, CloudWatch RDS metric
  summaries, RDS operations evidence, Secrets Manager credential resolution,
  PostgreSQL database inventory, PostgreSQL activity summary, PostgreSQL role
  security, deterministic findings, and S3 JSON snapshot persistence.
- Collection now writes only canonical schema-2 service/subservice artifacts
  under `raw/snapshots/schema=2/...` for RDS, PostgreSQL, and deterministic
  findings, followed by a completion manifest. Current RDS-adjacent EC2
  security group and CloudWatch RDS metric evidence are RDS subservices.
- The PostgreSQL auditor permission boundary has been checked with fixed catalog queries and mostly matches the intended read-only posture.
- `SYS_ENV` now defaults to `dev`, accepts only `dev` or `prod`, and derives snapshot bucket names as `infra-audit-rl-<SYS_ENV>`.
- PostgreSQL security rules `SEC002` and `SEC003` are implemented and embedded
  in snapshots.
- AWS/RDS rules for public exposure, open RDS recommendations, pending
  maintenance, pending parameter apply status, CPU pressure, low free storage,
  and low freeable memory are implemented.
- PostgreSQL activity rules for idle-in-transaction sessions, long
  transactions, concentrated connection ownership, and missing
  `application_name` are implemented.
- Deterministic snapshot and fleet report summaries are implemented over raw
  snapshots.
- `uv run infra-auditor serve` starts a local FastAPI/Bootstrap report console using
  `INFRA_AUDITOR_WEB_HOST` and `INFRA_AUDITOR_WEB_PORT`, defaulting to
  `127.0.0.1:8008`.
- `./run.sh` is available as the local central runner: it checks Python/uv,
  syncs dependencies, loads `.env`, and starts the report console.
- The report console uses a left pane with project environment/bucket context,
  global Sync all, and navigation for RDS, Database (PG),
  planned AWS, planned EC2, Elasticsearch, Bitbucket, Reports, Raw Data, and a
  fixed Chat entry. Runtime selectors and actions live in the right pane.
- Service views expose right-pane selectors for subservice, date, and timestamp,
  defaulting to the latest snapshot object.
- The visible report console sync actions run as background jobs with per-alias
  progress polling. Service views show `Sync now`; global `Sync all` lives below
  the sidebar project title. Today sync remains available through MCP.
- The report console now renders a lightweight shell first and loads S3-backed
  content through `/view`, so slow AWS/S3 token or network work shows behind a
  visible loader rather than delaying the whole page.
- `uv run infra-auditor mcp` starts a local stdio MCP server with tools over
  configured instances, latest reports, finding summaries, completed-run
  listings, latest approved artifacts, and controlled latest/today-data sync.

## What Is Partially Implemented

- Snapshot model contains run metadata, RDS metadata, AWS network/metric/ops
  evidence, database inventory, PostgreSQL activity evidence, PostgreSQL role
  security evidence, collector statuses, collection gaps, and findings.
- Artifact model contains run metadata, service/subservice and
  collector-boundary metadata, boundary status, and only the evidence owned by
  that RDS, PostgreSQL, or deterministic-finding split.
- Report model contains per-snapshot and per-service fleet summaries: severity
  counts, rule counts, top findings, collector statuses, network exposure
  summary, selected CloudWatch metric summaries, RDS operations summary, and
  PostgreSQL inventory/activity/role summary.
- Secrets Manager boundary validates `username` and `password`; live secrets now use the credential-only schema and were verified without printing values.
- PostgreSQL connection factory uses TLS and context managers.

## What Is Not Implemented

- Findings lifecycle/history.
- Performance Insights/Database Insights collectors.
- CloudWatch Logs collectors.
- Parquet/Glue/Athena storage.
- SES reports and email send actions.
- Docker/ECS/EventBridge deployment.
- Terraform.
- Pydantic AI, LLM analyst, OpenAI/Anthropic SDKs, hosted MCP, or MCP-backed
  chat.
- Automatic remediation.
- AWS permission sets, IAM roles, Secrets Manager secrets, S3 buckets, ECS tasks, EventBridge schedules, and CI/CD identities are not created by this repository.

## Known Findings

- Raptor Catalog has effective role paths to `rds_superuser`, including `usr_rl_abhishek_pathak -> raptorsupplies24 -> rds_superuser` and `role_cleanup -> raptorsupplies24 -> rds_superuser`.
- Login-to-login inheritance exists and should be reviewed.
- Latest deterministic `raptor-catalog` run produced 21 findings:
  `CFG009=1`, `OPS001=1`, `OPS003=1`, `OPS005=1`, `OPS012=1`, `OPS013=4`,
  `OPS015=1`, `SEC002=3`, and `SEC003=8`.
- Latest deterministic `udb` run produced 12 findings:
  `CFG009=1`, `OPS012=1`, `OPS013=5`, `OPS015=1`, `SEC002=1`, and `SEC003=3`.
- `PubliclyAccessible=true` exists on both RDS instances. The implemented
  network collector now evaluates attached security group ingress successfully.
- The auditor cannot connect to `unified_db_live` on `udb` or `raptor_db` on `raptor-catalog`; decide whether future collectors should require those databases.
- On `raptor-catalog`, `pg_stat_statements` extension views are selectable in `datalyze_db`, `ptm_flow_prod`, and `raptor_catalog`. This is not application table access, but future query/stat collectors must not read query text without a documented minimization design.

## Open Decisions

- Confirm per-database include/exclude scope, especially `unified_db_live` and
  `raptor_db`, and intended ownership/permissions policy before the deep audit.
- Future service and hosted LLM/MCP decisions are deferred behind PostgreSQL.

## Blockers

- No current blocker for read-only RDS PostgreSQL snapshot collection.
- Schema-3 live validation remains: new reports/runs prefixes need IAM access and
  a fresh Sync all. Existing schema-2 objects remain untouched.
- Parquet/Glue/Athena, Performance Insights, SES, and ECS/EventBridge
  deployment remain unimplemented.

## Next Recommended Task

Follow [practical next steps](runbooks/postgres-next-steps.md): validate coverage,
update only the schema-3 S3 prefixes, restart, and Sync all to verify raw/report/run
families on both instances. Then cross-check database scope and implement
sequential per-database catalog collection. Deep PostgreSQL Audit precedes the
LLM analyst and other services; see [coverage plan](services/postgres.md).

## Last Validation

2026-09-07 canonical schema-2 storage cutover:

- Removed full compatibility snapshot persistence and all schema-1 read paths.
- Finalized `schema/env/service/region/instance/subservice/date/timestamp`
  ordering, with optional instance partitions reserved for future non-instance
  services and `region=global` reserved for nonregional evidence.
- Collection writes eight boundary-owned artifacts and writes a small run
  manifest last; only manifests define completed runs.
- UI reports reconstruct an in-memory snapshot from a selected artifact's
  manifest, while Raw Data reads the selected artifact directly.
- MCP tools now expose completed runs and canonical artifacts. Today sync checks
  the latest manifest instead of coordinating duplicate object families.
- Manifest references are validated against the complete approved boundary set
  and exact canonical keys before referenced S3 reads.
- Ruff, formatting, mypy, configuration validation, JavaScript syntax, and all
  46 unit tests pass.
- No schema-2 live collection or schema-1 deletion was performed in this session.

2026-09-07 dependent filters and console cleanup (storage details superseded by
the schema-2 cutover above):

- Server/subservice/date changes now refresh dependent dates/timestamps through
  a scoped API, with loaders, stale-request cancellation, no-store responses,
  recoverable error states, and versioned browser assets.
- RDS/Database selectors require matching subservice artifacts and full snapshots;
  Raw Data full snapshot remains available for pre-split history.
- Removed stale-key override of selected filter context. History remains bounded
  to the reader's existing newest 50 objects per partition.
- Moved global Sync all below project branding; service actions say Sync now and
  sit at the right edge of each service heading. Removed visible Sync today;
  restored the environment value and icon-labelled snapshot bucket in a compact
  metadata row below the title.
- Python quality gates passed with 45 unit tests; JavaScript syntax check passed.
- Chromium checks with fake data passed for Apply navigation, dependent options,
  empty/error recovery, inline title/version fit, and collapsed-sidebar Sync all.
- A stale running FastAPI process was found serving the new static JavaScript
  without the newly registered `/api/filter-options` route, producing HTTP 404s.
  After restarting the local console, live read-only HTTP checks passed for both
  servers across RDS, PostgreSQL, and Raw Data transitions and the selected view URL.
- No live AWS/PostgreSQL collection was run; only approved S3 report-data reads occurred.


2026-09-02 repository/architecture review:

- Read project guardrails, architecture, runtime/config/security docs, runbooks, code, tests, `.env.example`, and git status/diff.
- Current git worktree was clean before documentation updates.
- Verified current code uses optional local AWS profile selection and otherwise relies on boto3 provider behavior.
- Added AWS identity/access bootstrap documentation and recorded official AWS research sources.
- Local validation passed: `uv run infra-auditor config validate`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` with 13 tests.
- No live AWS or PostgreSQL commands were run.

2026-09-02 local AWS profile follow-up:

- Created local-only `.env` with non-secret settings and `INFRA_AUDITOR_AWS_PROFILE=infra-auditor`.
- Verified the profile is logged in without recording account details in docs.
- `uv run infra-auditor collect --instance udb` reached RDS discovery successfully, then returned `PARTIAL_SUCCESS` because Secrets Manager credential resolution was denied.
- `uv run infra-auditor collect --instance raptor-catalog` reached RDS discovery successfully, then returned `PARTIAL_SUCCESS` because Secrets Manager credential resolution was denied.
- Local partial snapshots were written under gitignored `data/snapshots/`.

2026-09-02 Secrets Manager follow-up:

- Verified `infra-auditor` can read both configured Secrets Manager entries without printing secret values.
- At that time, both secret payloads included extra RDS-template fields: `engine`, `host`, `port`, `dbname`, and `dbInstanceIdentifier`.
- `uv run infra-auditor collect --instance udb` and `uv run infra-auditor collect --instance raptor-catalog` still return `PARTIAL_SUCCESS` because `PostgresCredentials` forbids those extra fields by design.

2026-09-02 successful live V0.1 collection:

- Rechecked both secret payload key sets; each contains only `username` and `password`.
- `uv run infra-auditor collect --instance udb` succeeded with 6 databases discovered and wrote `data/snapshots/0bbc9ceb-38dd-454c-bbc9-2a29b258d127/udb.json`.
- `uv run infra-auditor collect --instance raptor-catalog` succeeded with 12 databases discovered and wrote `data/snapshots/562af0a7-bc1a-4c90-9ea2-9cdab3e1721d/raptor-catalog.json`.
- No secret values were printed or recorded in project docs.

2026-09-02 PostgreSQL permission-boundary check:

- Used fixed catalog queries only; no application table rows were read.
- Both instances use `prj_rl_rds_auditor_prod`, connection limit `2`, read-only transaction settings, expected timeouts, and `application_name=infra-auditor`.
- Both instances have `pg_read_all_settings` and `pg_read_all_stats`; neither has `pg_monitor`, `pg_stat_scan_tables`, `pg_read_all_data`, `pg_write_all_data`, `pg_signal_backend`, or `rds_superuser`.
- Checked database-level `CREATE`; it was false on connectable databases.
- `udb`: `postgres` and `udb_airflow_metadata_db` were connectable; `unified_db_live` was not connectable.
- `raptor-catalog`: all non-template databases except `raptor_db` were connectable.
- No application table privileges were observed. The only selectable non-system relations were extension-owned `pg_stat_statements` views on selected `raptor-catalog` databases.

2026-09-03 S3 persistence implementation:

- Reviewed successful local snapshots and permission-boundary notes.
- Implemented `SYS_ENV` settings with allowed values `dev` and `prod`; unset
  defaults to `dev`.
- S3 snapshot bucket names derive from `SYS_ENV` as `infra-audit-rl-<SYS_ENV>`.
- Replaced active local JSON persistence with S3 JSON persistence using
  conditional `PutObject` and timestamp-based object names.
- Live S3 access inspection from the current narrow local identity returned
  `AccessDenied`, which is consistent with write-only permissions but means
  bucket posture was not verified from this profile.
- Live S3-backed collection succeeded for `udb` and wrote
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=udb/dt=2026-09-03/20260903T100426Z.json`.
- Live S3-backed collection succeeded for `raptor-catalog` and wrote
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=raptor-catalog/dt=2026-09-03/20260903T100426Z.json`.
- After the writes, the same identity still received `AccessDenied` for
  `ListBucket` on `raw/snapshots/` and `HeadObject` on both written snapshots;
  the observed runtime boundary is write-only from this profile.
- Local validation passed: `uv run infra-auditor config validate`,
  `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy src`, and `uv run pytest` with 17 tests.

2026-09-03 PostgreSQL security rules implementation:

- Added fixed-query PostgreSQL role-security evidence collection from
  `pg_roles` and `pg_auth_members`.
- Embedded deterministic findings in each instance snapshot.
- Implemented `SEC002` for login membership paths to `rds_superuser`.
- Implemented `SEC003` for direct login-to-login role membership.
- Refactored PostgreSQL collection to use one bootstrap database connection per
  instance run for database inventory and role security, preserving the
  connection-limit boundary.
- First live `raptor-catalog` run failed on `rolvaliduntil = infinity`; the
  role query now normalizes infinite timestamps to `null`.
- Live S3-backed collection succeeded for `raptor-catalog` and wrote
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=raptor-catalog/dt=2026-09-03/20260903T105332Z.json`.
- The successful `raptor-catalog` role-security evidence contained 59 roles and
  41 membership edges; deterministic findings were 3 `SEC002` and 8 `SEC003`.
- Live S3-backed collection for `udb` remained `PARTIAL_SUCCESS` because the
  bootstrap PostgreSQL connection timed out; AWS discovery, secret resolution,
  and S3 persistence still succeeded.
- Local validation passed after the role-security change:
  `uv run infra-auditor config validate`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` with
  23 tests.

2026-09-03 AWS/RDS operational collector implementation:

- Added read-only collectors for attached security group ingress, CloudWatch RDS
  metric summaries, RDS pending maintenance, RDS recommendations, DB parameter
  group parameters, and aggregated PostgreSQL activity metadata.
- Activity evidence intentionally excludes `pg_stat_activity.query` text.
- Added deterministic rules for `SEC001`, `CFG002`, `CFG009`, `OPS001`,
  `OPS003`, `OPS005`, `OPS007`, `OPS008`, `OPS012`, `OPS013`, `OPS014`, and
  `OPS015`.
- Local validation passed: `uv run infra-auditor config validate`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`,
  and `uv run pytest` with 29 tests.
- Live `raptor-catalog` collection wrote
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=raptor-catalog/dt=2026-09-03/20260903T114521Z.json`.
- That live run was `PARTIAL_SUCCESS`: RDS discovery, Secrets Manager,
  PostgreSQL database inventory, PostgreSQL activity summary, PostgreSQL role
  security, deterministic rules, and S3 persistence succeeded; the new AWS
  network/metric/ops collectors failed because the current identity lacks the
  read-only AWS permissions listed in Blockers.
- After the owner added the missing read-only AWS permissions and ran from the
  whitelisted network, live S3-backed collection succeeded for both configured
  instances.
- `raptor-catalog` success snapshot:
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=raptor-catalog/dt=2026-09-03/20260903T115827Z.json`;
  all collectors succeeded, 12 databases discovered, 22 findings.
- `udb` success snapshot:
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=udb/dt=2026-09-03/20260903T115839Z.json`;
  all collectors succeeded, 6 databases discovered, 12 findings.

2026-09-03 report/UI implementation:

- Added deterministic report models over raw snapshots, including severity
  counts, rule counts, collector summaries, selected RDS metrics, RDS operations,
  network exposure, PostgreSQL activity, and role/security inventory.
- Added S3 snapshot read helpers for listing latest snapshots and validating
  stored raw JSON as `AuditSnapshot`.
- Added `uv run infra-auditor serve`, backed by FastAPI/Uvicorn and configured
  through `INFRA_AUDITOR_WEB_HOST` and `INFRA_AUDITOR_WEB_PORT`; defaults are
  `127.0.0.1:8008`.
- Added a local Bootstrap dashboard with instance/snapshot selectors, report
  summary, findings table, collector table, raw JSON viewer, and controlled
  collect action.
- Local validation passed: `uv run infra-auditor config validate`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`,
  and `uv run pytest` with 32 tests.
- Live S3 read check from the current local identity returned `AccessDenied` for
  `ListBucket`; add the documented S3 read permissions before the UI can load
  existing snapshots.
- The local UI launched successfully at `http://127.0.0.1:8008`; `/healthz`
  returned `{"status":"ok"}` and `/` returned HTTP 200.

2026-09-04 service-aware report console refactor:

- Refactored the local UI into maintainable template/static assets under
  `src/infra_auditor/ui/templates` and `src/infra_auditor/ui/static`.
- Added a left-pane/right-pane report console with service selection, fleet
  overview, instance detail, snapshot history, raw JSON review, and export
  links.
- Made S3 snapshot reads service-aware so future raw snapshot splitting can keep
  the same partition style while avoiding reads of unrelated service data.
- Added fleet report models and Markdown export rendering.
- Added `POST /collect-all`, `/api/fleet-report`, `/exports/fleet.json`,
  `/exports/fleet.md`, `/exports/instance.json`, and `/exports/instance.md`.
- Added root `./run.sh` as the local central runner.
- Local validation passed: `bash -n run.sh`,
  `uv run infra-auditor config validate`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` with
  35 tests.
- Launched the report console through `./run.sh` at
  `http://127.0.0.1:8008`; `/healthz` returned OK, `/` and the instance detail
  view returned HTTP 200, and `/api/fleet-report?service=rds-postgres` loaded
  without S3 read errors.
- Exercised `POST /collect-all?service=rds-postgres` through the running UI.
  Fresh S3-backed collection succeeded for both configured instances and wrote:
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=raptor-catalog/dt=2026-09-04/20260904T061600Z.json`
  and
  `s3://infra-audit-rl-dev/raw/snapshots/snapshot_schema=1/env=dev/region=ap-south-1/service=rds-postgres/instance=udb/dt=2026-09-04/20260904T061607Z.json`.
- The fresh fleet report contains 2 instances, 33 total findings, 0 critical, 4
  high, 19 medium, 10 low, and no S3 read errors.

2026-09-04 service-section UI refactor:

- Reworked the UI shell so the left pane is navigation only: RDS, Postgres, AWS,
  Elasticsearch, Bitbucket, Reports, Raw Data, and a fixed Chat entry.
- Moved server, database, snapshot, severity, rule, export, and generate actions
  into right-pane control strips.
- Split the old instance/fleet UI into dedicated RDS, Postgres, Reports, Raw,
  planned-service, and Chat partials.
- RDS currently presents instance-level RDS/AWS evidence from the existing
  `rds-postgres` snapshots. Postgres presents database inventory,
  role/activity summaries, and Postgres-specific findings from the same raw
  snapshots.
- AWS, Elasticsearch, and Bitbucket are visible as planned sections without
  standalone collectors. Chat is a UI placeholder only; no LLM/MCP integration
  or external prompt flow has been added.
- Added a UI render unit test for the service navigation and RDS/Postgres/Chat
  right-pane views.
- Restarted the local report console through `./run.sh`; `/healthz`, RDS,
  Postgres, Reports, Raw Data, AWS placeholder, and Chat views all returned HTTP
  200 against S3-backed data.

2026-09-04 UI polish and async content loading:

- Added a border-mounted sidebar collapse/expand control. Expanded mode shows
  icon and text navigation; collapsed mode keeps the project logo and nav icons.
- Added a light/dark theme toggle in the project header and stores the selected
  theme in browser local storage.
- Updated CDN assets to Bootstrap `5.3.8` and Bootstrap Icons `1.13.1`.
- Changed the dashboard runtime flow so `/` returns the UI shell quickly and
  `/view` loads the selected S3-backed RDS/Postgres/Reports/Raw content behind a
  central loader.
- Added loader behavior for form submits so generate actions visibly enter a
  running state before redirecting back to the shell.
- Live verification: `/` returned HTTP 200 without waiting on S3-backed report
  reads; `/view` returned HTTP 200 for RDS, Postgres, Reports, Raw Data, and
  Chat.

2026-09-04 service/subservice raw artifacts and base MCP layer:

- Designed the first raw split boundary as eight service/subservice artifacts
  per instance run: `rds/instance`, `rds/operations`,
  `rds/ec2-security-groups`, `rds/cloudwatch-rds-metrics`,
  `postgres/database-inventory`, `postgres/activity-summary`,
  `postgres/role-security`, and
  `audit-heuristics/deterministic-findings`.
- Kept the full `service=rds-postgres` raw snapshot as the compatibility
  artifact for existing UI/report reads.
- Added `SnapshotSplitArtifact` models, service/subservice key/prefix builders,
  S3 split writes, and typed S3 split reads under
  `raw/snapshots/artifact_schema=...`.
- Added `uv run infra-auditor mcp` using the official MCP Python SDK v2
  (`mcp==2.1.1` resolved locally).
- Added `sync_latest_audit_data` and `sync_today_audit_data` as controlled MCP
  tools that call the existing read-only collector workflow for configured
  aliases and write immutable S3 audit artifacts. Today sync skips aliases that
  already have a full snapshot for the current UTC day.
- MCP tools are constrained to configured instances, latest/listed full
  snapshots, deterministic reports, filtered findings, latest/listed approved
  split artifacts, and controlled sync. No generic SQL, arbitrary AWS calls,
  arbitrary S3 key reads, secrets, query text, shell bridge, or remediation
  tools were added.
- Local validation passed: `uv run infra-auditor config validate`,
  `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy src`, `uv run pytest` with 41 tests, and
  `uv run infra-auditor --help` / `uv run infra-auditor mcp --help`.
- Local UI verification on `127.0.0.1:8009` returned HTTP 200 for `/`, RDS,
  AWS/EC2 planned placeholders, Raw Data full snapshot, Raw Data split
  selection, Reports, and Chat views.
- No live AWS or PostgreSQL collection was run in this implementation session.

2026-09-04 sync UX and domain cleanup:

- Corrected the local UI domain split: current CloudWatch RDS metrics and
  attached EC2 security group ingress are shown under RDS, not as standalone AWS
  or EC2 pages.
- Renamed the Postgres navigation/page label to Database (PG).
- Added the project version beside the UI title, sourced from package metadata
  derived from `pyproject.toml`.
- Added background UI sync jobs with status polling, per-alias
  collected/skipped/failed results, and visible `Sync this`, `Sync all`, and `Sync today`
  actions.
- Removed the old synchronous web collect endpoints; `uv run infra-auditor collect`
  remains the direct terminal collection path.
- Updated MCP with `sync_today_audit_data`; it skips collection when the latest
  configured full snapshot and all current split artifacts are already under the
  current UTC day.
- Added a gradual permission expansion plan for RDS metrics, Database (PG), AWS
  identity posture, IAM Identity Center, and EC2 fleet posture.
- Validation passed: `uv run ruff format .`, `uv run ruff check .`,
  `uv run mypy src`, `uv run pytest` with 43 tests,
  `uv run ruff format --check .`, `uv run infra-auditor config validate`,
  `uv run infra-auditor --help`, and `uv run infra-auditor mcp --help`.
- Restarted the local report console on `127.0.0.1:8009`; `/`, RDS, RDS
  metrics, Raw Data split selection, and the sync-job status API returned
  expected HTTP responses.

2026-08-26 local validation:

- `uv sync` passed.
- `uv run ruff check .` passed.
- `uv run ruff format --check .` passed.
- `uv run mypy src` passed.
- `uv run pytest` passed: 13 tests.
- `uv run infra-auditor config validate` passed: 2 configured instances, default region `ap-south-1`.

No live AWS or PostgreSQL collection was run in that bootstrap session.
