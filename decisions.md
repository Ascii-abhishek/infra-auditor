# Decisions

This file is the chronological decision index. Use monotonically increasing IDs and keep `Status` current.

## DEC-0001 - Deterministic evidence first, LLM/MCP deferred

Date: 2026-08-26
Status: Superseded by DEC-0010

### Scope / Module
architecture, collectors, rules, llm, mcp

### Decision
Build V1 as a deterministic evidence collection and audit foundation before adding LLM or MCP access.

### Rationale / Why
Production safety and evidence traceability are the core value. LLMs may help explain and investigate later, but they must not define both evidence selection and interpretation without deterministic constraints.

### Alternatives considered
- Start with an MCP server.
- Start with an LLM agent that queries production directly.

### Trade-offs & constraints
Early functionality is narrower, but the security model and data contracts are clearer.

### Security implications
No production credentials or arbitrary SQL path is exposed to an LLM.

### Operational implications
Operators can run and inspect deterministic snapshots before any AI-facing layer exists.

### Future reconsideration trigger
When normalized evidence and deterministic findings are mature enough to support a constrained LLM analyst.

## DEC-0002 - Locked V1 security boundaries

Date: 2026-08-26
Status: Accepted

### Scope / Module
security, collectors, llm, mcp, remediation

### Decision
V1 enforces these locked boundaries: no production credentials to LLMs, no generic SQL MCP tool, no automatic remediation, read-only collectors, no application table rows, and query text minimization.

### Rationale / Why
The auditor must not create a larger production risk than the risks it detects.

### Alternatives considered
- Read-only generic SQL for LLMs.
- Auto-remediation for obvious findings.
- Collecting broad query text by default.

### Trade-offs & constraints
Some investigations remain manual. Safety and auditability take priority.

### Security implications
Limits blast radius from model mistakes, prompt injection, leaked secrets, and accidental destructive operations.

### Operational implications
All initial production interactions are read-only and evidence-focused.

### Future reconsideration trigger
Only after an explicit owner-approved remediation or query-text redaction design exists.

## DEC-0003 - V1 Python stack and packaging

Date: 2026-08-26
Status: Accepted

### Scope / Module
pyproject, packaging, developer tooling

### Decision
Use Python 3.12+, uv, Pydantic v2, pydantic-settings, psycopg 3, boto3, Typer, structlog, tenacity, PyArrow, Jinja2, pytest, pytest-cov, Ruff, mypy, PyYAML, and Hatchling for the `src/` package build backend.

### Rationale / Why
The core stack was locked by the bootstrap brief. PyYAML is required to safely parse the human-managed YAML registry. Hatchling provides the minimal build backend needed for the `infra-auditor` console script with `uv run`.

### Alternatives considered
- Plain scripts without package installation.
- setuptools as build backend.
- JSON-only resource configuration.

### Trade-offs & constraints
Hatchling and PyYAML add small dependencies. The result is easier CLI execution and friendlier human configuration.

### Security implications
YAML is read through `yaml.safe_load`; secrets are forbidden from YAML.

### Operational implications
Developers use `uv sync`, `uv run infra-auditor ...`, and the lockfile for repeatable setup.

### Future reconsideration trigger
If packaging or safe YAML parsing requirements materially change.

## DEC-0004 - Settings and resource registry split

Date: 2026-08-26
Status: Accepted

### Scope / Module
config

### Decision
Use `INFRA_AUDITOR_` Pydantic Settings for process settings and a validated YAML registry for non-secret audit targets.

### Rationale / Why
Settings describe how the process runs; the registry describes what resources should be audited. Live infrastructure metadata comes from AWS discovery.

### Alternatives considered
- Put everything in environment variables.
- Put endpoints and infrastructure metadata in YAML.
- Put credentials in `.env`.

### Trade-offs & constraints
There are two configuration sources to understand, but the secret and live-state boundaries remain clean.

### Security implications
YAML and `.env.example` contain no credentials, endpoints, AWS account IDs, VPC IDs, subnet IDs, security group IDs, or capacity facts.

### Operational implications
Production can rely on ECS environment configuration, task IAM role, and Secrets Manager.

### Future reconsideration trigger
When multi-account or policy configuration becomes a real implemented requirement.

## DEC-0005 - Secrets Manager per instance for V1 database credentials

