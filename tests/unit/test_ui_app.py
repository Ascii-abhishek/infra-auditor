from datetime import UTC, datetime
from typing import Any

from infra_auditor.collectors.postgres.discovery import DatabaseInfo, DatabaseKind
from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.models.common import CollectionStatus
from infra_auditor.models.snapshot import AuditSnapshot, InstanceSnapshot, RunMetadata
from infra_auditor.storage.s3_reader import S3SnapshotObject
from infra_auditor.ui.app import SECTION_SUBSERVICES, create_app


class FakeReader:
    def __init__(self) -> None:
        self.snapshot = AuditSnapshot(
            metadata=RunMetadata(
                run_id="run-1",
                environment="dev",
                region="ap-south-1",
                started_at=datetime(2026, 9, 4, 6, 0, tzinfo=UTC),
                completed_at=datetime(2026, 9, 4, 6, 1, tzinfo=UTC),
                status=CollectionStatus.SUCCESS,
            ),
            instances=[
                InstanceSnapshot(
                    alias="db",
                    db_instance_identifier="database-1",
                    region="ap-south-1",
                    status=CollectionStatus.SUCCESS,
                    databases=[
                        DatabaseInfo(
                            name="postgres",
                            allow_connections=True,
                            is_template=False,
                            kind=DatabaseKind.SYSTEM,
                            connection_eligible=True,
                        ),
                        DatabaseInfo(
                            name="app_db",
                            allow_connections=True,
                            is_template=False,
                            kind=DatabaseKind.APPLICATION,
                            connection_eligible=True,
                        ),
                    ],
                )
            ],
        )
        self.object = S3SnapshotObject(
            bucket="infra-audit-rl-dev",
            key=(
                "raw/snapshots/schema=2/env=dev/service=rds/region=ap-south-1/"
                "instance=db/subservice=instance/dt=2026-09-04/20260904T060000Z.json"
            ),
            uri=(
                "s3://infra-audit-rl-dev/raw/snapshots/schema=2/env=dev/service=rds/"
                "region=ap-south-1/instance=db/subservice=instance/dt=2026-09-04/"
                "20260904T060000Z.json"
            ),
            size_bytes=100,
            last_modified=datetime(2026, 9, 4, 6, 0, tzinfo=UTC),
        )

    def list_snapshots(self, **_kwargs: Any) -> list[S3SnapshotObject]:
        return [self.object]

    def list_artifacts(self, **_kwargs: Any) -> list[S3SnapshotObject]:
        return [self.object]

    def list_manifests(self, **_kwargs: Any) -> list[S3SnapshotObject]:
        return [self.object]

    def read_latest_snapshot(self, **_kwargs: Any) -> tuple[S3SnapshotObject, AuditSnapshot]:
        return self.object, self.snapshot

    def read_snapshot(self, _key: str) -> AuditSnapshot:
        return self.snapshot

    def read_snapshot_for_artifact(self, _key: str) -> AuditSnapshot:
        return self.snapshot

    def read_artifact(self, _key: str) -> object:
        return self.snapshot


def test_create_app_registers_dashboard_and_api_routes() -> None:
    resource_config = ResourceConfig.model_validate(
        {
            "version": 1,
            "aws": {"default_region": "ap-south-1"},
            "instances": {
                "db": {
                    "db_instance_identifier": "database-1",
                    "secret_id": "infra-auditor/postgres/db",
                }
            },
        }
    )

    app = create_app(
        settings=AppSettings(_env_file=None),
        resource_config=resource_config,
        reader=FakeReader(),
    )

    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/view" in paths
    assert "/sync-jobs" in paths
    assert "/api/sync-jobs/{job_id}" in paths
    assert "/api/fleet-report" in paths
    assert "/api/latest-report" in paths
    assert "/api/run" in paths
    assert "/api/runs" in paths
    assert "/exports/fleet.json" in paths
    assert "/exports/fleet.md" in paths


