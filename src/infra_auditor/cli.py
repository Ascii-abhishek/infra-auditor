"""Typer command-line interface."""

from pathlib import Path
from typing import Annotated

import structlog
import typer

from infra_auditor.collectors.aws.client import (
    create_boto3_session,
    create_rds_client,
)
from infra_auditor.collectors.aws.rds import RDSDiscovery
from infra_auditor.config import AppSettings, ResourceConfig, load_resource_config
from infra_auditor.exceptions import ConfigurationError, InfraAuditorError, SnapshotValidationError
from infra_auditor.logging import configure_logging
from infra_auditor.models.common import CollectionStatus
from infra_auditor.models.snapshot import InstanceSnapshot
from infra_auditor.ui.app import create_app
from infra_auditor.workflows import collect_and_write_instance

app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
discover_app = typer.Typer(no_args_is_help=True)

app.add_typer(config_app, name="config")
app.add_typer(discover_app, name="discover")

logger = structlog.get_logger(__name__)


@config_app.command("validate")
def validate_config(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to non-secret resource registry YAML."),
    ] = None,
) -> None:
    """Validate settings and the configured instance registry."""

    settings = AppSettings()
    configure_logging(settings.log_level, settings.log_format)
    resource_config = _load_config_or_exit(settings, config_path)
    typer.echo(
        f"OK: {len(resource_config.instances)} instance(s), "
        f"default region {resource_config.aws.default_region}"
    )


@discover_app.command("aws")
def discover_aws(
    instance: Annotated[
        str | None,
        typer.Option("--instance", help="Optional configured instance alias to discover."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to non-secret resource registry YAML."),
    ] = None,
) -> None:
    """Read RDS metadata for configured instances without touching PostgreSQL."""

    settings = AppSettings()
    configure_logging(settings.log_level, settings.log_format)
    resource_config = _load_config_or_exit(settings, config_path)
    aliases = [instance] if instance is not None else list(resource_config.instances)

    session = create_boto3_session(settings)
    failures = 0
    for alias in aliases:
        if alias not in resource_config.instances:
            typer.secho(f"Unknown instance alias: {alias}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        region = resource_config.region_for_instance(alias)
        discovery = RDSDiscovery(create_rds_client(session, region))
        try:
            rds_instance = discovery.describe_instance(
                alias=alias,
                config=resource_config.instances[alias],
                region=region,
            )
        except InfraAuditorError as exc:
            failures += 1
            logger.warning(
                "aws_discovery_failed", instance_alias=alias, error_type=type(exc).__name__
            )
            typer.secho(f"{alias}: FAILED ({exc})", fg=typer.colors.RED, err=True)
            continue

        endpoint = rds_instance.endpoint.address if rds_instance.endpoint else "unknown"
        typer.echo(
            f"{alias}: OK {rds_instance.identifier} "
            f"{rds_instance.engine or 'unknown'} {rds_instance.engine_version or 'unknown'} "
            f"endpoint={endpoint}"
        )

    if failures:
        raise typer.Exit(code=1)


@app.command("collect")
def collect(
    instance: Annotated[str, typer.Option("--instance", help="Configured instance alias.")],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to non-secret resource registry YAML."),
    ] = None,
) -> None:
    """Collect the V0.1 read-only snapshot for one configured RDS PostgreSQL instance."""

    settings = AppSettings()
    configure_logging(settings.log_level, settings.log_format)
    resource_config = _load_config_or_exit(settings, config_path)
    if instance not in resource_config.instances:
        typer.secho(f"Unknown instance alias: {instance}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        result = collect_and_write_instance(
            settings=settings,
            resource_config=resource_config,
            alias=instance,
        )
    except SnapshotValidationError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    snapshot = result.snapshot
    instance_snapshot = snapshot.instances[0]

    typer.echo(f"Run ID: {snapshot.metadata.run_id}")
    typer.echo(f"Instance: {instance_snapshot.alias}")
    typer.echo(
        f"AWS discovery: {_collector_status(instance_snapshot, 'aws.rds.describe_db_instances')}"
    )
    typer.echo(
        "AWS security groups: "
        f"{_collector_status(instance_snapshot, 'aws.ec2.security_group_ingress')}"
    )
    typer.echo(
        "CloudWatch RDS metrics: "
        f"{_collector_status(instance_snapshot, 'aws.cloudwatch.rds_metrics')}"
    )
    typer.echo(f"RDS operations: {_collector_status(instance_snapshot, 'aws.rds.operations')}")
    typer.echo(
        "PostgreSQL database inventory: "
        f"{_collector_status(instance_snapshot, 'postgres.database_inventory')}"
    )
    typer.echo(
        "PostgreSQL activity summary: "
        f"{_collector_status(instance_snapshot, 'postgres.activity_summary')}"
    )
    typer.echo(
        "PostgreSQL role security: "
        f"{_collector_status(instance_snapshot, 'postgres.role_security')}"
    )
    typer.echo(f"Databases discovered: {len(instance_snapshot.databases)}")
    typer.echo(f"Findings: {len(instance_snapshot.findings)}")
    typer.echo(f"Snapshot: {result.snapshot_uri}")
    typer.echo(f"Status: {snapshot.metadata.status}")

    if snapshot.metadata.status == CollectionStatus.FAILED:
        raise typer.Exit(code=1)


@app.command("serve")
def serve(
    host: Annotated[
        str | None,
        typer.Option("--host", help="Host for the local report UI."),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", help="Port for the local report UI."),
    ] = None,
) -> None:
    """Run the local FastAPI report UI."""

    import uvicorn

    settings = AppSettings()
    configure_logging(settings.log_level, settings.log_format)
    uvicorn.run(
        create_app(),
        host=host or settings.web_host,
        port=port or settings.web_port,
        log_level=settings.log_level.lower(),
    )


@app.command("mcp")
def mcp() -> None:
    """Run the MCP server over stdio."""

    from infra_auditor.mcp.server import main

    main()


def _load_config_or_exit(settings: AppSettings, config_path: Path | None) -> ResourceConfig:
    try:
        return load_resource_config(config_path or settings.resource_config_path)
    except ConfigurationError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


def _collector_status(snapshot: InstanceSnapshot, collector_name: str) -> str:
    for collector in snapshot.collectors:
        if collector.name == collector_name:
            return str(collector.status.value)
    return CollectionStatus.SKIPPED.value
