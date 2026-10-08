"""Cloud ontology: canonical resources, relationships, and discovery coverage.

The ontology is the provider-normalized source of truth for a connected cloud
environment.  Agent flows are consumers of this package; they must not invent
authoritative infrastructure facts themselves.
"""

from .models import (
    CoverageStatus,
    DiscoveryCoverage,
    OntologyRelationship,
    OntologyResource,
    OntologySnapshot,
    RelationshipEvidence,
    RelationshipKind,
    UnresolvedRelationship,
)
from .provider import OntologyProviderAdapter
from .registry import (
    get_ontology_adapter,
    register_ontology_adapter,
    supported_ontology_providers,
)


def _register_builtin_adapters() -> None:
    from .aws import AwsOntologyAdapter
    from .azure import AzureOntologyAdapter
    from .gcp import GcpOntologyAdapter

    register_ontology_adapter("aws", AwsOntologyAdapter)
    register_ontology_adapter("azure", AzureOntologyAdapter)
    register_ontology_adapter("gcp", GcpOntologyAdapter)


_register_builtin_adapters()

__all__ = [
    "CoverageStatus",
    "DiscoveryCoverage",
    "OntologyRelationship",
    "OntologyResource",
    "OntologySnapshot",
    "RelationshipEvidence",
    "RelationshipKind",
    "UnresolvedRelationship",
    "OntologyProviderAdapter",
    "get_ontology_adapter",
    "register_ontology_adapter",
    "supported_ontology_providers",
]
