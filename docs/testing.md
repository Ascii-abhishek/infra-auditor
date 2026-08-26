# Testing

## Local Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Use formatting when needed:

```bash
uv run ruff format .
```

## Unit Tests

Unit tests must not require live AWS or PostgreSQL. Use fakes/stubs/fixtures for:

- RDS `DescribeDBInstances`,
- Secrets Manager `GetSecretValue`,
- PostgreSQL connection/cursor behavior,
- snapshot output paths.

## Integration Tests

Integration tests that touch real AWS/RDS must be explicitly marked:

```python
@pytest.mark.integration
```

Plain `pytest` must never accidentally touch production.

## Sensitive Test Data

Use fake secrets and fixture metadata only. Do not commit production snapshots, logs, AWS credentials, passwords, or private keys.
