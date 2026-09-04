"""Deterministic PostgreSQL security rules."""

from collections import defaultdict
from hashlib import sha256

from infra_auditor.collectors.postgres.role_security import (
    PostgresRole,
    PostgresRoleMembership,
    PostgresRoleSecurityEvidence,
)
from infra_auditor.models.evidence import EvidenceReference
from infra_auditor.models.finding import Finding, FindingSeverity

RDS_SUPERUSER_ROLE = "rds_superuser"


def evaluate_postgres_security_findings(
    *,
    run_id: str,
    instance_alias: str,
    role_security: PostgresRoleSecurityEvidence | None,
) -> list[Finding]:
    """Evaluate deterministic PostgreSQL security findings."""

    if role_security is None:
        return []

    roles_by_name = {role.name: role for role in role_security.roles}
    findings: list[Finding] = []
    findings.extend(
        _rds_superuser_membership_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            roles_by_name=roles_by_name,
            memberships=role_security.memberships,
        )
    )
    findings.extend(
        _login_to_login_membership_findings(
            run_id=run_id,
            instance_alias=instance_alias,
            roles_by_name=roles_by_name,
            memberships=role_security.memberships,
        )
    )
    return findings


def _rds_superuser_membership_findings(
    *,
    run_id: str,
    instance_alias: str,
    roles_by_name: dict[str, PostgresRole],
    memberships: list[PostgresRoleMembership],
) -> list[Finding]:
    if RDS_SUPERUSER_ROLE not in roles_by_name:
        return []

    adjacency = _membership_adjacency(memberships)
    findings: list[Finding] = []
    for role in sorted(roles_by_name.values(), key=lambda item: item.name):
        if not role.can_login or role.name == RDS_SUPERUSER_ROLE:
            continue
        path = _find_membership_path(
            adjacency=adjacency,
            start=role.name,
            target=RDS_SUPERUSER_ROLE,
        )
        if path is None:
            continue

        path_text = " -> ".join(path)
        findings.append(
            Finding(
                rule_id="SEC002",
                fingerprint=_fingerprint("SEC002", instance_alias, role.name),
                category="security/postgres/roles",
                severity=FindingSeverity.HIGH,
                resource=f"{instance_alias}/role/{role.name}",
                title="Login role has membership path to rds_superuser",
                summary=(
                    f"Role {role.name} can reach {RDS_SUPERUSER_ROLE} through "
                    f"membership path: {path_text}."
                ),
                observed={
                    "login_role": role.name,
                    "target_role": RDS_SUPERUSER_ROLE,
                    "membership_path": path,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        resource=f"{instance_alias}/role/{role.name}",
                        path="instances[0].postgres_role_security.memberships",
                    )
                ],
                recommendation=(
                    "Review whether this login role needs the effective RDS "
                    "administrative path. Prefer narrowly scoped NOLOGIN group "
                    "roles for normal application and human access."
                ),
            )
        )
    return findings


def _login_to_login_membership_findings(
    *,
    run_id: str,
    instance_alias: str,
    roles_by_name: dict[str, PostgresRole],
    memberships: list[PostgresRoleMembership],
) -> list[Finding]:
    findings: list[Finding] = []
    for membership in sorted(memberships, key=lambda item: (item.member, item.role)):
        member = roles_by_name.get(membership.member)
        parent = roles_by_name.get(membership.role)
        if member is None or parent is None:
            continue
        if not member.can_login or not parent.can_login:
            continue

        findings.append(
            Finding(
                rule_id="SEC003",
                fingerprint=_fingerprint("SEC003", instance_alias, member.name, parent.name),
                category="security/postgres/roles",
                severity=FindingSeverity.MEDIUM,
                resource=f"{instance_alias}/role/{member.name}",
                title="Login role is directly a member of another login role",
                summary=(
                    f"Login role {member.name} is directly a member of login role {parent.name}."
                ),
                observed={
                    "member_login_role": member.name,
                    "parent_login_role": parent.name,
                    "admin_option": membership.admin_option,
                },
                evidence=[
                    _evidence(
                        run_id=run_id,
                        resource=f"{instance_alias}/role/{member.name}",
                        path="instances[0].postgres_role_security.memberships",
                    )
                ],
                recommendation=(
                    "Review this role chain. Prefer LOGIN roles granted to "
                    "NOLOGIN group roles so ownership, human access, and "
                    "application privileges remain easier to reason about."
                ),
            )
        )
    return findings


def _membership_adjacency(
    memberships: list[PostgresRoleMembership],
) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for membership in memberships:
        adjacency[membership.member].append(membership.role)
    return {member: sorted(roles) for member, roles in adjacency.items()}


def _find_membership_path(
    *,
    adjacency: dict[str, list[str]],
    start: str,
    target: str,
) -> list[str] | None:
    stack: list[tuple[str, list[str]]] = [(start, [start])]
    while stack:
        current, path = stack.pop()
        for parent in reversed(adjacency.get(current, [])):
            if parent in path:
                continue
            next_path = [*path, parent]
            if parent == target:
                return next_path
            stack.append((parent, next_path))
    return None


def _evidence(*, run_id: str, resource: str, path: str) -> EvidenceReference:
    return EvidenceReference(
        snapshot_run_id=run_id,
        collector="postgres.role_security",
        resource=resource,
        path=path,
    )


def _fingerprint(*parts: str) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
