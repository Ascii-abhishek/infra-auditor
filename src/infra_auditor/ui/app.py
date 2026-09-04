"""FastAPI app for the local infra-auditor control surface."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from infra_auditor.collectors.aws.client import create_boto3_session, create_s3_read_client
from infra_auditor.collectors.postgres.activity import ActivityGroup
from infra_auditor.config import AppSettings, ResourceConfig, load_resource_config
from infra_auditor.exceptions import InfraAuditorError
from infra_auditor.logging import configure_logging
from infra_auditor.models.finding import FindingSeverity
from infra_auditor.models.snapshot import InstanceSnapshot
from infra_auditor.models.snapshot_split import SnapshotSplitService, SnapshotSplitSubservice
from infra_auditor.reports import (
    build_fleet_report,
    build_snapshot_report,
    render_fleet_markdown,
    render_snapshot_markdown,
)
from infra_auditor.reports.models import (
    FindingReportItem,
    FleetReport,
    InstanceReport,
    SnapshotReport,
)
from infra_auditor.storage.s3_reader import S3SnapshotObject, S3SnapshotReader
from infra_auditor.sync import AuditSyncMode
from infra_auditor.ui.sync_jobs import UISyncJobManager

UI_DIR = Path(__file__).parent
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"
SNAPSHOT_SERVICES = ({"id": "rds-postgres", "label": "RDS PostgreSQL"},)
try:
    PROJECT_VERSION = version("infra-auditor")
except PackageNotFoundError:
    PROJECT_VERSION = "0.1.0"
NAV_ITEMS = (
    {
        "id": "rds",
        "label": "RDS",
        "icon": "bi-hdd-network",
        "href_extra": "instance",
        "state": "Live",
    },
    {
        "id": "postgres",
        "label": "Database (PG)",
        "icon": "bi-database",
        "href_extra": "instance",
        "state": "Live",
    },
    {
        "id": "aws",
        "label": "AWS",
        "icon": "bi-cloud",
        "href_extra": "",
        "state": "Planned",
    },
    {
        "id": "ec2",
        "label": "EC2",
        "icon": "bi-diagram-3",
        "href_extra": "",
        "state": "Planned",
    },
    {
        "id": "elasticsearch",
        "label": "Elasticsearch",
        "icon": "bi-search",
        "href_extra": "",
        "state": "Planned",
    },
    {
        "id": "bitbucket",
        "label": "Bitbucket",
        "icon": "bi-git",
        "href_extra": "",
        "state": "Planned",
    },
    {
        "id": "reports",
        "label": "Reports",
        "icon": "bi-clipboard-data",
        "href_extra": "",
        "state": "Live",
    },
    {
        "id": "raw",
        "label": "Raw Data",
        "icon": "bi-braces",
        "href_extra": "instance",
        "state": "Live",
    },
)
SUPPORTED_SECTIONS = {item["id"] for item in NAV_ITEMS} | {"chat"}
INSTANCE_SECTIONS = {"rds", "postgres", "raw"}
PLACEHOLDER_SECTIONS = {"aws", "ec2", "elasticsearch", "bitbucket"}
SEVERITY_OPTIONS = ("all", *(severity.value for severity in FindingSeverity))
SECTION_SUBSERVICES: dict[str, tuple[dict[str, str], ...]] = {
    "rds": (
        {"id": SnapshotSplitSubservice.RDS_INSTANCE.value, "label": "Overview"},
        {"id": SnapshotSplitSubservice.RDS_OPERATIONS.value, "label": "Operations"},
        {
            "id": SnapshotSplitSubservice.RDS_EC2_SECURITY_GROUPS.value,
            "label": "Security groups",
        },
        {
            "id": SnapshotSplitSubservice.RDS_CLOUDWATCH_METRICS.value,
            "label": "RDS metrics",
        },
    ),
    "postgres": (
        {
            "id": SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY.value,
            "label": "Database inventory",
        },
        {
            "id": SnapshotSplitSubservice.POSTGRES_ACTIVITY_SUMMARY.value,
            "label": "Activity summary",
        },
        {
            "id": SnapshotSplitSubservice.POSTGRES_ROLE_SECURITY.value,
            "label": "Role security",
        },
    ),
    "raw": (
        {"id": "full-snapshot", "label": "Full snapshot"},
        {"id": SnapshotSplitSubservice.RDS_INSTANCE.value, "label": "RDS instance"},
        {"id": SnapshotSplitSubservice.RDS_OPERATIONS.value, "label": "RDS operations"},
        {
            "id": SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY.value,
            "label": "Postgres inventory",
        },
        {
            "id": SnapshotSplitSubservice.POSTGRES_ACTIVITY_SUMMARY.value,
            "label": "Postgres activity",
        },
        {
            "id": SnapshotSplitSubservice.POSTGRES_ROLE_SECURITY.value,
            "label": "Postgres roles",
        },
        {
            "id": SnapshotSplitSubservice.RDS_EC2_SECURITY_GROUPS.value,
            "label": "RDS security groups",
        },
        {
            "id": SnapshotSplitSubservice.RDS_CLOUDWATCH_METRICS.value,
            "label": "RDS metrics",
        },
        {
            "id": SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS.value,
            "label": "Deterministic findings",
        },
    ),
}
RAW_SPLIT_SUBSERVICE_SERVICES: dict[str, SnapshotSplitService] = {
    SnapshotSplitSubservice.RDS_INSTANCE.value: SnapshotSplitService.RDS,
    SnapshotSplitSubservice.RDS_OPERATIONS.value: SnapshotSplitService.RDS,
    SnapshotSplitSubservice.POSTGRES_DATABASE_INVENTORY.value: SnapshotSplitService.POSTGRES,
    SnapshotSplitSubservice.POSTGRES_ACTIVITY_SUMMARY.value: SnapshotSplitService.POSTGRES,
    SnapshotSplitSubservice.POSTGRES_ROLE_SECURITY.value: SnapshotSplitService.POSTGRES,
    SnapshotSplitSubservice.RDS_EC2_SECURITY_GROUPS.value: SnapshotSplitService.RDS,
    SnapshotSplitSubservice.RDS_CLOUDWATCH_METRICS.value: SnapshotSplitService.RDS,
    SnapshotSplitSubservice.AUDIT_DETERMINISTIC_FINDINGS.value: (
        SnapshotSplitService.AUDIT_HEURISTICS
    ),
}


@dataclass(frozen=True)
class FleetFinding:
    """Finding row with instance context for the fleet table."""

    instance_alias: str
    finding: FindingReportItem


@dataclass(frozen=True)
class SnapshotChoice:
    """UI-friendly snapshot history option."""

    key: str
    label: str
    date: str
    timestamp: str


def create_app(
    *,
    settings: AppSettings | None = None,
    resource_config: ResourceConfig | None = None,
    reader: S3SnapshotReader | None = None,
) -> FastAPI:
    """Create the local FastAPI UI application."""

    settings = settings or AppSettings()
    configure_logging(settings.log_level, settings.log_format)
    resource_config = resource_config or load_resource_config(settings.resource_config_path)
    if reader is None:
        session = create_boto3_session(settings)
        reader = S3SnapshotReader(
            create_s3_read_client(session, settings.aws_region),
            settings.snapshot_bucket,
        )

    app = FastAPI(title="Infra Auditor", docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    template_env = _template_environment()
    sync_jobs = UISyncJobManager(
        settings=settings,
        resource_config=resource_config,
        reader=reader,
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(
        service: Annotated[str | None, Query()] = None,
        section: Annotated[str | None, Query()] = None,
        view: Annotated[str | None, Query()] = None,
        instance: Annotated[str | None, Query()] = None,
        database: Annotated[str | None, Query()] = None,
        subservice: Annotated[str | None, Query()] = None,
        date: Annotated[str | None, Query()] = None,
        timestamp: Annotated[str | None, Query()] = None,
        key: Annotated[str | None, Query()] = None,
        severity: Annotated[str | None, Query()] = None,
        rule: Annotated[str | None, Query()] = None,
        new_chat: Annotated[bool, Query()] = False,
        notice: Annotated[str | None, Query()] = None,
        error_message: Annotated[str | None, Query(alias="error")] = None,
    ) -> HTMLResponse:
        aliases = list(resource_config.instances)
        selected_service = _selected_snapshot_service(service)
        selected_service_label = _snapshot_service_label(selected_service)
        selected_section = _selected_section(section, legacy_view=view)
        selected_instance = _selected_instance(instance, aliases)
        selected_subservice = _selected_subservice(selected_section, subservice)
        content_url = _content_url(
            service=selected_service,
            section=selected_section,
            instance=selected_instance,
            database=database,
            subservice=selected_subservice,
            date=date,
            timestamp=timestamp,
            key=key,
            severity=severity,
            rule=rule,
            new_chat=new_chat,
            notice=notice,
            error=error_message,
        )
        html = template_env.get_template("dashboard.html").render(
            aliases=aliases,
            nav_items=NAV_ITEMS,
            selected_service=selected_service,
            selected_service_label=selected_service_label,
            section=selected_section,
            section_label=_section_label(selected_section),
            selected_instance=selected_instance,
            selected_subservice=selected_subservice,
            content_url=content_url,
            settings=settings,
            project_version=PROJECT_VERSION,
        )
        return HTMLResponse(html)

    @app.get("/view", response_class=HTMLResponse)
    def dashboard_view(
        service: Annotated[str | None, Query()] = None,
        section: Annotated[str | None, Query()] = None,
        view: Annotated[str | None, Query()] = None,
        instance: Annotated[str | None, Query()] = None,
        database: Annotated[str | None, Query()] = None,
        subservice: Annotated[str | None, Query()] = None,
        date: Annotated[str | None, Query()] = None,
        timestamp: Annotated[str | None, Query()] = None,
        key: Annotated[str | None, Query()] = None,
        severity: Annotated[str | None, Query()] = None,
        rule: Annotated[str | None, Query()] = None,
        new_chat: Annotated[bool, Query()] = False,
        notice: Annotated[str | None, Query()] = None,
        error_message: Annotated[str | None, Query(alias="error")] = None,
    ) -> HTMLResponse:
        aliases = list(resource_config.instances)
        selected_service = _selected_snapshot_service(service)
        selected_service_label = _snapshot_service_label(selected_service)
        selected_section = _selected_section(section, legacy_view=view)
        selected_instance = _selected_instance(instance, aliases)
        selected_database = database or "all"
        selected_subservice = _selected_subservice(selected_section, subservice)
        selected_severity = _selected_severity(severity)
        selected_rule = rule or "all"
        selected_key = key
        selected_date = date
        selected_timestamp = timestamp
        snapshots: list[S3SnapshotObject] = []
        snapshot_choices: list[SnapshotChoice] = []
        date_options: list[str] = []
        timestamp_options: list[str] = []
        fleet_report: FleetReport | None = None
        fleet_errors: dict[str, str] = {}
        fleet_findings: list[FleetFinding] = []
        report: SnapshotReport | None = None
        instance_snapshot: InstanceSnapshot | None = None
        raw_snapshot_json: str | None = None
        raw_source_uri: str | None = None
        database_names: list[str] = []
        postgres_activity_groups: list[ActivityGroup] = []
        error: str | None = error_message

        try:
            if selected_section not in PLACEHOLDER_SECTIONS | {"chat"}:
                fleet_report, fleet_errors = _load_fleet_report(
                    settings=settings,
                    resource_config=resource_config,
                    reader=reader,
                    service=selected_service,
                )
            if selected_section in INSTANCE_SECTIONS:
                region = resource_config.region_for_instance(selected_instance)
                if selected_section == "raw" and selected_subservice != "full-snapshot":
                    split_service = _raw_split_service_for_subservice(selected_subservice)
                    split_subservice = SnapshotSplitSubservice(selected_subservice)
                    snapshots = [
                        *reader.list_snapshot_split_artifacts(
                            environment=settings.environment,
                            region=region,
                            service=split_service,
                            subservice=split_subservice,
                            instance_alias=selected_instance,
                        )
                    ]
                else:
                    snapshots = reader.list_snapshots(
                        environment=settings.environment,
                        region=region,
                        service=selected_service,
                        instance_alias=selected_instance,
                    )
                snapshot_choices = _snapshot_choices(snapshots)
                key_choice = _snapshot_choice_for_key(snapshot_choices, selected_key)
                if key_choice is not None:
                    selected_date = selected_date or key_choice.date
                    selected_timestamp = selected_timestamp or key_choice.timestamp
                date_options = _date_options(snapshot_choices)
                selected_date = _selected_date(selected_date, date_options)
                timestamp_options = _timestamp_options(snapshot_choices, selected_date)
                selected_timestamp = _selected_timestamp(
                    selected_timestamp,
                    timestamp_options,
                )
                selected_key = selected_key or _selected_snapshot_key(
                    snapshot_choices,
                    selected_date=selected_date,
                    selected_timestamp=selected_timestamp,
                )
                if selected_key is not None:
                    raw_source_uri = f"s3://{settings.snapshot_bucket}/{selected_key}"
                    if selected_section == "raw" and selected_subservice != "full-snapshot":
                        artifact = reader.read_snapshot_split_artifact(selected_key)
                        raw_snapshot_json = json.dumps(
                            artifact.model_dump(mode="json"),
                            indent=2,
                        )
                    else:
                        snapshot = reader.read_snapshot(selected_key)
                        report = build_snapshot_report(
                            snapshot,
                            source_uri=raw_source_uri,
                            top_findings_limit=100,
                        )
                        instance_snapshot = snapshot.instances[0] if snapshot.instances else None
                        database_names = _database_names(instance_snapshot)
                        selected_database = _selected_database(selected_database, database_names)
                        postgres_activity_groups = _postgres_activity_groups(
                            instance_snapshot,
                            selected_database=selected_database,
                        )
                        if selected_section == "raw":
                            raw_snapshot_json = json.dumps(
                                snapshot.model_dump(mode="json"),
                                indent=2,
                            )
            fleet_findings = _fleet_findings(
                fleet_report,
                severity=selected_severity,
                rule=selected_rule,
            )
        except InfraAuditorError as exc:
            error = str(exc)

        instance_report = _first_instance_report(report)
        rds_findings = _section_findings(instance_report, "rds")
        postgres_findings = _section_findings(instance_report, "postgres")
        rule_options = _rule_options(fleet_report)
        html = template_env.get_template("partials/content.html").render(
            aliases=aliases,
            nav_items=NAV_ITEMS,
            snapshot_services=SNAPSHOT_SERVICES,
            selected_service=selected_service,
            selected_service_label=selected_service_label,
            section=selected_section,
            section_label=_section_label(selected_section),
            selected_instance=selected_instance,
            selected_database=selected_database,
            selected_subservice=selected_subservice,
            selected_subservice_label=_subservice_label(selected_section, selected_subservice),
            subservice_options=_subservice_options(selected_section),
            selected_date=selected_date,
            selected_timestamp=selected_timestamp,
            date_options=date_options,
            timestamp_options=timestamp_options,
            selected_severity=selected_severity,
            selected_rule=selected_rule,
            selected_key=selected_key,
            snapshots=snapshots,
            database_names=database_names,
            fleet_report=fleet_report,
            fleet_errors=fleet_errors,
            fleet_findings=fleet_findings,
            report=report,
            instance_report=instance_report,
            instance_snapshot=instance_snapshot,
            rds_findings=rds_findings,
            postgres_findings=postgres_findings,
            postgres_activity_groups=postgres_activity_groups,
            severity_options=SEVERITY_OPTIONS,
            rule_options=rule_options,
            raw_snapshot_json=raw_snapshot_json,
            raw_source_uri=raw_source_uri,
            new_chat=new_chat,
            notice=notice,
            error=error,
            settings=settings,
            project_version=PROJECT_VERSION,
            num=_format_number,
            yn=_format_bool,
        )
        return HTMLResponse(html)

    @app.post("/sync-jobs")
    def start_sync_job(
        mode: Annotated[str | None, Query()] = None,
        target: Annotated[str | None, Query()] = None,
        instance: Annotated[str | None, Query()] = None,
        service: Annotated[str | None, Query()] = None,
        section: Annotated[str | None, Query()] = None,
        database: Annotated[str | None, Query()] = None,
        subservice: Annotated[str | None, Query()] = None,
    ) -> JSONResponse:
        selected_mode = _selected_sync_mode(mode)
        selected_target = "instance" if target == "instance" else "all"
        instance_alias = instance if selected_target == "instance" else None
        if instance_alias is not None and instance_alias not in resource_config.instances:
            return JSONResponse({"error": f"unknown instance: {instance_alias}"}, status_code=404)

        selected_service = _selected_snapshot_service(service)
        selected_section = _selected_section(section)
        selected_instance = _selected_instance(instance, list(resource_config.instances))
        selected_subservice = _selected_subservice(selected_section, subservice)
        job = sync_jobs.start(instance_alias=instance_alias, mode=selected_mode)
        refresh_url = _content_url(
            service=selected_service,
            section=selected_section,
            instance=selected_instance,
            database=database,
            subservice=selected_subservice,
            date=None,
            timestamp=None,
            key=None,
            severity=None,
            rule=None,
            new_chat=False,
            notice=f"Sync job {job.job_id} finished",
            error=None,
        )
        return JSONResponse(
            {
                "job": job.model_dump(mode="json"),
                "status_url": f"/api/sync-jobs/{job.job_id}",
                "refresh_url": refresh_url,
            },
            status_code=202,
        )

    @app.get("/api/sync-jobs/{job_id}")
    def api_sync_job(job_id: str) -> JSONResponse:
        job = sync_jobs.get(job_id)
        if job is None:
            return JSONResponse({"error": f"unknown sync job: {job_id}"}, status_code=404)
        return JSONResponse(job.model_dump(mode="json"))

    @app.get("/api/snapshots")
    def api_snapshots(
        instance: Annotated[str, Query()],
        service: Annotated[str | None, Query()] = None,
    ) -> JSONResponse:
        if instance not in resource_config.instances:
            return JSONResponse({"error": f"unknown instance: {instance}"}, status_code=404)
        region = resource_config.region_for_instance(instance)
        try:
            objects = reader.list_snapshots(
                environment=settings.environment,
                region=region,
                service=_selected_snapshot_service(service),
                instance_alias=instance,
            )
        except InfraAuditorError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        return JSONResponse([item.model_dump(mode="json") for item in objects])

    @app.get("/api/latest-report")
    def api_latest_report(
        instance: Annotated[str, Query()],
        service: Annotated[str | None, Query()] = None,
    ) -> JSONResponse:
        if instance not in resource_config.instances:
            return JSONResponse({"error": f"unknown instance: {instance}"}, status_code=404)
        region = resource_config.region_for_instance(instance)
        try:
            item, snapshot = reader.read_latest_snapshot(
                environment=settings.environment,
                region=region,
                service=_selected_snapshot_service(service),
                instance_alias=instance,
            )
            report = build_snapshot_report(snapshot, source_uri=item.uri, top_findings_limit=100)
        except InfraAuditorError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        return JSONResponse(report.model_dump(mode="json"))

    @app.get("/api/fleet-report")
    def api_fleet_report(service: Annotated[str | None, Query()] = None) -> JSONResponse:
        try:
            fleet_report, fleet_errors = _load_fleet_report(
                settings=settings,
                resource_config=resource_config,
                reader=reader,
                service=_selected_snapshot_service(service),
            )
        except InfraAuditorError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        return JSONResponse(
            {
                "report": fleet_report.model_dump(mode="json") if fleet_report else None,
                "errors": fleet_errors,
            }
        )

    @app.get("/api/snapshot")
    def api_snapshot(key: Annotated[str, Query()]) -> JSONResponse:
        try:
            snapshot = reader.read_snapshot(key)
        except InfraAuditorError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        return JSONResponse(snapshot.model_dump(mode="json"))

    @app.get("/exports/fleet.json")
    def export_fleet_json(service: Annotated[str | None, Query()] = None) -> JSONResponse:
        fleet_report, fleet_errors = _load_fleet_report(
            settings=settings,
            resource_config=resource_config,
            reader=reader,
            service=_selected_snapshot_service(service),
        )
        return JSONResponse(
            {
                "report": fleet_report.model_dump(mode="json") if fleet_report else None,
                "errors": fleet_errors,
            }
        )

    @app.get("/exports/fleet.md")
    def export_fleet_markdown(service: Annotated[str | None, Query()] = None) -> PlainTextResponse:
        fleet_report, fleet_errors = _load_fleet_report(
            settings=settings,
            resource_config=resource_config,
            reader=reader,
            service=_selected_snapshot_service(service),
        )
        if fleet_report is None:
            body = "# Infra Auditor Fleet Report\n\nNo snapshots loaded.\n"
        else:
            body = render_fleet_markdown(fleet_report)
        if fleet_errors:
            body += "\n## Load Errors\n\n"
            for alias, message in fleet_errors.items():
                body += f"- `{alias}`: {message}\n"
        return PlainTextResponse(body, media_type="text/markdown")

    @app.get("/exports/instance.json")
    def export_instance_json(key: Annotated[str, Query()]) -> JSONResponse:
        try:
            snapshot = reader.read_snapshot(key)
            report = build_snapshot_report(
                snapshot,
                source_uri=f"s3://{settings.snapshot_bucket}/{key}",
                top_findings_limit=100,
            )
        except InfraAuditorError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        return JSONResponse(report.model_dump(mode="json"))

    @app.get("/exports/instance.md")
    def export_instance_markdown(key: Annotated[str, Query()]) -> PlainTextResponse:
        try:
            snapshot = reader.read_snapshot(key)
            report = build_snapshot_report(
                snapshot,
                source_uri=f"s3://{settings.snapshot_bucket}/{key}",
                top_findings_limit=100,
            )
        except InfraAuditorError as exc:
            return PlainTextResponse(str(exc), status_code=500)
        return PlainTextResponse(render_snapshot_markdown(report), media_type="text/markdown")

    return app


def _template_environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    environment.filters["dt"] = _format_datetime
    return environment


def _load_fleet_report(
    *,
    settings: AppSettings,
    resource_config: ResourceConfig,
    reader: S3SnapshotReader,
    service: str,
) -> tuple[FleetReport | None, dict[str, str]]:
    reports: list[SnapshotReport] = []
    errors: dict[str, str] = {}
    for alias in resource_config.instances:
        region = resource_config.region_for_instance(alias)
        try:
            item, snapshot = reader.read_latest_snapshot(
                environment=settings.environment,
                region=region,
                service=service,
                instance_alias=alias,
            )
        except InfraAuditorError as exc:
            errors[alias] = str(exc)
            continue
        reports.append(build_snapshot_report(snapshot, source_uri=item.uri, top_findings_limit=100))

    if not reports:
        return None, errors
    return (
        build_fleet_report(
            reports,
            service=service,
            environment=settings.environment,
            region=settings.aws_region,
        ),
        errors,
    )


def _fleet_findings(
    report: FleetReport | None,
    *,
    severity: str,
    rule: str,
) -> list[FleetFinding]:
    if report is None:
        return []
    findings: list[FleetFinding] = []
    for snapshot in report.snapshots:
        for instance in snapshot.instances:
            for finding in instance.top_findings:
                if severity != "all" and finding.severity.value != severity:
                    continue
                if rule != "all" and finding.rule_id != rule:
                    continue
                findings.append(FleetFinding(instance_alias=instance.alias, finding=finding))
    return findings[:30]


def _selected_snapshot_service(candidate: str | None) -> str:
    service_ids = {service["id"] for service in SNAPSHOT_SERVICES}
    if candidate in service_ids:
        return candidate
    return SNAPSHOT_SERVICES[0]["id"]


def _selected_sync_mode(candidate: str | None) -> AuditSyncMode:
    if candidate == AuditSyncMode.TODAY.value:
        return AuditSyncMode.TODAY
    return AuditSyncMode.LATEST


def _snapshot_service_label(service_id: str) -> str:
    for service in SNAPSHOT_SERVICES:
        if service["id"] == service_id:
            return service["label"]
    return service_id


def _selected_section(candidate: str | None, legacy_view: str | None = None) -> str:
    if candidate in SUPPORTED_SECTIONS:
        return candidate
    if legacy_view == "fleet":
        return "reports"
    if legacy_view == "instance":
        return "rds"
    return "rds"


def _section_label(section_id: str) -> str:
    if section_id == "chat":
        return "Audit Chat"
    for item in NAV_ITEMS:
        if item["id"] == section_id:
            return item["label"]
    return section_id


def _selected_instance(candidate: str | None, aliases: list[str]) -> str:
    if candidate in aliases:
        return candidate
    if not aliases:
        raise ValueError("no configured instances")
    return aliases[0]


def _first_instance_report(report: SnapshotReport | None) -> InstanceReport | None:
    if report is None or not report.instances:
        return None
    return report.instances[0]


def _database_names(snapshot: InstanceSnapshot | None) -> list[str]:
    if snapshot is None:
        return []
    return [database.name for database in snapshot.databases]


def _selected_database(candidate: str, database_names: list[str]) -> str:
    if candidate == "all" or candidate in database_names:
        return candidate
    return "all"


def _postgres_activity_groups(
    snapshot: InstanceSnapshot | None,
    *,
    selected_database: str,
) -> list[ActivityGroup]:
    if snapshot is None or snapshot.postgres_activity is None:
        return []
    groups = snapshot.postgres_activity.groups
    if selected_database != "all":
        groups = [group for group in groups if group.database_name == selected_database]
    return groups[:25]


def _section_findings(
    report: InstanceReport | None,
    section: str,
) -> list[FindingReportItem]:
    if report is None:
        return []
    if section == "rds":
        return [
            finding
            for finding in report.top_findings
            if "aws/rds" in finding.category or "/rds" in finding.resource
        ]
    if section == "postgres":
        return [
            finding
            for finding in report.top_findings
            if "postgres" in finding.category or "/postgres" in finding.resource
        ]
    return list(report.top_findings)


def _rule_options(report: FleetReport | None) -> list[str]:
    if report is None:
        return []
    rules = {
        finding.rule_id
        for snapshot in report.snapshots
        for instance in snapshot.instances
        for finding in instance.top_findings
    }
    return sorted(rules)


def _subservice_options(section: str) -> tuple[dict[str, str], ...]:
    return SECTION_SUBSERVICES.get(section, ())


def _selected_subservice(section: str, candidate: str | None) -> str:
    options = _subservice_options(section)
    option_ids = {option["id"] for option in options}
    if candidate in option_ids:
        return candidate
    if options:
        return options[0]["id"]
    return ""


def _subservice_label(section: str, subservice: str) -> str:
    for option in _subservice_options(section):
        if option["id"] == subservice:
            return option["label"]
    return subservice or "All"


def _raw_split_service_for_subservice(subservice: str) -> SnapshotSplitService:
    return RAW_SPLIT_SUBSERVICE_SERVICES[subservice]


def _snapshot_choices(objects: Sequence[S3SnapshotObject]) -> list[SnapshotChoice]:
    return [
        SnapshotChoice(
            key=item.key,
            label=f"{_snapshot_date(item.key)} / {_snapshot_timestamp(item.key)}",
            date=_snapshot_date(item.key),
            timestamp=_snapshot_timestamp(item.key),
        )
        for item in objects
    ]


def _snapshot_choice_for_key(
    choices: list[SnapshotChoice],
    key: str | None,
) -> SnapshotChoice | None:
    if key is None:
        return None
    for choice in choices:
        if choice.key == key:
            return choice
    return None


def _date_options(choices: list[SnapshotChoice]) -> list[str]:
    return sorted({choice.date for choice in choices if choice.date}, reverse=True)


def _selected_date(candidate: str | None, options: list[str]) -> str | None:
    if candidate in options:
        return candidate
    return options[0] if options else None


def _timestamp_options(
    choices: list[SnapshotChoice],
    selected_date: str | None,
) -> list[str]:
    return [
        choice.timestamp
        for choice in choices
        if selected_date is None or choice.date == selected_date
    ]


def _selected_timestamp(candidate: str | None, options: list[str]) -> str | None:
    if candidate in options:
        return candidate
    return options[0] if options else None


def _selected_snapshot_key(
    choices: list[SnapshotChoice],
    *,
    selected_date: str | None,
    selected_timestamp: str | None,
) -> str | None:
    for choice in choices:
        if selected_date is not None and choice.date != selected_date:
            continue
        if selected_timestamp is not None and choice.timestamp != selected_timestamp:
            continue
        return choice.key
    return choices[0].key if choices else None


def _snapshot_date(key: str) -> str:
    for part in key.split("/"):
        if part.startswith("dt="):
            return part.removeprefix("dt=")
    return ""


def _snapshot_timestamp(key: str) -> str:
    filename = key.rsplit("/", 1)[-1]
    return filename.removesuffix(".json")


def _selected_severity(candidate: str | None) -> str:
    if candidate in SEVERITY_OPTIONS:
        return candidate
    return "all"


def _content_url(
    *,
    service: str,
    section: str,
    instance: str,
    database: str | None,
    subservice: str,
    date: str | None,
    timestamp: str | None,
    key: str | None,
    severity: str | None,
    rule: str | None,
    new_chat: bool,
    notice: str | None,
    error: str | None,
) -> str:
    params = {
        "service": service,
        "section": section,
        "instance": instance,
    }
    if database:
        params["database"] = database
    if subservice:
        params["subservice"] = subservice
    if date:
        params["date"] = date
    if timestamp:
        params["timestamp"] = timestamp
    if key:
        params["key"] = key
    if severity:
        params["severity"] = severity
    if rule:
        params["rule"] = rule
    if new_chat:
        params["new_chat"] = "true"
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    return f"/view?{urlencode(params)}"


def _format_datetime(value: object) -> str:
    if value is None:
        return "unknown"
    return str(value)


def _format_number(value: object, suffix: str) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value}{suffix}"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"
