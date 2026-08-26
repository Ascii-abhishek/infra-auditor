from pathlib import Path

import pytest

from infra_auditor.config import AppSettings, LogFormat, load_resource_config
from infra_auditor.exceptions import ConfigurationError


def test_load_example_resource_config() -> None:
    config = load_resource_config(Path("config/environments.example.yaml"))

    assert config.version == 1
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


def test_settings_environment_overrides_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFRA_AUDITOR_LOG_FORMAT", "json")

    settings = AppSettings(_env_file=None)

    assert settings.log_format == LogFormat.JSON
