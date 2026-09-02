# Decisions

This file is the chronological decision index. Use monotonically increasing IDs and keep `Status` current.

## DEC-0001 - Deterministic evidence first, LLM/MCP deferred

Date: 2026-08-26
Status: Accepted

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
