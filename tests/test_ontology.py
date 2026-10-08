from copy import deepcopy

import pytest
from pydantic import ValidationError

from wontology.demo import demo
from wontology.ontology.models import OntologySnapshot
from wontology.ontology.spec_engine import SpecOntologyAdapter


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_examples_are_valid_evidence_backed_graphs(provider):
    value = demo(provider)
    snapshot = OntologySnapshot.model_validate(value)
    assert snapshot.promotable
    assert len(snapshot.resources) >= 4
    assert len(snapshot.relationships) >= 4
    assert all(edge.evidence and not edge.inferred for edge in snapshot.relationships)
    assert all(not row.raw for row in snapshot.resources)


def test_shared_network_is_not_application_dependency():
    value = demo()
    apps = [
        r["canonical_id"]
        for r in value["resources"]
        if r["provider_type"] == "AWS::EC2::Instance"
    ]
    assert len(apps) == 2
    assert not any(
        e["source_id"] in apps and e["target_id"] in apps
        for e in value["relationships"]
    )


@pytest.mark.parametrize("mutation", ["duplicate", "dangling", "inferred", "evidence"])
def test_invalid_snapshot_rejected(mutation):
    value = deepcopy(demo())
    if mutation == "duplicate":
        value["resources"].append(value["resources"][0])
    elif mutation == "dangling":
        value["relationships"][0]["target_id"] = "aws://absent"
    elif mutation == "inferred":
        value["relationships"][0]["inferred"] = True
    else:
        value["relationships"][0]["evidence"] = []
    with pytest.raises(ValidationError):
        OntologySnapshot.model_validate(value)


def test_aws_function_names_do_not_collide_across_regions():
    inventory = {
        "lambda": [
            {
                "FunctionName": "app",
                "FunctionArn": f"arn:aws:lambda:{region}:000000000000:function:app",
                "_region": region,
            }
            for region in ("us-east-1", "eu-west-1")
        ]
    }
    snapshot = SpecOntologyAdapter("aws").build_snapshot(
        inventory, cloud_scope_id="000000000000"
    )
    assert len({r.canonical_id for r in snapshot.resources}) == 2


def test_ambiguous_short_alias_never_connects_wrong_resource():
    inventory = {
        "instances": [
            {
                "selfLink": "https://compute.example/instances/app",
                "name": "app",
                "networkInterfaces": [{"network": "prod"}],
            }
        ],
        "networks": [
            {
                "selfLink": "https://compute.example/regions/a/networks/prod",
                "name": "prod",
            },
            {
                "selfLink": "https://compute.example/regions/b/networks/prod",
                "name": "prod",
            },
        ],
    }
    snapshot = SpecOntologyAdapter("gcp").build_snapshot(
        inventory, cloud_scope_id="example"
    )
    assert not snapshot.relationships
    assert snapshot.unresolved_relationships


def test_generic_inventory_does_not_drop_different_resource_with_same_name():
    inventory = {
        "networks": [{"selfLink": "https://compute.example/networks/prod", "name": "prod"}],
        "resource_inventory": [{"fullResourceName": "//storage.googleapis.com/prod", "name": "prod", "assetType": "storage.googleapis.com/Bucket"}],
    }
    snapshot = SpecOntologyAdapter("gcp").build_snapshot(inventory, cloud_scope_id="example")
    assert len(snapshot.resources) == 2
