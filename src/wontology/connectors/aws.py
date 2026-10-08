"""AWS SDK inventory. Only explicitly listed metadata operations are callable."""

from __future__ import annotations

import boto3
import jmespath
from botocore.config import Config

from .base import Collector

# key, SDK service, operation, resource-array expression
REGIONAL = [
    ("vpc", "ec2", "describe_vpcs", "Vpcs"),
    ("subnet", "ec2", "describe_subnets", "Subnets"),
    ("securitygroup", "ec2", "describe_security_groups", "SecurityGroups"),
    ("ec2", "ec2", "describe_instances", "Reservations[].Instances[]"),
    ("ebs", "ec2", "describe_volumes", "Volumes"),
    ("route_table", "ec2", "describe_route_tables", "RouteTables"),
    ("internet_gateway", "ec2", "describe_internet_gateways", "InternetGateways"),
    ("nat_gateway", "ec2", "describe_nat_gateways", "NatGateways"),
    ("alb", "elbv2", "describe_load_balancers", "LoadBalancers"),
    ("lambda", "lambda", "list_functions", "Functions"),
    ("rds", "rds", "describe_db_instances", "DBInstances"),
    ("ecr", "ecr", "describe_repositories", "repositories"),
    ("sns", "sns", "list_topics", "Topics"),
    ("loggroup", "logs", "describe_log_groups", "logGroups"),
    ("kms", "kms", "list_keys", "Keys"),
]
GLOBAL = [
    ("s3", "s3", "list_buckets", "Buckets"),
    ("iam_role", "iam", "list_roles", "Roles"),
]


def scan(options, publish, cancelled):
    session = boto3.Session(profile_name=options.get("profile") or None)
    config = Config(
        connect_timeout=5,
        read_timeout=20,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    identity = session.client("sts", config=config).get_caller_identity()
    account = identity["Account"]
    c = Collector("aws", account, publish, cancelled)
    regions = options.get("regions") or [session.region_name or "us-east-1"]
    if len(regions) > 40 or any(not isinstance(r, str) or not r for r in regions):
        raise ValueError("Choose between 1 and 40 AWS regions")
    for region, catalog in [(regions[0], GLOBAL), *[(r, REGIONAL) for r in regions]]:
        for key, service, operation, expression in catalog:

            def fetch(
                service=service,
                operation=operation,
                expression=expression,
                region=region,
                key=key,
            ):
                client = session.client(service, region_name=region, config=config)
                pages = (
                    client.get_paginator(operation).paginate()
                    if client.can_paginate(operation)
                    else [getattr(client, operation)()]
                )
                for page in pages:
                    c.check()
                    for row in jmespath.search(expression, page) or []:
                        row = dict(row)
                        # EC2 IDs are region-specific; names are not globally unique.
                        if key == "lambda":
                            row["resource_id"] = row.get("FunctionArn")
                        yield {
                            **row,
                            "_region": "global"
                            if (key, service, operation, expression) in GLOBAL
                            else region,
                            "_source_api": f"{service}.{operation}",
                        }

            c.collect(
                key,
                "global" if (key, service, operation, expression) in GLOBAL else region,
                fetch,
            )
    return c.snapshot()
