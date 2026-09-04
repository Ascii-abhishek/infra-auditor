from infra_auditor.collectors.postgres.role_security import (
    PostgresRole,
    PostgresRoleMembership,
    PostgresRoleSecurityEvidence,
)
from infra_auditor.models.finding import FindingSeverity
from infra_auditor.rules.postgres_security import evaluate_postgres_security_findings


def role(name: str, *, can_login: bool) -> PostgresRole:
    return PostgresRole(
        name=name,
        can_login=can_login,
        inherit=True,
        superuser=False,
        create_role=False,
        create_db=False,
        replication=False,
        bypass_rls=False,
        connection_limit=-1,
    )


def test_sec002_finds_login_path_to_rds_superuser() -> None:
    evidence = PostgresRoleSecurityEvidence(
        roles=[
            role("app_user", can_login=True),
            role("app_group", can_login=False),
            role("rds_superuser", can_login=False),
        ],
        memberships=[
            PostgresRoleMembership(
                member="app_user",
                role="app_group",
                admin_option=False,
            ),
            PostgresRoleMembership(
                member="app_group",
                role="rds_superuser",
                admin_option=False,
            ),
        ],
    )

    findings = evaluate_postgres_security_findings(
        run_id="run-123",
        instance_alias="raptor-catalog",
        role_security=evidence,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "SEC002"
    assert finding.severity == FindingSeverity.HIGH
    assert finding.observed["membership_path"] == [
        "app_user",
        "app_group",
        "rds_superuser",
    ]
    assert finding.evidence[0].collector == "postgres.role_security"


def test_sec003_finds_login_to_login_membership() -> None:
    evidence = PostgresRoleSecurityEvidence(
        roles=[
            role("human_user", can_login=True),
            role("legacy_login", can_login=True),
            role("readonly_group", can_login=False),
        ],
        memberships=[
            PostgresRoleMembership(
                member="human_user",
                role="legacy_login",
                admin_option=True,
            ),
            PostgresRoleMembership(
                member="human_user",
                role="readonly_group",
                admin_option=False,
            ),
        ],
    )

    findings = evaluate_postgres_security_findings(
        run_id="run-123",
        instance_alias="udb",
        role_security=evidence,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "SEC003"
    assert finding.severity == FindingSeverity.MEDIUM
    assert finding.observed["member_login_role"] == "human_user"
    assert finding.observed["parent_login_role"] == "legacy_login"
    assert finding.observed["admin_option"] is True


def test_postgres_security_rules_skip_when_evidence_missing() -> None:
    findings = evaluate_postgres_security_findings(
        run_id="run-123",
        instance_alias="udb",
        role_security=None,
    )

    assert findings == []
