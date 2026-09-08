from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from infra_auditor.capabilities import CAPABILITIES_BY_KEY, ServiceName, SubserviceName
from infra_auditor.config import load_resource_config
from infra_auditor.models.snapshot_split import SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY
from infra_auditor.service_registry import ServiceRegistry


def example_tree() -> dict[str, Any]:
    return yaml.safe_load(Path("config/environments.yaml").read_text())


def test_multiregion_tree_resolves_independent_selections(tmp_path: Path) -> None:
    raw = example_tree()
    raw["services"]["rds"]["regions"]["eu-west-1"] = {
        "instances": {
            "reporting-eu": {"db_instance_identifier": "reporting", "subservices": ["instance"]}
        }
    }
    raw["services"]["postgres"]["regions"]["eu-west-1"] = {
        "instances": {
            "reporting-eu": {
                "depends_on": {"service": "rds", "region": "eu-west-1", "instance": "reporting-eu"},
                "secret_id": "example/reference",
                "subservices": ["role-security"],
            }
        }
    }
    path = tmp_path / "regions.yml"
    path.write_text(yaml.safe_dump(raw))
    config = load_resource_config(path)
    assert config.region_for_instance("reporting-eu") == "eu-west-1"
    assert config.region_for_instance("udb") == "ap-south-1"
    assert config.coverage_for_instance("reporting-eu").collector_names() == frozenset(
        {
            "aws.rds.describe_db_instances",
            "postgres.role_security",
        }
    )
    assert "aws.cloudwatch.rds_metrics" in config.coverage_for_instance("udb").collector_names()


@pytest.mark.parametrize(
    "case",
    [
        "missing_host",
        "wrong_region",
        "wrong_subservice",
        "no_secret",
        "missing_discovery",
        "duplicate_alias",
        "unknown_service",
        "secret_on_rds",
        "bad_region",
        "report_as_collector",
    ],
)
def test_invalid_tree_fails_before_execution(case: str) -> None:
    raw = example_tree()
    rds = raw["services"]["rds"]
    pg = raw["services"]["postgres"]
    target = pg["regions"]["ap-south-1"]["instances"]["udb"]
    if case == "missing_host":
        target["depends_on"]["instance"] = "missing"
    elif case == "wrong_region":
        target["depends_on"]["region"] = "eu-west-1"
    elif case == "wrong_subservice":
        target["subservices"] = ["operations"]
    elif case == "no_secret":
        del target["secret_id"]
    elif case == "missing_discovery":
        rds["subservices"] = ["operations"]
    elif case == "duplicate_alias":
        rds["regions"]["eu-west-1"] = deepcopy(rds["regions"]["ap-south-1"])
    elif case == "unknown_service":
        raw["services"]["elasticsearch"] = deepcopy(rds)
    elif case == "secret_on_rds":
        rds["regions"]["ap-south-1"]["instances"]["udb"]["secret_id"] = "forbidden"
    elif case == "bad_region":
        rds["regions"]["../../private"] = rds["regions"].pop("ap-south-1")
    else:
        target["subservices"] = ["deterministic-findings"]
    with pytest.raises(ValidationError):
        ServiceRegistry.model_validate(raw)


def test_absent_postgres_is_rds_only_without_secret() -> None:
    raw = example_tree()
    del raw["services"]["postgres"]
    config = ServiceRegistry.model_validate(raw).execution_config()
    assert config.instances["udb"].secret_id is None
    assert config.coverage_for_instance("udb").postgres.subservices == []


def test_explicit_empty_instance_selection_overrides_service_defaults() -> None:
    raw = example_tree()
    target = raw["services"]["postgres"]["regions"]["ap-south-1"]["instances"]["udb"]
    target["subservices"] = []
    del target["secret_id"]
    config = ServiceRegistry.model_validate(raw).execution_config()
    assert config.coverage_for_instance("udb").postgres.subservices == []
    assert config.coverage_for_instance("raptor-catalog").postgres.subservices


def test_every_selectable_capability_has_the_matching_artifact_contract() -> None:
    for key, capability in CAPABILITIES_BY_KEY.items():
        assert capability.collector in SNAPSHOT_SPLIT_DEFINITIONS_BY_KEY[key].collector_names
    assert (
        ServiceName.POSTGRES,
        SubserviceName.AUDIT_DETERMINISTIC_FINDINGS,
    ) not in CAPABILITIES_BY_KEY
