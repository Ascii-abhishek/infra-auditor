from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from infra_auditor.collectors.aws.models import RDSEndpoint, RDSInstance
from infra_auditor.collectors.postgres.discovery import DatabaseDiscoveryCollector
from infra_auditor.config import AppSettings, ResourceConfig
from infra_auditor.models.common import CollectionStatus
from infra_auditor.runtime import collect_instance_snapshot
from infra_auditor.secrets.aws import PostgresCredentials
from infra_auditor.storage.local import LocalSnapshotWriter


class FakeRDSDiscovery:
    def __init__(self, instance: RDSInstance) -> None:
        self.instance = instance

    def describe_instance(self, **_kwargs: Any) -> RDSInstance:
        return self.instance


class FakeCredentialProvider:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def get_postgres_credentials(self, _secret_id: str) -> PostgresCredentials:
        if self.should_fail:
            raise RuntimeError("secret unavailable")
        return PostgresCredentials(username="prj_rl_rds_auditor_prod", password="fake-password")


class FakeConnection:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self.rows = rows

    def execute(self, _query: str) -> Iterator[Sequence[object]]:
        return iter(self.rows)


class FakeConnectionFactory:
    @contextmanager
    def connect(self, **_kwargs: Any) -> Iterator[FakeConnection]:
        yield FakeConnection([("postgres", True, False), ("app_db", True, False)])


def example_resource_config() -> ResourceConfig:
    return ResourceConfig.model_validate(
        {
            "version": 1,
            "aws": {"default_region": "ap-south-1"},
            "instances": {
                "raptor-catalog": {
                    "db_instance_identifier": "cleancatalograptorsupplies",
                    "secret_id": "infra-auditor/postgres/raptor-catalog",
                }
            },
        }
    )


def example_rds_instance() -> RDSInstance:
    return RDSInstance(
        alias="raptor-catalog",
        identifier="cleancatalograptorsupplies",
        region="ap-south-1",
        engine="postgres",
        engine_version="15.17",
        endpoint=RDSEndpoint(address="example.rds.amazonaws.com", port=5432),
    )


def test_collect_instance_snapshot_success_and_local_write(tmp_path: Path) -> None:
    settings = AppSettings(_env_file=None, snapshot_output_dir=tmp_path)
    snapshot = collect_instance_snapshot(
        settings=settings,
        resource_config=example_resource_config(),
        alias="raptor-catalog",
        rds_discovery_factory=lambda _region: FakeRDSDiscovery(example_rds_instance()),
        credential_provider_factory=lambda _region: FakeCredentialProvider(),
        connection_factory=FakeConnectionFactory(),
        database_collector=DatabaseDiscoveryCollector(),
        run_id_factory=lambda: "run-123",
    )

    assert snapshot.metadata.run_id == "run-123"
    assert snapshot.metadata.status == CollectionStatus.SUCCESS
    assert snapshot.instances[0].status == CollectionStatus.SUCCESS
    assert [database.name for database in snapshot.instances[0].databases] == ["postgres", "app_db"]

    path = LocalSnapshotWriter(tmp_path).write(snapshot)

    assert path == tmp_path / "run-123" / "raptor-catalog.json"
    assert path.exists()
    assert "fake-password" not in path.read_text(encoding="utf-8")


def test_collect_instance_snapshot_secret_failure_is_partial_success() -> None:
    settings = AppSettings(_env_file=None)
    snapshot = collect_instance_snapshot(
        settings=settings,
        resource_config=example_resource_config(),
        alias="raptor-catalog",
        rds_discovery_factory=lambda _region: FakeRDSDiscovery(example_rds_instance()),
        credential_provider_factory=lambda _region: FakeCredentialProvider(should_fail=True),
        connection_factory=FakeConnectionFactory(),
        database_collector=DatabaseDiscoveryCollector(),
        run_id_factory=lambda: "run-456",
    )

    assert snapshot.metadata.status == CollectionStatus.PARTIAL_SUCCESS
    assert snapshot.instances[0].aws_instance is not None
    assert snapshot.instances[0].databases == []
    assert snapshot.instances[0].gaps[0].collector == "secrets.postgres_credentials"
    assert snapshot.instances[0].collectors[-1].status == CollectionStatus.SKIPPED
