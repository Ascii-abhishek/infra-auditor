# Observability

## V1 Runtime Logs

The V1 runtime log destination is:

```text
application stdout/stderr -> ECS stdout -> CloudWatch Logs
```

Local runs default to console rendering. Production should use JSON rendering with:

```bash
INFRA_AUDITOR_LOG_FORMAT=json
```

## Required Context

Collection logs should include available safe context such as:

- run ID,
- service,
- environment,
- region,
- instance alias,
- DB instance identifier,
- database when applicable,
- collector,
- event,
- duration where useful,
- status.

## Redaction

Never log database passwords, Secrets Manager secret values, AWS access keys, connection strings with passwords, raw FDW secrets, full sensitive SQL, or bind values.

The logging setup redacts common key names such as password, secret, token, access key, connection URI, connection string, and DSN. This is defense-in-depth, not permission to pass secrets to logs.

## Future LLM Observability

Pydantic AI functionality is deferred. When it arrives, evaluate OpenTelemetry, Pydantic Logfire, or another OTLP backend for model/tool-call instrumentation. Do not couple deterministic collectors to Logfire in V1.
