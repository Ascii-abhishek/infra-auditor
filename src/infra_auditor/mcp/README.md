# MCP Layer

The base MCP server exists as a local stdio layer:

```bash
uv run infra-auditor mcp
```

It exposes approved snapshot/report reads for configured instances:

- `describe_audit_data_boundary`
- `list_audit_instances`
- `list_audit_runs`
- `get_latest_instance_report`
- `get_fleet_report`
- `get_instance_findings`
- `list_audit_artifacts`
- `get_latest_audit_artifact`
- `sync_latest_audit_data`
- `sync_today_audit_data`

Read tools query stored audit artifacts, not production databases directly.
`sync_latest_audit_data` may run the existing read-only collector workflow for
configured aliases and write immutable S3 artifacts. `sync_today_audit_data`
uses the same workflow but skips aliases that already have a completed-run
manifest for the current UTC day. A generic
`execute_sql(sql)` or `run_query(sql)` tool is explicitly out of bounds, as are
arbitrary AWS calls, arbitrary S3 key reads, secret reads, query text retrieval,
and remediation.

Registry version 3 resolves service/region/instance targets and exposes effective service coverage in instance summaries.
Only RDS/PostgreSQL boundaries are approved. Schema 3 reads raw evidence from
`raw/`, deterministic findings from `reports/`, and completed-run manifests from
`runs/`. All three prefixes are fixed and constrained to the configured bucket,
environment, region and instance. Config changes need restart and a latest sync.
