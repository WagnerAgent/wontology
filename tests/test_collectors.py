from threading import Event
from types import SimpleNamespace

import pytest

from wontology.connectors.base import Collector, Cancelled, sanitize


def test_partial_pages_preserved_and_marked_failed():
    def fetch():
        yield {"VpcId": "vpc-example"}
        raise PermissionError("403 secret-token-must-not-leak")

    updates = []
    collector = Collector(
        "aws", "000000000000", lambda *args: updates.append(args), Event()
    )
    collector.collect("vpc", "us-east-1", fetch)
    result = collector.snapshot()
    assert len(result["resources"]) == 1
    assert result["coverage"][0]["status"] == "access_denied"
    assert "secret-token" not in str(result)
    assert updates


def test_cancelled_scan_does_not_report_empty_success():
    cancelled = Event()
    cancelled.set()
    collector = Collector("aws", "000000000000", lambda *_: None, cancelled)
    with pytest.raises(Cancelled):
        collector.collect("vpc", "region", lambda: [])
    assert not collector.coverage


def test_sensitive_data_redacted():
    value = sanitize(
        {
            "raw": {"private": "value"},
            "environment": {"TOKEN": "secret"},
            "properties": {
                "password": "secret",
                "name": "resource",
            "key": "-----BEGIN " + "PRIVATE KEY-----",
            },
        }
    )
    assert "raw" not in value
    assert value["environment"] == "[redacted]"
    assert value["properties"]["name"] == "resource"
    assert "secret" not in str(value)


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


def test_azure_pagination_and_nested_subnet_relationships(monkeypatch):
    from wontology.connectors import azure

    sub = "00000000-0000-0000-0000-000000000000"
    vnet = f"/subscriptions/{sub}/providers/Microsoft.Network/virtualNetworks/prod"
    pages = iter(
        [
            {
                "data": [
                    {
                        "id": vnet,
                        "name": "prod",
                        "type": "Microsoft.Network/virtualNetworks",
                        "properties": {
                            "subnets": [
                                {"id": vnet + "/subnets/private", "name": "private"}
                            ]
                        },
                    }
                ],
                "$skipToken": "page2",
            },
            {
                "data": [
                    {
                        "id": vnet + "/interfaces/web",
                        "name": "web",
                        "type": "Microsoft.Network/networkInterfaces",
                        "properties": {
                            "ipConfigurations": [
                                {
                                    "properties": {
                                        "subnet": {"id": vnet + "/subnets/private"}
                                    }
                                }
                            ]
                        },
                    }
                ]
            },
        ]
    )
    calls = []

    class Credential:
        def __init__(self, **_):
            pass

        def get_token(self, *_):
            return SimpleNamespace(token="not-a-real-token")

        def close(self):
            pass

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return Response(next(pages))

    monkeypatch.setattr(azure, "DefaultAzureCredential", Credential)
    monkeypatch.setattr(azure.requests, "post", post)
    result = azure.scan({"subscription": sub}, lambda *_: None, Event())
    assert calls[1]["options"]["$skipToken"] == "page2"
    assert len(result["resources"]) == 3
    assert {r["kind"] for r in result["relationships"]} == {"contains", "deployed_in"}
    assert all(c["status"] == "complete" for c in result["coverage"])


@pytest.mark.parametrize(
    "payload", [{"data": "bad"}, {"data": [], "resultTruncated": "true"}]
)
def test_azure_malformed_or_truncated_inventory_is_not_empty_success(
    monkeypatch, payload
):
    from wontology.connectors import azure

    monkeypatch.setattr(
        azure,
        "DefaultAzureCredential",
        lambda **_: SimpleNamespace(
            get_token=lambda *_: SimpleNamespace(token="example"), close=lambda: None
        ),
    )
    monkeypatch.setattr(azure.requests, "post", lambda *_, **__: Response(payload))
    result = azure.scan(
        {"subscription": "00000000-0000-0000-0000-000000000000"},
        lambda *_: None,
        Event(),
    )
    assert result["coverage"][0]["status"] == "failed"


def test_gcp_pages_and_full_resource_identity(monkeypatch):
    from wontology.connectors import gcp

    pages = iter(
        [
            {
                "assets": [
                    {
                        "name": "//compute.googleapis.com/projects/example-project/global/networks/prod",
                        "assetType": "compute.googleapis.com/Network",
                        "resource": {
                            "data": {
                                "name": "prod",
                                "selfLink": "https://compute.example/networks/prod",
                            }
                        },
                    }
                ],
                "nextPageToken": "page2",
            },
            {
                "assets": [
                    {
                        "name": "//compute.googleapis.com/projects/example-project/zones/a/instances/web",
                        "assetType": "compute.googleapis.com/Instance",
                        "resource": {
                            "data": {
                                "name": "web",
                                "selfLink": "https://compute.example/instances/web",
                                "networkInterfaces": [
                                    {"network": "https://compute.example/networks/prod"}
                                ],
                            }
                        },
                    }
                ]
            },
        ]
    )
    calls = []

    class Session:
        def __init__(self, credentials):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get(self, url, **kwargs):
            calls.append(kwargs)
            return Response(next(pages))

    requested_scopes = []

    def auth(**kwargs):
        requested_scopes.extend(kwargs["scopes"])
        return object(), "example-project"

    monkeypatch.setattr(gcp.google.auth, "default", auth)
    monkeypatch.setattr(gcp, "AuthorizedSession", Session)
    result = gcp.scan({"project": "example-project"}, lambda *_: None, Event())
    assert calls[1]["params"]["pageToken"] == "page2"
    assert len(result["resources"]) == 2
    assert len(result["relationships"]) == 1
    assert requested_scopes == ["https://www.googleapis.com/auth/cloud-platform"]


def test_aws_uses_only_metadata_and_follows_paginator(monkeypatch):
    from wontology.connectors import aws

    calls = []

    class Client:
        def get_caller_identity(self):
            return {"Account": "000000000000"}

        def can_paginate(self, operation):
            return operation == "describe_vpcs"

        def get_paginator(self, operation):
            calls.append(operation)
            return SimpleNamespace(
                paginate=lambda: iter(
                    [{"Vpcs": [{"VpcId": "vpc-a"}]}, {"Vpcs": [{"VpcId": "vpc-b"}]}]
                )
            )

        def __getattr__(self, operation):
            calls.append(operation)
            return lambda: {}

    session = SimpleNamespace(region_name="us-east-1", client=lambda *_, **__: Client())
    monkeypatch.setattr(aws.boto3, "Session", lambda **_: session)
    result = aws.scan({}, lambda *_: None, Event())
    assert len(result["resources"]) == 2
    assert all(
        op.startswith(("get_caller_identity", "describe_", "list_")) for op in calls
    )
    assert len(result["coverage"]) == len(aws.REGIONAL) + len(aws.GLOBAL)