Date: 2026-08-26
Status: Accepted

### Scope / Module
secrets, collectors/postgres

### Decision
Resolve PostgreSQL credentials from AWS Secrets Manager using one configured secret ID per RDS instance. Expected shape is `{"username": "...", "password": "..."}`.

### Rationale / Why
This keeps production passwords out of repo config and matches the locked V1 authentication direction.

### Alternatives considered
- IAM database authentication.
- Environment variable passwords.
- Local credential files.

### Trade-offs & constraints
Password rotation remains a separate operational concern. IAM auth may be better later but is not required for V1.

### Security implications
Secret values are validated but not logged or persisted.

### Operational implications
The owner must create the read-only Secrets Manager secrets before live collection.

### Future reconsideration trigger
When IAM database authentication is evaluated for production collectors.

## DEC-0006 - CloudWatch Logs as V1 runtime log destination

Date: 2026-08-26
Status: Accepted

### Scope / Module
observability, logging

### Decision
Emit structured logs to stdout/stderr. Local runs can use console output; production should use JSON logs collected by ECS into CloudWatch Logs.

### Rationale / Why
CloudWatch Logs fits the expected AWS runtime and avoids coupling deterministic collectors to another observability SaaS.

### Alternatives considered
- Add Logfire immediately.
- Add another logging SaaS immediately.
- Use only pretty CLI output.

### Trade-offs & constraints
LLM/tool-call tracing is deferred. Operational logs still exist from the beginning.

### Security implications
Logging includes conservative redaction for keys such as password, secret, token, access key, connection URI, DSN, and connection string.

### Operational implications
Future ECS tasks can stream JSON logs to CloudWatch Logs without changing collector code.

### Future reconsideration trigger
When Pydantic AI/LLM functionality arrives and OpenTelemetry/Logfire/OTLP backend choices are evaluated.

## DEC-0007 - Local JSON snapshots first; historical lake deferred

Date: 2026-08-26
Status: Accepted

### Scope / Module
storage, snapshots, roadmap

### Decision
V0.1 writes local JSON snapshots under gitignored `data/snapshots/`. S3, Parquet, Glue Catalog, Athena, and DynamoDB latest-state cache are deferred.

### Rationale / Why
The first safe milestone is to inspect one full snapshot locally before adding infrastructure persistence.

### Alternatives considered
- Start with S3/Parquet/Athena.
- Create another PostgreSQL database for audit history.

### Trade-offs & constraints
No historical query layer exists yet. Local snapshots may still contain operationally sensitive metadata.

### Security implications
`data/` is gitignored; snapshots must not be committed.

### Operational implications
Developers can validate behavior before deploying AWS storage infrastructure.

### Future reconsideration trigger
When real snapshots are validated and daily/weekly retention requirements are defined.

## DEC-0008 - Partial failure is evidence

Date: 2026-08-26
Status: Accepted

### Scope / Module
runtime, collectors, snapshots

### Decision
Runs preserve collector statuses and collection gaps. If AWS discovery succeeds but a later sub-check fails, the snapshot is `PARTIAL_SUCCESS` instead of discarding useful evidence.

### Rationale / Why
Operational audits must show what could not be collected and why.

### Alternatives considered
- Fail the whole run on the first sub-check failure.
- Hide failed collectors from the snapshot.

### Trade-offs & constraints
Consumers must understand partial snapshots. The benefit is stronger operational truthfulness.

### Security implications
Gap messages must stay sanitized and avoid secret material.

### Operational implications
One unreachable database or missing permission does not erase AWS evidence for the instance.

### Future reconsideration trigger
If snapshot consumers require stricter fail-fast semantics for a particular workflow.

## DEC-0009 - Temporary AWS identities and separated runtime roles

Date: 2026-09-02
Status: Accepted

### Scope / Module
aws, identity, local development, ecs, scheduler, ci-cd

### Decision
Use temporary AWS credentials for humans and workloads. Local development should
prefer IAM Identity Center with a project-specific `InfraAuditorDeveloper`
permission set and an optional `infra-auditor-dev` AWS profile. Application code
continues to use boto3's standard credential/provider chain.

Future production will use separate roles:

- ECS task role for `infra-auditor` application AWS permissions.
- ECS task execution role for ECS/Fargate image pull, logging, and execution
  operations.
