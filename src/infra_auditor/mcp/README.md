# MCP Layer

The base MCP server exists as a local stdio layer:

```bash
uv run infra-auditor mcp
```

It exposes approved snapshot/report reads for configured instances:

- `describe_audit_data_boundary`
- `list_audit_instances`
- `list_audit_snapshots`
- `get_latest_instance_report`
- `get_fleet_report`
- `get_instance_findings`
- `list_snapshot_split_artifacts`
- `get_latest_snapshot_split_artifact`
- `sync_latest_audit_data`
- `sync_today_audit_data`

Read tools query stored audit artifacts, not production databases directly.
`sync_latest_audit_data` may run the existing read-only collector workflow for
configured aliases and write immutable S3 artifacts. `sync_today_audit_data`
uses the same workflow but skips aliases that already have a full snapshot and
all current split artifacts for the current UTC day. A generic
`execute_sql(sql)` or `run_query(sql)` tool is explicitly out of bounds, as are
arbitrary AWS calls, arbitrary S3 key reads, secret reads, query text retrieval,
and remediation.
