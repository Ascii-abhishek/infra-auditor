from typing import Any

from infra_auditor.collectors.aws.models import (
    RDSEndpoint,
    RDSInstance,
    RDSVpcSecurityGroup,
)
from infra_auditor.collectors.aws.network import (
    SecurityGroupIngressCollector,
    SecurityGroupPeerType,
)


class FakeEC2Client:
    def describe_security_groups(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "SecurityGroups": [
                {
                    "GroupId": "sg-123",
                    "GroupName": "rds-postgres",
                    "VpcId": "vpc-123",
                    "IpPermissions": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 5432,
                            "ToPort": 5432,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        },
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 22,
                            "ToPort": 22,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        },
                    ],
                }
            ]
        }


def test_security_group_collector_flags_public_database_port_ingress() -> None:
    evidence = SecurityGroupIngressCollector(FakeEC2Client()).collect(
        RDSInstance(
            alias="db",
            identifier="database-1",
            region="ap-south-1",
            endpoint=RDSEndpoint(address="example.amazonaws.com", port=5432),
            vpc_security_groups=[RDSVpcSecurityGroup(vpc_security_group_id="sg-123")],
        )
    )

    assert evidence.database_port == 5432
    assert evidence.public_database_port_ingress is True
    group = evidence.security_groups[0]
    assert group.group_id == "sg-123"
    assert group.public_database_port_ingress is True
    postgres_rule = group.ingress_rules[0]
    assert postgres_rule.covers_database_port is True
    assert postgres_rule.public_ipv4 is True
    assert postgres_rule.peers[0].type == SecurityGroupPeerType.IPV4