- EventBridge Scheduler execution role for starting the approved ECS task and
  passing only approved ECS roles.
- GitHub Actions OIDC deployment role for future CI/CD.

### Rationale / Why
AWS documentation supports IAM Identity Center and SDK credential providers for
short-term local credentials. ECS documentation separates application task
permissions from ECS execution permissions. EventBridge scheduled ECS tasks need
their own execution role when running tasks and passing roles.

### Alternatives considered
- Long-lived IAM user and access keys for local development.
- Requiring a hard-coded local AWS profile in production.
- Placing application AWS permissions in the ECS task execution role.
- Giving the application task role scheduler permissions.
- GitHub Actions access keys for future CI/CD.

### Trade-offs & constraints
Initial setup requires IAM Identity Center and permission-set administration.
The payoff is clearer least privilege and no normal project workflow based on
long-lived AWS access keys.

### Security implications
No AWS access keys are stored in `.env` files as the normal auth mechanism.
Developer, runtime, execution, scheduler, and future CI/CD permissions remain
separate so each principal has a narrow blast radius.

### Operational implications
Local runs use `aws sso login --profile infra-auditor-dev` and then
`AWS_PROFILE=infra-auditor-dev uv run infra-auditor ...`, or an optional
non-secret `INFRA_AUDITOR_AWS_PROFILE`. Production ECS tasks rely on task-role
credentials supplied by AWS.

### Future reconsideration trigger
If IAM Identity Center is unavailable or unsuitable for the AWS organization, or
if a future deployment target other than ECS Fargate becomes the approved
runtime.

## DEC-0010 - S3 raw JSON snapshots with SYS_ENV-derived buckets

Date: 2026-09-03
Status: Accepted

### Scope / Module
config, storage, cli, snapshots, aws

### Decision
Use `SYS_ENV` as the deployment environment selector with allowed values `dev`
and `prod`; default to `dev` when unset. Persist raw JSON snapshots only to S3,
using buckets named `infra-audit-rl-<SYS_ENV>`.

Snapshot keys use this partition-friendly shape:

