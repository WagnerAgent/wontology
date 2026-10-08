"""Synthetic cloud examples. No customer infrastructure or credentials."""

from .ontology.spec_engine import SpecOntologyAdapter


def demo(provider="aws"):
    if provider == "aws":
        scope = "000000000000"
        inventory = {
            "vpc": [
                {
                    "VpcId": "vpc-demo",
                    "Tags": [{"Key": "Name", "Value": "Production network"}],
                    "_region": "us-east-1",
                }
            ],
            "subnet": [
                {
                    "SubnetId": "subnet-public",
                    "VpcId": "vpc-demo",
                    "Tags": [{"Key": "Name", "Value": "Public subnet"}],
                    "_region": "us-east-1",
                },
                {
                    "SubnetId": "subnet-private",
                    "VpcId": "vpc-demo",
                    "Tags": [{"Key": "Name", "Value": "Private subnet"}],
                    "_region": "us-east-1",
                },
            ],
            "securitygroup": [
                {
                    "GroupId": "sg-web",
                    "GroupName": "Web access",
                    "VpcId": "vpc-demo",
                    "_region": "us-east-1",
                }
            ],
            "ec2": [
                {
                    "InstanceId": f"i-demo-{n}",
                    "SubnetId": "subnet-private",
                    "VpcId": "vpc-demo",
                    "SecurityGroups": [{"GroupId": "sg-web"}],
                    "Tags": [{"Key": "Name", "Value": f"Application {n}"}],
                    "State": {"Name": "running"},
                    "_region": "us-east-1",
                }
                for n in (1, 2)
            ],
            "alb": [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:000000000000:loadbalancer/app/demo",
                    "LoadBalancerName": "Public gateway",
                    "VpcId": "vpc-demo",
                    "AvailabilityZones": [{"SubnetId": "subnet-public"}],
                    "SecurityGroups": ["sg-web"],
                    "_region": "us-east-1",
                }
            ],
            "rds": [
                {
                    "DBInstanceArn": "arn:aws:rds:us-east-1:000000000000:db:demo",
                    "DBInstanceIdentifier": "Application database",
                    "DBSubnetGroup": {
                        "VpcId": "vpc-demo",
                        "Subnets": [{"SubnetIdentifier": "subnet-private"}],
                    },
                    "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-web"}],
                    "_region": "us-east-1",
                }
            ],
            "ebs": [
                {
                    "VolumeId": "vol-demo",
                    "Attachments": [{"InstanceId": "i-demo-1"}],
                    "_region": "us-east-1",
                }
            ],
            "s3": [{"Name": "wontology-example-assets", "_region": "global"}],
            "lambda": [
                {
                    "FunctionArn": "arn:aws:lambda:us-east-1:000000000000:function:demo",
                    "FunctionName": "Background worker",
                    "VpcConfig": {
                        "SubnetIds": ["subnet-private"],
                        "SecurityGroupIds": ["sg-web"],
                    },
                    "_region": "us-east-1",
                }
            ],
        }
    elif provider == "azure":
        scope = "00000000-0000-0000-0000-000000000000"
        base = f"/subscriptions/{scope}/resourceGroups/demo/providers/Microsoft.Network"
        vnet, subnet, nic, sg = (
            f"{base}/virtualNetworks/prod",
            f"{base}/virtualNetworks/prod/subnets/private",
            f"{base}/networkInterfaces/web",
            f"{base}/networkSecurityGroups/web",
        )
        inventory = {
            "virtual_networks": [
                {
                    "id": vnet,
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": "Production network",
                    "location": "eastus",
                }
            ],
            "subnets": [
                {
                    "id": subnet,
                    "type": "Microsoft.Network/virtualNetworks/subnets",
                    "name": "Private subnet",
                    "location": "eastus",
                    "parent_vnet_id": vnet,
                    "properties": {"networkSecurityGroup": {"id": sg}},
                }
            ],
            "network_interfaces": [
                {
                    "id": nic,
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "Application interface",
                    "location": "eastus",
                    "properties": {
                        "ipConfigurations": [
                            {"properties": {"subnet": {"id": subnet}}}
                        ],
                        "networkSecurityGroup": {"id": sg},
                    },
                }
            ],
            "security_groups": [
                {
                    "id": sg,
                    "type": "Microsoft.Network/networkSecurityGroups",
                    "name": "Web access",
                    "location": "eastus",
                }
            ],
            "virtual_machines": [
                {
                    "id": f"/subscriptions/{scope}/resourceGroups/demo/providers/Microsoft.Compute/virtualMachines/web",
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "Application server",
                    "location": "eastus",
                    "properties": {
                        "networkProfile": {"networkInterfaces": [{"id": nic}]}
                    },
                }
            ],
        }
    elif provider == "gcp":
        scope = "wontology-example"
        base = f"https://www.googleapis.com/compute/v1/projects/{scope}"
        network, subnet = (
            f"{base}/global/networks/prod",
            f"{base}/regions/us-central1/subnetworks/private",
        )
        inventory = {
            "networks": [
                {
                    "selfLink": network,
                    "name": "Production network",
                    "assetType": "compute.googleapis.com/Network",
                    "location": "global",
                }
            ],
            "subnetworks": [
                {
                    "selfLink": subnet,
                    "name": "Private subnet",
                    "network": network,
                    "assetType": "compute.googleapis.com/Subnetwork",
                    "location": "us-central1",
                }
            ],
            "instances": [
                {
                    "selfLink": f"{base}/zones/us-central1-a/instances/web",
                    "name": "Application server",
                    "assetType": "compute.googleapis.com/Instance",
                    "location": "us-central1-a",
                    "networkInterfaces": [{"network": network, "subnetwork": subnet}],
                }
            ],
            "disks": [
                {
                    "selfLink": f"{base}/zones/us-central1-a/disks/web",
                    "name": "Application disk",
                    "assetType": "compute.googleapis.com/Disk",
                    "location": "us-central1-a",
                    "users": [f"{base}/zones/us-central1-a/instances/web"],
                }
            ],
        }
    else:
        raise ValueError("Unknown provider")
    for rows in inventory.values():
        for row in rows:
            row["_source_api"] = "synthetic-example"
    coverage = [
        {
            "service": key,
            "location": "example",
            "status": "complete",
            "resources_found": len(rows),
        }
        for key, rows in inventory.items()
    ]
    value = (
        SpecOntologyAdapter(provider)
        .build_snapshot(inventory, cloud_scope_id=scope, coverage=coverage)
        .model_dump(mode="json")
    )
    for row in value["resources"]:
        row["raw"] = {}
    return {
        **value,
        "provider": provider,
        "scope": scope,
        "demo": True,
        "complete": True,
        "id": f"demo-{provider}",
    }
