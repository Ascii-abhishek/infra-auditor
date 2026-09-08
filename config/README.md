# Environment registry

`environments.yaml` is the active non-secret audit registry. Its current syntax is
**registry version 3**. `SYS_ENV=dev|prod` selects the runtime environment/bucket;
this file lists targets. Select another file with
`INFRA_AUDITOR_RESOURCE_CONFIG_PATH`. `.yaml` and `.yml` both parse, but the
repository's actual filename and default are `config/environments.yaml`.

## Tree and identity

```text
version: 3
services
  <service>
    subservices: [service defaults]
    regions
      <region>
        instances
          <alias>
            <service-specific target fields>
            subservices: [optional instance replacement]
```

The pattern is shared across services. Fields and dependencies belong to reviewed
service adapters in code. The registry loader validates the tree and resolves an
execution plan; YAML cannot load arbitrary code or invent a collector.

A target's conceptual identity is `(service, region, alias)`. The current CLI,
UI and MCP select collection jobs by alias, so aliases **must be unique across
regions within a service**. PostgreSQL on RDS currently runs as one paired job:
its RDS and PostgreSQL entries must use the same alias and region. Validation
rejects ambiguity and mismatched dependencies rather than picking one silently.
This is an explicit current adapter constraint, not a universal rule for future
services. Independent adapters or duplicate-alias selectors need code changes.

Each region explicitly contains its instances; adding an additional region does
not change existing instances. A region has an AWS-style identifier such as
`ap-south-1`, `eu-west-1`, or `us-gov-west-1`; validation checks syntax, not AWS
availability or your authorization. Aliases use 2–63 lowercase letters/digits/
hyphens, starting with a letter. Unsupported global/non-regional services remain
future work; `global` is not accepted by today's regional adapter.

## Supported service fields

| Service | Instance fields | Meaning |
| --- | --- | --- |
| `rds` | `db_instance_identifier` required | Existing AWS RDS identifier; endpoint, version and capacity are discovered |
| `postgres` | `depends_on` required | An explicit host reference containing `service: rds`, `region`, and `instance` |
| `postgres` | `secret_id` required when enabled | Secrets Manager reference in that region; never the secret value |
| Either | `subservices` optional | Replaces this instance's service default list, including an explicit empty PG list |

RDS entries cannot carry PostgreSQL secrets or dependencies. PostgreSQL entries
cannot duplicate the RDS identifier. No credentials, usernames, passwords,
endpoints, infrastructure capacity, SQL, or executable paths belong in this YAML.
The PostgreSQL login username comes from the referenced secret.

## Exact subservice strings

Names are case-sensitive. The authoritative enum/catalog is
[`capabilities.py`](../src/infra_auditor/capabilities.py); validation, execution
selection and artifact service names share those definitions.

| Service | String | Evidence | Dependency |
| --- | --- | --- | --- |
| `rds` | `instance` | Current RDS metadata, endpoint and attached resource identifiers | Mandatory for each configured RDS host |
| `rds` | `operations` | Maintenance, recommendations, parameter values | Same host's `rds/instance` |
| `rds` | `ec2-security-groups` | Attached security group ingress | Same host's `rds/instance`; not standalone EC2 |
| `rds` | `cloudwatch-rds-metrics` | Bounded RDS metric summaries | Same host's `rds/instance`; not generic CloudWatch |
| `postgres` | `database-inventory` | Database names/classification | Referenced `rds/instance`, Secrets Manager and TLS PG connection |
| `postgres` | `activity-summary` | Aggregated connection/state/wait/age metadata | Same host, credentials and connection |
| `postgres` | `role-security` | Role attributes and membership edges | Same host, credentials and connection |

`deterministic-findings` is a supported **report artifact name** for both services,
but cannot appear in a collector selection. Rules run over whatever evidence was
collected. It is not a service, an external collector, or a YAML policy.

There are no aliases such as `hardware-health`, `security`, `tables`, `indexes`,
`overview`, `all`, or `*`. Elasticsearch and other service types are not yet
implemented. Misspellings, duplicates, unknown keys and wrong-service subservices
fail validation. A collector being disabled means **not checked by configuration**,
not healthy and not a collector error.

## Supported variations

**Inheritance:** omit an instance's `subservices` to inherit its service defaults.
Specify a list to replace only that instance's selection; other instances and the
other service retain their selections. Explicit `null` also inherits; prefer omission.

**RDS-only:** omit a PostgreSQL target entirely, or put `subservices: []` on it.
The runtime skips credentials and PG connections. RDS needs `[instance]` at minimum.
A PostgreSQL service may also set `subservices: []` as its global default.

**More regions/instances:** add another region beneath each relevant service, then
add the matching PostgreSQL reference. For example, alongside existing regions:

```yaml
# Under services.rds.regions:
eu-west-1:
  instances:
    reporting-eu:
      db_instance_identifier: reporting-postgres
      subservices: [instance, cloudwatch-rds-metrics]

# Under services.postgres.regions:
eu-west-1:
  instances:
    reporting-eu:
      depends_on:
        service: rds
        region: eu-west-1
        instance: reporting-eu
      secret_id: infra-auditor/postgres/reporting-eu
      subservices: [database-inventory, role-security]
```

These fragments illustrate placement, not a runnable complete registry. The
application can collect targets across regions using region-bound AWS clients;
credentials stay with the target's region. AWS profile/identity and the S3 bucket
remain runtime settings shared by the process. Multi-account/provider selection
and independent per-subservice schedules are not implemented.

## Storage pattern

The S3 layout already uses service, region, instance and subservice in that order:

```text
raw/snapshots/schema=3/env=<env>/service=<service>/region=<region>/instance=<alias>/subservice=<name>/dt=<date>/<timestamp>.json
reports/snapshots/schema=3/env=<env>/service=<service>/region=<region>/instance=<alias>/subservice=deterministic-findings/dt=<date>/<timestamp>.json
runs/schema=3/env=<env>/region=<region>/instance=<alias>/dt=<date>/<timestamp>.json
```

The `runs/` manifest has no service partition because it commits the paired
RDS/PostgreSQL job. It references every raw/report object and is written last.
That guarantees a stored family is complete; individual collectors may still
have failed, with their gaps recorded. See [storage details](../docs/storage-layout.md).
The YAML registry version and stored artifact schema are separate version numbers;
this tree change does not change the schema-3 S3 layout again.

## Apply changes

Run `uv run infra-auditor config validate` to see each alias's effective region
and coverage. Restart UI/MCP after editing, then use latest/Sync all; today sync
does not detect configuration changes. The UI/MCP consume the resolved plan and
retain historical disabled-boundary data. Older registry versions 1/2 remain
readable for existing local files; use this version-3 tree for new configuration.

A future adapter must register its service, subservices, credential/provider
boundary, evidence schema, dependency validation, collectors and tests. Generic
raw navigation and MCP boundary discovery use the registered definitions; rich
service reports still need service-specific implementation. Adding an existing
service's target is configuration-only; adding a service type is not.