```text
raw/snapshots/snapshot_schema=<version>/env=<SYS_ENV>/region=<region>/service=rds-postgres/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

### Rationale / Why
The project is an auditor with no write/remediation workflow, so a simple
dev/prod split is enough for now and keeps team conventions in place for future
MCP or broader access scopes. S3 gives immediate durable persistence without
adding local file state or a database.

### Alternatives considered
- Keep local JSON as the active writer.
- Add a configurable `local|s3|both` storage mode.
- Include full run IDs in S3 object filenames.

### Trade-offs & constraints
Timestamp-only object names are simpler but rely on conditional writes to reject
same-second collisions. The full run ID remains inside the snapshot body and S3
object metadata.

### Security implications
Snapshots include operational infrastructure metadata such as endpoints, ARNs,
VPC IDs, subnet IDs, and security group IDs, but not credentials or secret
values. Runtime writers need only `s3:PutObject` to the approved
`raw/snapshots/*` prefix and should not receive `s3:GetObject`,
`s3:ListBucket`, or `s3:DeleteObject` for normal collection.

### Operational implications
Local development defaults to `SYS_ENV=dev` and writes to
`infra-audit-rl-dev`. Production systems must set `SYS_ENV=prod` and write to
`infra-audit-rl-prod`.

### Future reconsideration trigger
When Parquet/Glue/Athena, cross-account access, Object Lock, retention rules, or
MCP-facing audit-data reads are implemented.

## DEC-0011 - Embed first deterministic PostgreSQL security findings in snapshots

Date: 2026-09-03
Status: Accepted

### Scope / Module
collectors/postgres, rules, models, snapshots

### Decision
Collect PostgreSQL role security evidence with fixed catalog queries against
`pg_roles` and `pg_auth_members`, then embed deterministic findings in the same
per-instance snapshot JSON. The first implemented rules are:

- `SEC002`: login role has a membership path to `rds_superuser`.
- `SEC003`: login role is directly a member of another login role.

### Rationale / Why
These rules convert known manual review findings into repeatable,
evidence-referenced audit output. Keeping findings embedded in the same JSON
keeps V0.1 simple and makes S3 snapshots immediately useful before adding a
separate report artifact or database.

### Alternatives considered
- Store findings as separate S3 objects immediately.
- Build MCP read APIs before deterministic rules exist.
- Query live PostgreSQL from MCP or an LLM directly.

### Trade-offs & constraints
Snapshot JSON will grow as evidence and findings expand. That is acceptable for
the current instance count and can be split by category later if needed.

### Security implications
No application table rows, PostgreSQL passwords, generic SQL API, unrestricted
query text, or remediation path is added. Role names and memberships are
operationally sensitive and remain private audit evidence in S3.

### Operational implications
The CLI now prints a finding count after collection. Full finding details live
inside the S3 snapshot for future reporting and MCP read APIs.

### Future reconsideration trigger
When findings become large enough to require category-specific objects, a latest
finding index, Parquet history, or MCP-facing read optimization.

## DEC-0012 - Keep RDS operational evidence in the per-instance snapshot

Date: 2026-09-03
Status: Accepted

### Scope / Module
collectors/aws, collectors/postgres, rules, models, snapshots

### Decision
For V0.1, collect broad read-only RDS operational evidence into the same
per-instance JSON snapshot: attached security group ingress, bounded CloudWatch
RDS metric summaries, pending maintenance, RDS recommendations, DB parameter
group parameters, and aggregated PostgreSQL activity metadata without query
text.

### Rationale / Why
The project needs useful audit output before building MCP/reporting layers.
Keeping one JSON object per instance keeps the first consumer simple and lets
rules and later analysts reason from a consistent evidence bundle.

### Alternatives considered
- Split raw evidence by metric category immediately.
- Query AWS/PostgreSQL live from MCP on demand.
- Defer performance and network evidence until after reports exist.

### Trade-offs & constraints
Snapshot JSON will grow. That is acceptable for the current instance count; if
size or consumption becomes awkward, evidence can split by category while
preserving the same schema-versioned S3 prefix model.

### Security implications
The implementation adds read-only AWS APIs and fixed PostgreSQL SQL only. It
does not add AWS mutating permissions, generic SQL execution, application table
reads, unrestricted query text, or remediation.

### Operational implications
Missing IAM permissions or network access produce collection gaps and
`PARTIAL_SUCCESS` snapshots rather than losing all evidence.

### Future reconsideration trigger
When Parquet/Athena history, MCP data reads, Performance Insights, or
category-specific report artifacts are implemented.

## DEC-0013 - Report model first, local FastAPI UI before MCP

Date: 2026-09-03
Status: Accepted

### Scope / Module
reports, storage, ui, cli, mcp

### Decision
Add deterministic report models over raw S3 snapshots, then serve them through
a localhost-bound FastAPI/Bootstrap UI. MCP remains deferred until the report
shape is useful and stable.

### Rationale / Why
Reports give a single human control surface for validating evidence, findings,
raw JSON, and collector behavior before exposing the same data to agents. The
report model becomes the reusable reader-facing contract for UI, CLI, and later
MCP tools.

### Alternatives considered
- Build MCP before a human report surface.
- Build a frontend framework application immediately.
- Keep reports as ad hoc JSON transformations inside the UI.

### Trade-offs & constraints
FastAPI and Uvicorn add runtime dependencies. The UI stays intentionally small,
server-rendered, and internal so the dependency and security surface remains
modest.

### Security implications
The UI may list/read S3 snapshots and trigger the existing read-only collection
workflow. It must not expose arbitrary SQL, arbitrary AWS API calls, secret
values, application rows, or remediation actions. Binding beyond localhost needs
an approved authentication and network-access design.

### Operational implications
Local UI defaults to `127.0.0.1:8008` through Pydantic settings. The UI/report
identity needs S3 `ListBucket`/`GetObject` for snapshot reads in addition to the
collector's existing `PutObject` permission.

### Future reconsideration trigger
When authentication, multi-user access, MCP production exposure, SES reports,
or hosted deployment requirements are designed.

## DEC-0014 - Service-aware report console and central local runner

Date: 2026-09-04
Status: Accepted

### Scope / Module
reports, storage, ui, scripts, docs

### Decision
Keep the first UI as a small server-rendered FastAPI/Bootstrap report console,
but organize it as maintainable HTML, CSS, and JavaScript files. Add a
service-aware S3 reader path and fleet report model so the console can show a
service-level overview, instance-level detail, snapshot history, raw JSON, and
JSON/Markdown exports. Add root `run.sh` as the local central runner.

### Rationale / Why
The owner expects raw snapshots to split by service soon. Making the reader and
UI service-aware now preserves the existing partition shape and lets the UI
fetch only the service/instance data currently being inspected. A simple
server-rendered console gives a practical review surface before MCP/LLM layers
are connected.

### Alternatives considered
- Keep a single inline HTML template inside Python.
- Build a full frontend framework application immediately.
- Build MCP first and rely on an agent as the only review surface.

### Trade-offs & constraints
The UI remains intentionally local/internal and modest. It does not yet provide
authentication, background job orchestration, report history comparisons, or
multi-service collectors beyond the implemented `rds-postgres` partition.

### Security implications
No new mutation path is added. The console may trigger the existing read-only
collector workflow and may read S3 snapshots for reporting. It must still avoid
generic SQL, arbitrary AWS calls, secrets, application table rows, unrestricted
query text, and remediation.

### Operational implications
`./run.sh` checks Python 3.12+, ensures `uv`, warns when AWS CLI is absent,
runs `uv sync`, loads `.env`, and starts the configured web host/port. The
report identity still needs S3 `ListBucket`/`GetObject`; pure collector
identities can remain write-only.

### Future reconsideration trigger
When the console needs background job state, authentication, multi-user hosting,
service comparison tables, or production deployment behind an approved access
boundary.

## DEC-0015 - Separate UI sections before splitting raw snapshot artifacts

Date: 2026-09-04
Status: Accepted

### Scope / Module
ui, reports, storage, mcp

### Decision
Represent RDS and Postgres as separate product sections in the report console
before physically splitting the raw JSON artifacts. RDS presents
instance/server-level evidence such as public access, storage, CPU, memory,
connections, maintenance, recommendations, and parameter groups. Postgres
presents within-database audit evidence such as database inventory, role
security, and activity summaries. Keep AWS, Elasticsearch, and Bitbucket visible
as planned sections, and keep Chat as an inert placeholder until MCP/LLM
integration is designed.

### Rationale / Why
The owner wants the product to feel like a service audit hub, while the current
collector still produces one consistent `rds-postgres` evidence bundle. Splitting
the UI first clarifies the target user experience and helps identify the cleanest
raw artifact boundaries before storage contracts change.

### Alternatives considered
- Split raw snapshots before the UI proves which sections need separate reads.
- Keep RDS and Postgres combined in one instance page.
- Add a real LLM chat surface before MCP tools and prompt boundaries exist.

### Trade-offs & constraints
The UI now has planned sections that do not yet have collectors. RDS and
Postgres are report slices over the same raw snapshot for now, so storage split
work still needs a deliberate data-contract pass.

### Security implications
No new data access or mutation boundary is added. Chat remains disabled and does
not send audit evidence to an LLM. Future chat must call approved MCP/data tools
over snapshots and reports, not arbitrary SQL, shell commands, or AWS APIs.

### Operational implications
The local report console remains the review surface for validating what data is
useful before implementing raw snapshot splits and MCP endpoints.

### Future reconsideration trigger
When raw artifacts split by service/category, or when a real authenticated
MCP/LLM chat workflow is introduced.

## DEC-0016 - Lightweight UI shell with async report content

Date: 2026-09-04
Status: Accepted

### Scope / Module
ui, reports, runtime

### Decision
Render the report console shell from `/` without reading S3, then load the
selected S3-backed section through `/view` in the browser. Add a visible loader,
sidebar collapse/expand preference, and light/dark theme preference stored in
browser local storage. Pin the CDN UI assets to Bootstrap `5.3.8` and Bootstrap
Icons `1.13.1`.

### Rationale / Why
S3 reads and local AWS token loading can delay first paint. Returning the shell
first gives immediate UI feedback while preserving the existing server-rendered
templates and avoiding a frontend framework.

### Alternatives considered
- Keep `/` blocking on all S3/report reads.
- Add a frontend framework and client-side router.
- Cache latest report data locally before the raw snapshot split is designed.

### Trade-offs & constraints
The async content route improves perceived load time but does not make S3 reads
faster. The first version reloads the shell on navigation instead of maintaining
a client-side router.

### Security implications
`/view` is a rendering endpoint over existing report/snapshot data. It must not
grow into arbitrary AWS, shell, SQL, or remediation execution.

### Operational implications
Slow AWS/S3 access now appears as a loader in the UI. Browser-only preferences
do not affect runtime settings or snapshot content.

### Future reconsideration trigger
When background job state, server-side report caching, auth, or multi-user
hosting is implemented.

## DEC-0017 - Split raw S3 artifacts and add constrained MCP tools

Date: 2026-09-04
Status: Accepted

### Scope / Module
storage, models, reports, mcp, cli, docs

### Decision
Keep writing the full compatibility snapshot under
`raw/snapshots/.../service=rds-postgres/...`, and additionally write split raw
artifacts under the same approved root with service/subservice partitions:

```text
raw/snapshots/artifact_schema=<version>/snapshot_schema=<version>/env=<SYS_ENV>/region=<region>/service=<service>/subservice=<subservice>/instance=<alias>/dt=<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json
```

Current split artifacts are `rds/instance`, `rds/operations`,
`rds/ec2-security-groups`, `rds/cloudwatch-rds-metrics`,
`postgres/database-inventory`, `postgres/activity-summary`,
`postgres/role-security`, and
`audit-heuristics/deterministic-findings`.

Add a local stdio MCP server through `uv run infra-auditor mcp`, using the
official Python MCP SDK v2 package (`mcp>=2,<3`). The first tools expose only
configured instance summaries, full snapshot listings, latest deterministic
instance/fleet reports, filtered finding summaries, split artifact listings,
latest split artifacts, `sync_latest_audit_data`, and
`sync_today_audit_data`, which run the existing read-only collector workflow
for configured aliases and write immutable S3 audit artifacts. The today sync
mode skips aliases that already have a full snapshot and all current split
artifacts for the current UTC day.

### Rationale / Why
The UI refactor proved the first useful product boundaries: RDS, PostgreSQL,
and deterministic audit heuristics/findings. RDS-attached EC2 security group
ingress and CloudWatch RDS metrics are RDS subservices in the current product,
not standalone AWS or EC2 inventory. Writing split artifacts now makes those
boundaries durable without breaking the existing report console, which can
still read the full compatibility snapshot.

MCP is useful once reports exist because agents can now read stable deterministic
contracts instead of touching live systems. The official SDK provides typed
tool schemas, structured output validation, read-only tool annotations, and
stdio transport support. A controlled sync tool is useful for chat workflows
that should reason over the latest data, but it remains constrained to the
existing collector workflow and configured aliases.

### Alternatives considered
- Replace the full snapshot with split artifacts immediately.
- Build MCP tools over live PostgreSQL or AWS checks.
- Expose a generic S3 key reader to MCP clients.
- Let MCP hosts submit arbitrary AWS or SQL checks.
- Implement the MCP protocol by hand.

### Trade-offs & constraints
Collection now writes nine S3 objects per instance run: one compatibility
snapshot and eight split artifacts. This is acceptable at current scale and
keeps the migration reversible. Split artifacts duplicate run metadata from the
full snapshot so each object remains self-describing.

### Security implications
No generic SQL, arbitrary AWS calls, arbitrary S3 key reads, query text,
secret values, application table rows, or remediation paths are added. MCP tools
use configured instance aliases and fixed service/subservice choices to derive
S3 read prefixes. `sync_latest_audit_data` and `sync_today_audit_data` read
live systems only through the existing collector workflow and never accept SQL
text, AWS action names, secret IDs, or remediation instructions.

### Follow-up adjustment
On 2026-09-04, the local UI was corrected so AWS and EC2 are planned
standalone domains instead of live peers for RDS-adjacent evidence. The
PostgreSQL view was renamed to Database (PG), and the UI/MCP sync flow gained
an explicit today mode for daily collection without duplicate same-day runs.

### Operational implications
Writers still need `s3:PutObject` for `raw/snapshots/*`. MCP/report identities
need `s3:ListBucket` and `s3:GetObject` for the same approved prefix. The MCP
command is a local stdio server, not a hosted HTTP service.

### Future reconsideration trigger
When the UI/report path reads split artifacts directly, when report caching or
latest-state indexes are added, or when hosted/authenticated MCP exposure is
designed.
