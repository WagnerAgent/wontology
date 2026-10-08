"""Provider-neutral contracts for Wontology's cloud ontology."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


ONTOLOGY_SCHEMA_VERSION = "3.0.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RelationshipKind(str, Enum):
    """Small, directional vocabulary shared by every cloud provider."""

    CONTAINS = "contains"
    DEPLOYED_IN = "deployed_in"
    ATTACHED_TO = "attached_to"
    ASSOCIATED_WITH = "associated_with"
    ROUTES_TO = "routes_to"
    SECURED_BY = "secured_by"
    ASSUMES_ROLE = "assumes_role"
    TRIGGERS = "triggers"
    PUBLISHES_TO = "publishes_to"
    SUBSCRIBES_TO = "subscribes_to"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    ENCRYPTED_BY = "encrypted_by"
    EXPOSES = "exposes"
    MANAGES = "manages"
    DEAD_LETTERS_TO = "dead_letters_to"
    DEPENDS_ON = "depends_on"
    CONNECTS_TO = "connects_to"
    SNAPSHOT_OF = "snapshot_of"
    REPLICA_OF = "replica_of"
    VERSION_OF = "version_of"
    CONFIGURED_BY = "configured_by"


class CoverageStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"
    ACCESS_DENIED = "access_denied"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class RelationshipEvidence(BaseModel):
    """Why Wontology believes an edge exists."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="Provider API/config source or inference engine")
    path: str | None = Field(default=None, description="Path in the source payload")
    value: Any | None = None
    observed: bool = True


class OntologyResource(BaseModel):
    """One stable cloud object as observed at a point in time."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str
    provider: str
    provider_type: str
    service: str = "unknown"
    provider_id: str
    aliases: tuple[str, ...] = ()
    cloud_scope_id: str = Field(
        description="Provider tenancy boundary: AWS account, GCP project, or Azure subscription"
    )
    location: str
    location_type: str = Field(
        description="global, region, zone, or provider-specific scope"
    )
    name: str | None = None
    category: str
    capabilities: tuple[str, ...] = ()
    semantic_type: str = "generic.resource"
    semantic_facets: dict[str, str | None] = Field(default_factory=dict)
    health: dict[str, Any] = Field(
        default_factory=lambda: {
            "state": "unknown",
            "native_state": None,
            "evidence_path": None,
        }
    )
    classification_status: str = "unclassified"
    classification_rule_id: str | None = None
    presentation_ref: str = "generic.resource"
    properties: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)
    source_api: str
    observed_at: datetime = Field(default_factory=utc_now)
    schema_version: str = ONTOLOGY_SCHEMA_VERSION


class OntologyRelationship(BaseModel):
    """A directional, evidence-bearing link between two ontology objects."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    target_id: str
    kind: RelationshipKind
    evidence: tuple[RelationshipEvidence, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    inferred: bool = False
    rule_id: str
    rule_version: str = "1"
    observed_at: datetime = Field(default_factory=utc_now)

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.source_id, self.target_id, self.kind.value, self.rule_id)


class DiscoveryCoverage(BaseModel):
    """Positive or negative evidence about what a discovery run examined."""

    model_config = ConfigDict(frozen=True)

    provider: str
    cloud_scope_id: str
    location: str
    service: str
    status: CoverageStatus
    resources_found: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)

    @property
    def scope_key(self) -> str:
        return f"{self.provider}:{self.cloud_scope_id}:{self.location}:{self.service}"


class UnresolvedRelationship(BaseModel):
    """A referenced provider object that was not present in this snapshot."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    target_ref: str
    kind: RelationshipKind
    rule_id: str
    path: str


class OntologySnapshot(BaseModel):
    """A validated graph projection produced by one discovery run."""

    resources: tuple[OntologyResource, ...]
    relationships: tuple[OntologyRelationship, ...]
    coverage: tuple[DiscoveryCoverage, ...] = ()
    unresolved_relationships: tuple[UnresolvedRelationship, ...] = ()
    schema_version: str = ONTOLOGY_SCHEMA_VERSION
    spec_bundle_version: str = "unversioned"
    spec_bundle_hash: str = ""
    taxonomy_version: str = "3.0.0"
    presentation_bundle_version: str = "unversioned"
    presentation_bundle_hash: str = ""

    @property
    def coverage_summary(self) -> dict[str, Any]:
        successful = sum(
            1
            for item in self.coverage
            if item.status in (CoverageStatus.COMPLETE, CoverageStatus.EMPTY)
        )
        total = len(self.coverage)
        gaps = total - successful
        return {
            "status": "complete" if total > 0 and gaps == 0 else "partial",
            "successful_scopes": successful,
            "gap_scopes": gaps,
            "total_scopes": total,
            "coverage_ratio": round(successful / total, 4) if total else 0.0,
        }

    @property
    def promotable(self) -> bool:
        summary = self.coverage_summary
        return summary["total_scopes"] > 0 and summary["status"] == "complete"

    @model_validator(mode="after")
    def validate_graph(self) -> "OntologySnapshot":
        resource_ids = [resource.canonical_id for resource in self.resources]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("ontology snapshot contains duplicate canonical IDs")

        known = set(resource_ids)
        dangling = [
            edge.identity
            for edge in self.relationships
            if edge.source_id not in known or edge.target_id not in known
        ]
        if dangling:
            raise ValueError(
                f"ontology snapshot contains dangling edges: {dangling[:5]}"
            )

        edge_ids = [edge.identity for edge in self.relationships]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("ontology snapshot contains duplicate relationships")
        if any(edge.inferred for edge in self.relationships):
            raise ValueError(
                "AI-inferred relationships cannot enter an authoritative snapshot"
            )
        if any(not edge.evidence for edge in self.relationships):
            raise ValueError("authoritative relationships require evidence")
        return self