def test_dashboard_renders_service_nav_and_right_pane_views() -> None:
    app = create_app(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=FakeReader(),
    )
    dashboard = next(route.endpoint for route in app.routes if route.path == "/")
    dashboard_view = next(route.endpoint for route in app.routes if route.path == "/view")

    shell_response = dashboard(section="rds", instance="db")
    rds_response = dashboard_view(section="rds", instance="db")
    rds_metrics_response = dashboard_view(
        section="rds",
        instance="db",
        subservice="cloudwatch-rds-metrics",
    )
    postgres_response = dashboard_view(section="postgres", instance="db", database="app_db")
    aws_response = dashboard_view(section="aws", instance="db")
    ec2_response = dashboard_view(section="ec2", instance="db")
    chat_response = dashboard_view(section="chat")

    assert shell_response.status_code == 200
    shell_html = shell_response.body.decode("utf-8")
    assert "content-root" in shell_html
    assert "/static/app.js?v=" in shell_html
    assert "/static/app.css?v=" in shell_html
    assert '<div class="brand-title">Infra Auditor</div>' in shell_html
    assert "Database (PG)" in shell_html
    assert "EC2" in shell_html
    assert "CloudWatch" not in shell_html
    assert rds_response.status_code == 200
    rds_html = rds_response.body.decode("utf-8")
    assert "RDS Audit" in rds_html
    assert "Sync now" in rds_html
    assert "Sync today" not in rds_html
    assert "Sync all" not in rds_html
    assert "Sync all" in shell_html
    assert ">dev</span>" in shell_html
    assert "bi-bucket" in shell_html
    assert "infra-audit-rl-dev" in shell_html
    assert rds_html.index("Sync now") < rds_html.index('class="control-strip"')
    assert "select-loader-wrap" in rds_html
    assert rds_metrics_response.status_code == 200
    assert "CloudWatch RDS metric evidence" in rds_metrics_response.body.decode("utf-8")
    assert postgres_response.status_code == 200
    postgres_html = postgres_response.body.decode("utf-8")
    assert "Database (PG)" in postgres_html
    assert "app_db" in postgres_html
    assert aws_response.status_code == 200
    assert "AWS does not have a standalone collector yet" in aws_response.body.decode("utf-8")
    assert ec2_response.status_code == 200
    assert "EC2 does not have a standalone collector yet" in ec2_response.body.decode("utf-8")
    assert chat_response.status_code == 200
    chat_html = chat_response.body.decode("utf-8")
    assert "Audit Chat" in chat_html
    assert "New chat" in chat_html


def _resource_config() -> ResourceConfig:
    return ResourceConfig.model_validate(
        {
            "version": 1,
            "aws": {"default_region": "ap-south-1"},
            "instances": {
                "db": {
                    "db_instance_identifier": "database-1",
                    "secret_id": "infra-auditor/postgres/db",
                }
            },
        }
    )


def test_filter_history_is_scoped_and_stale_key_cannot_override_selection() -> None:
    import json

    class ScopedReader(FakeReader):
        def __init__(self) -> None:
            super().__init__()
            self.old = self.object.model_copy(
                update={
                    "key": self.object.key.replace("2026-09-04", "2026-09-03").replace(
                        "20260904T060000Z", "20260903T060000Z"
                    ),
                }
            )
            self.read_keys: list[str] = []

        def list_snapshots(self, **_kwargs: Any) -> list[S3SnapshotObject]:
            return [self.object, self.old]

        def list_artifacts(self, **kwargs: Any) -> list[S3SnapshotObject]:
            if kwargs["subservice"] == "operations":
                return [self.old]
            if kwargs["subservice"] == "role-security":
                return []
            return [self.object]

        def read_snapshot(self, key: str) -> AuditSnapshot:
            self.read_keys.append(key)
            return self.snapshot

        def read_snapshot_for_artifact(self, key: str) -> AuditSnapshot:
            self.read_keys.append(key)
            return self.snapshot

    reader = ScopedReader()
    app = create_app(
        settings=AppSettings(_env_file=None), resource_config=_resource_config(), reader=reader
    )
    options = next(r.endpoint for r in app.routes if r.path == "/api/filter-options")
    view = next(r.endpoint for r in app.routes if r.path == "/view")
    body = json.loads(
        options(instance="db", section="rds", subservice="operations", date="2026-09-04").body
    )
    assert body["dates"] == ["2026-09-03"]
    assert body["timestamps"] == ["20260903T060000Z"]
    empty = json.loads(options(instance="db", section="postgres", subservice="role-security").body)
    assert empty["dates"] == empty["timestamps"] == []
    assert options(instance="db", section="postgres", subservice="operations").status_code == 400
    assert options(instance="other", section="rds", subservice="instance").status_code == 404
    view(instance="db", section="rds", subservice="operations", key=reader.object.key)
    assert reader.read_keys == [reader.old.key]


def test_filter_options_support_every_section_subservice_and_server_pair() -> None:
    config = ResourceConfig.model_validate(
        {
            "version": 1,
            "aws": {"default_region": "ap-south-1"},
            "instances": {
                "db": {
                    "db_instance_identifier": "database-1",
                    "secret_id": "infra-auditor/postgres/db",
                },
                "db-two": {
                    "db_instance_identifier": "database-2",
                    "secret_id": "infra-auditor/postgres/db-two",
                },
            },
        }
    )
    app = create_app(
        settings=AppSettings(_env_file=None), resource_config=config, reader=FakeReader()
    )
    options = next(route.endpoint for route in app.routes if route.path == "/api/filter-options")

    for instance in config.instances:
        for section in ("rds", "postgres", "raw"):
            for subservice in SECTION_SUBSERVICES[section]:
                response = options(
                    instance=instance,
                    section=section,
                    subservice=subservice["id"],
                )
                assert response.status_code == 200
                assert response.headers["cache-control"] == "no-store"


def test_run_api_resolves_keys_only_from_the_configured_instance_listing() -> None:
    reader = FakeReader()
    app = create_app(
        settings=AppSettings(_env_file=None),
        resource_config=_resource_config(),
        reader=reader,
    )
    run_api = next(route.endpoint for route in app.routes if route.path == "/api/run")

    assert run_api(instance="db", key=reader.object.key).status_code == 200
    assert run_api(instance="db", key="private/unapproved.json").status_code == 404
    assert run_api(instance="other", key=reader.object.key).status_code == 404
