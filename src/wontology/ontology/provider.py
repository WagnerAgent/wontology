"""Provider port for building the provider-neutral cloud ontology."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Protocol, runtime_checkable

from wontology.ontology.models import OntologySnapshot


@runtime_checkable
class OntologyProviderAdapter(Protocol):
    """Contract implemented independently by AWS, GCP, and Azure adapters."""

    provider: str

    def build_snapshot(
        self,
        inventory: dict[str, list[dict[str, Any]]],
        *,
        cloud_scope_id: str,
        observed_at: datetime | None = None,
        coverage: Iterable[Any] | None = None,
    ) -> OntologySnapshot:
        """Normalize provider payloads and derive evidence-backed relations."""
        ...
