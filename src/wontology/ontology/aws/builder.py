"""Compatibility wrapper around the provider-neutral spec engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from wontology.ontology.models import OntologySnapshot
from wontology.ontology.spec_engine import SpecOntologyAdapter


class AwsOntologyAdapter(SpecOntologyAdapter):
    def __init__(self) -> None:
        super().__init__("aws")


def build_aws_ontology_snapshot(
    inventory: dict[str, list[dict[str, Any]]],
    *,
    cloud_scope_id: str | None = None,
    account_id: str | None = None,
    observed_at: datetime | None = None,
    coverage: Iterable[Any] | None = None,
) -> OntologySnapshot:
    scope = cloud_scope_id or account_id
    if not scope:
        raise ValueError("cloud_scope_id is required")
    return AwsOntologyAdapter().build_snapshot(
        inventory, cloud_scope_id=scope, observed_at=observed_at, coverage=coverage
    )
