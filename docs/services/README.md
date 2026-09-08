# Service coverage

The active product scope is PostgreSQL on AWS RDS. RDS describes the hosting
infrastructure; PostgreSQL describes the database engine. They share configured
instance aliases. AWS account posture, standalone EC2, Elasticsearch, and other
services are deferred until the deep PostgreSQL audit is validated.

- [RDS evidence and reports](rds.md)
- [PostgreSQL evidence and deeper audit plan](postgres.md)
- [Storage and reporting](../storage-layout.md)
- [Configuration](../configuration.md)
- [Practical next steps](../runbooks/postgres-next-steps.md)

Configuration selects reviewed capabilities. Adding an instance of an existing
service requires YAML and its secret reference. Adding a new service requires
an implemented adapter, typed evidence, safe credentials, tests, and registration
of approved boundaries. YAML must never name arbitrary Python imports, SQL,
AWS actions, filesystem paths, or S3 prefixes. The MCP interface uses common
instance/service/subservice arguments but validates them against implemented
capabilities. Future generic rendering can show new typed evidence; rich service
views still need implementation. No LLM is connected yet.

The current tree/reference is [config/README.md](../../config/README.md).
Targets group by service, region and instance; the code-owned adapter validates
explicit host dependencies. One shared login name across databases is sufficient;
its server-local group carries monitoring privileges. See the current manual SQL
runbook for the owner's `grp_rl_infra_auditor` / `prj_rl_infra_auditor` roles.
