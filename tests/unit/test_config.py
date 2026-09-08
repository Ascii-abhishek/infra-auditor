from pathlib import Path

import pytest
from pydantic import ValidationError

from infra_auditor.config import AppSettings, LogFormat, SysEnv, load_resource_config
from infra_auditor.exceptions import ConfigurationError


def test_load_example_resource_config() -> None:
    config = load_resource_config(Path("config/environments.yaml"))

    assert config.version == 3
    assert config.aws.default_region == "ap-south-1"
    assert config.instances["raptor-catalog"].db_instance_identifier == "cleancatalograptorsupplies"
    assert config.instances["udb"].secret_id == "infra-auditor/postgres/udb"


def test_resource_config_rejects_invalid_alias(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        """
version: 1
aws:
  default_region: ap-south-1
instances:
  Bad_Alias:
    db_instance_identifier: example
    secret_id: infra-auditor/postgres/example
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="invalid instance aliases"):
        load_resource_config(config_path)


def test_settings_default_to_dev_when_sys_env_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SYS_ENV", raising=False)

    settings = AppSettings(_env_file=None)

    assert settings.sys_env == SysEnv.DEV
    assert settings.environment == "dev"
    assert settings.snapshot_bucket == "infra-audit-rl-dev"
    assert settings.web_host == "127.0.0.1"
    assert settings.web_port == 8008


def test_settings_read_sys_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYS_ENV", "prod")

    settings = AppSettings(_env_file=None)

    assert settings.sys_env == SysEnv.PROD
    assert settings.environment == "prod"
    assert settings.snapshot_bucket == "infra-audit-rl-prod"


def test_settings_reject_unknown_sys_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYS_ENV", "local")

    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)


def test_settings_overrides_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFRA_AUDITOR_LOG_FORMAT", "json")

    settings = AppSettings(_env_file=None)

    assert settings.log_format == LogFormat.JSON


def test_coverage_rejects_unknown_services_and_unsafe_dependencies() -> None:
    from infra_auditor.config import ServiceCoverage

    for raw in (
        {"elasticsearch": {}},
        {"postgres": {"subservices": ["execute_sql"]}},
        {"rds": {"subservices": ["operations"]}},
        {"postgres": {"subservices": ["role-security", "role-security"]}},
        {"postgres": {"password": "not-a-real-secret"}},
    ):
        with pytest.raises(ValidationError):
            ServiceCoverage.model_validate(raw)


def test_instance_coverage_replaces_defaults_and_version_one_stays_compatible() -> None:
    from infra_auditor.config import ResourceConfig

    raw = {
        "version": 2,
        "aws": {"default_region": "ap-south-1"},
        "services": {"postgres": {"subservices": []}},
        "instances": {
            "db": {
                "db_instance_identifier": "example",
                "secret_id": "example",
                "services": {"postgres": {"subservices": ["role-security"]}},
            },
            "other": {"db_instance_identifier": "other", "secret_id": "other"},
        },
    }
    config = ResourceConfig.model_validate(raw)
    assert config.coverage_for_instance("db").postgres.subservices == ["role-security"]
    assert config.coverage_for_instance("other").postgres.subservices == []
    raw["version"] = 1
    with pytest.raises(ValidationError, match="requires registry version 2"):
        ResourceConfig.model_validate(raw)
