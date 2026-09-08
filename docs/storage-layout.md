# S3 layout and report construction

Schema 3 separates observed facts, derived findings, and bookkeeping:

```text
s3://infra-audit-rl-<env>/
  raw/snapshots/schema=3/env=<env>/service=<rds|postgres>/region=<region>/instance=<alias>/subservice=<collector>/dt=<date>/<timestamp>.json
  reports/snapshots/schema=3/env=<env>/service=<rds|postgres>/region=<region>/instance=<alias>/subservice=deterministic-findings/dt=<date>/<timestamp>.json
  runs/schema=3/env=<env>/region=<region>/instance=<alias>/dt=<date>/<timestamp>.json
```

`raw/`, `reports/`, and `runs/` are sibling prefixes. Only RDS and PostgreSQL
appear as service partitions. S3 folders are key prefixes, not real directories.
Dates and timestamps are UTC. `run_id` and application/schema versions are also
stored in the JSON metadata.

Each instance run writes seven raw boundary artifacts, two service finding
artifacts, then one completion manifest. Disabled boundaries still have a small
artifact with explicit skipped status. This keeps a complete, fixed allowlisted
family even when configured coverage differs. Findings do not duplicate raw
evidence: they carry observed values and evidence references for their diagnosis.

The manifest references all nine artifacts and is written last. A completed
manifest can describe a partially successful collection; “complete” means storage
commit, not successful access to every source. Failure writing raw evidence or
findings prevents the completion marker. Conditional PutObject prevents overwrite;
there is no automatic orphan cleanup or deletion. Same-second collisions fail
rather than overwrite an earlier run.

For reports, readers validate the complete boundary set and recompute every key
from manifest identity before fetching references. They assemble the in-memory
snapshot, combine RDS/PostgreSQL findings, count severities/rules, sort findings,
and build instance/fleet summaries. These JSON/Markdown/UI summaries are generated
on demand; the persisted `reports/` objects contain full deterministic findings,
not cached HTML or a duplicated full snapshot. UI top findings are bounded; the
stored findings remain the complete rule output for that run.

Raw Data selects an individual evidence boundary; Reports displays derived
summaries. MCP may request approved service findings as `deterministic-findings`,
which resolves to `reports/`, never a caller-provided path. A standalone raw
artifact can exist from an uncommitted write; report assembly still requires its
manifest. Historical views retain their existing newest-50 listing limit.

## Cutover

The earlier `service=audit-heuristics` meant deterministic rule output;
`service=audit/subservice=run-manifest` meant bookkeeping. Neither was an audited
infrastructure service. Their removal changes the persisted family, so schema 3
is explicit instead of silently reinterpreting schema 2.

Schema-1 deletion and the prior commit were reported complete by the owner on
2026-09-08. Schema-2 objects are left untouched and are not listed by the schema-3
reader. Grant the new narrow prefixes, restart, run a fresh Sync all, and verify
both instances before considering any separate cleanup. No migration or bucket
deletion runs in this change. See the next-steps runbook for the exact sequence.

Future curated history, exports or analyst output should receive purpose-specific
sibling prefixes only when implemented, with separate schemas and access review.

## Relation to the service registry

Registry version 3 now follows `services → regions → instances`. S3 already uses
`service → region → instance → subservice`; this configuration change does not
change the artifact schema or paths again. The current run manifest commits a
paired RDS/PostgreSQL job, so its `runs/` key uses region/alias without a fictitious
service. Region and dependency rules are documented beside the YAML in
[config/README.md](../config/README.md).
