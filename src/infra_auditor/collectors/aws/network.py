"""AWS network evidence collectors."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from infra_auditor.collectors.aws.client import EC2Client
from infra_auditor.collectors.aws.models import RDSInstance
from infra_auditor.exceptions import AWSDiscoveryError


class SecurityGroupPeerType(StrEnum):
    """Supported security group ingress peer types."""

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    SECURITY_GROUP = "security_group"
    PREFIX_LIST = "prefix_list"


class SecurityGroupIngressPeer(BaseModel):
    """Normalized security group ingress peer."""

    type: SecurityGroupPeerType
    value: str
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class SecurityGroupIngressRule(BaseModel):
    """Normalized inbound security group rule."""

    ip_protocol: str
    from_port: int | None = None
    to_port: int | None = None
    peers: list[SecurityGroupIngressPeer] = Field(default_factory=list)
    covers_database_port: bool
    public_ipv4: bool
    public_ipv6: bool

    model_config = ConfigDict(extra="forbid")


class SecurityGroupEvidence(BaseModel):
    """Normalized security group evidence."""

    group_id: str
    group_name: str | None = None
    vpc_id: str | None = None
    ingress_rules: list[SecurityGroupIngressRule] = Field(default_factory=list)
    public_database_port_ingress: bool

    model_config = ConfigDict(extra="forbid")


class RDSSecurityGroupEvidence(BaseModel):
    """Security group evidence for one RDS DB instance."""

    database_port: int
    security_groups: list[SecurityGroupEvidence] = Field(default_factory=list)
    public_database_port_ingress: bool

    model_config = ConfigDict(extra="forbid")


class SecurityGroupIngressCollector:
    """Collect RDS-attached security group ingress evidence."""

    name = "aws.ec2.security_group_ingress"

    def __init__(self, client: EC2Client) -> None:
        self._client = client

    def collect(self, instance: RDSInstance) -> RDSSecurityGroupEvidence:
        group_ids = [
            group.vpc_security_group_id
            for group in instance.vpc_security_groups
            if group.vpc_security_group_id
        ]
        database_port = instance.endpoint.port if instance.endpoint else 5432
        if not group_ids:
            return RDSSecurityGroupEvidence(
                database_port=database_port,
                security_groups=[],
                public_database_port_ingress=False,
            )

        try:
            payloads = self._describe_security_groups(group_ids)
        except Exception as exc:  # noqa: BLE001 - AWS clients raise provider-specific errors.
            raise AWSDiscoveryError(
                f"failed to describe security groups for {instance.identifier}"
            ) from exc

        security_groups = [
            _security_group_from_payload(payload, database_port)
            for payload in payloads
            if isinstance(payload, dict)
        ]
        return RDSSecurityGroupEvidence(
            database_port=database_port,
            security_groups=security_groups,
            public_database_port_ingress=any(
                group.public_database_port_ingress for group in security_groups
            ),
        )

    def _describe_security_groups(self, group_ids: list[str]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        next_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"GroupIds": group_ids}
            if next_token is not None:
                kwargs["NextToken"] = next_token
            response = self._client.describe_security_groups(**kwargs)
            for item in response.get("SecurityGroups", []):
                if isinstance(item, dict):
                    payloads.append(item)
            token = response.get("NextToken")
            next_token = str(token) if token else None
            if next_token is None:
                return payloads


def _security_group_from_payload(
    payload: dict[str, Any],
    database_port: int,
) -> SecurityGroupEvidence:
    ingress_rules = [
        _ingress_rule_from_payload(permission, database_port)
        for permission in payload.get("IpPermissions", [])
        if isinstance(permission, dict)
    ]
    return SecurityGroupEvidence(
        group_id=str(payload.get("GroupId", "")),
        group_name=_optional_str(payload.get("GroupName")),
        vpc_id=_optional_str(payload.get("VpcId")),
        ingress_rules=ingress_rules,
        public_database_port_ingress=any(
            rule.covers_database_port and (rule.public_ipv4 or rule.public_ipv6)
            for rule in ingress_rules
        ),
    )


def _ingress_rule_from_payload(
    payload: dict[str, Any],
    database_port: int,
) -> SecurityGroupIngressRule:
    peers = _peers_from_payload(payload)
    from_port = _optional_int(payload.get("FromPort"))
    to_port = _optional_int(payload.get("ToPort"))
    public_ipv4 = any(
        peer.type == SecurityGroupPeerType.IPV4 and peer.value == "0.0.0.0/0" for peer in peers
    )
    public_ipv6 = any(
        peer.type == SecurityGroupPeerType.IPV6 and peer.value == "::/0" for peer in peers
    )
    return SecurityGroupIngressRule(
        ip_protocol=str(payload.get("IpProtocol", "")),
        from_port=from_port,
        to_port=to_port,
        peers=peers,
        covers_database_port=_covers_port(
            ip_protocol=str(payload.get("IpProtocol", "")),
            from_port=from_port,
            to_port=to_port,
            port=database_port,
        ),
        public_ipv4=public_ipv4,
        public_ipv6=public_ipv6,
    )


def _peers_from_payload(payload: dict[str, Any]) -> list[SecurityGroupIngressPeer]:
    peers: list[SecurityGroupIngressPeer] = []
    for item in payload.get("IpRanges", []):
        if isinstance(item, dict) and item.get("CidrIp"):
            peers.append(
                SecurityGroupIngressPeer(
                    type=SecurityGroupPeerType.IPV4,
                    value=str(item["CidrIp"]),
                    description=_optional_str(item.get("Description")),
                )
            )
    for item in payload.get("Ipv6Ranges", []):
        if isinstance(item, dict) and item.get("CidrIpv6"):
            peers.append(
                SecurityGroupIngressPeer(
                    type=SecurityGroupPeerType.IPV6,
                    value=str(item["CidrIpv6"]),
                    description=_optional_str(item.get("Description")),
                )
            )
    for item in payload.get("UserIdGroupPairs", []):
        if isinstance(item, dict) and item.get("GroupId"):
            peers.append(
                SecurityGroupIngressPeer(
                    type=SecurityGroupPeerType.SECURITY_GROUP,
                    value=str(item["GroupId"]),
                    description=_optional_str(item.get("Description")),
                )
            )
    for item in payload.get("PrefixListIds", []):
        if isinstance(item, dict) and item.get("PrefixListId"):
            peers.append(
                SecurityGroupIngressPeer(
                    type=SecurityGroupPeerType.PREFIX_LIST,
                    value=str(item["PrefixListId"]),
                    description=_optional_str(item.get("Description")),
                )
            )
    return peers


def _covers_port(
    *,
    ip_protocol: str,
    from_port: int | None,
    to_port: int | None,
    port: int,
) -> bool:
    if ip_protocol == "-1":
        return True
    if from_port is None or to_port is None:
        return False
    return from_port <= port <= to_port


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float | str | bytes | bytearray):
        return int(value)
    msg = f"expected int-compatible value, got {type(value).__name__}"
    raise TypeError(msg)


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
