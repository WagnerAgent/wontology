"""Validated, immutable ontology bundles and provider-neutral normalization."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any, Iterable
from urllib.parse import quote

import jmespath
import yaml

from wontology.ontology.bundle_v3 import load_v3_bundle
from wontology.ontology.models import (
    CoverageStatus,
    DiscoveryCoverage,
    OntologyRelationship,
    OntologyResource,
    OntologySnapshot,
    RelationshipEvidence,
    RelationshipKind,
    UnresolvedRelationship,
)


_UPPER_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def _first(payload: dict[str, Any], fields: Iterable[str]) -> Any | None:
    for field in fields:
        value = jmespath.search(field, payload)
        if value not in (None, "", []):
            return value
    return None


def _snake_key(key: str) -> str:
    return _UPPER_BOUNDARY.sub("_", key.replace("-", "_")).lower()


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {_snake_key(str(k)): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _tags(raw: dict[str, Any]) -> dict[str, str]:
    value = raw.get("Tags", raw.get("tags", raw.get("labels", {})))
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if isinstance(value, list):
        return {
            str(item.get("Key", item.get("key"))): str(
                item.get("Value", item.get("value"))
            )
            for item in value
            if isinstance(item, dict)
            and item.get("Key", item.get("key")) is not None
            and item.get("Value", item.get("value")) is not None
        }
    return {}


def canonical_id(provider: str, cloud_scope_id: str, provider_id: str) -> str:
    """Stable identity excludes location, type, category, and display name."""
    return (
        f"{provider}://{quote(cloud_scope_id, safe='')}/{quote(provider_id, safe='')}"
    )


def _aliases(
    provider_id: str, raw: dict[str, Any], id_fields: Iterable[str]
) -> set[str]:
    values = {provider_id, provider_id.lower()}
    for field in id_fields:
        value = jmespath.search(field, raw)
        if isinstance(value, (str, int)):
            values.update((str(value), str(value).lower()))
    for separator in ("/", ":"):
        values.add(provider_id.rsplit(separator, 1)[-1])
    return values


@dataclass(frozen=True)
class CompiledOntologyBundle:
    provider: str
    schema_version: str
    bundle_version: str
    sha256: str
    defaults: dict[str, Any]
    resources: dict[str, dict[str, Any]]
    relationships: tuple[dict[str, Any], ...]


@lru_cache(maxsize=16)
def load_bundle(provider: str) -> CompiledOntologyBundle:
    path = files("wontology.ontology.specs").joinpath(f"{provider.lower()}.yaml")
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes)
    required = {
        "schema_version",
        "bundle_version",
        "provider",
        "defaults",
        "resources",
        "relationships",
    }
    missing = required - set(data or {})
    if missing:
        raise ValueError(f"ontology bundle {provider!r} missing {sorted(missing)}")
    if data["provider"].lower() != provider.lower():
        raise ValueError("ontology bundle provider does not match its filename")
    resource_keys = set(data["resources"])
    for rule in data["relationships"]:
        if rule.get("source") not in resource_keys:
            raise ValueError(f"relationship {rule.get('id')} has unknown source")
        RelationshipKind(rule["kind"])
        jmespath.compile(rule["path"])
    return CompiledOntologyBundle(
        provider=data["provider"].lower(),
        schema_version=str(data["schema_version"]),
        bundle_version=str(data["bundle_version"]),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        defaults=dict(data["defaults"]),
        resources={str(k): dict(v or {}) for k, v in data["resources"].items()},
        relationships=tuple(dict(v) for v in data["relationships"]),
    )


class SpecOntologyAdapter:
    def __init__(self, provider: str):
        self.bundle = load_bundle(provider)
        self.semantic_bundle = load_v3_bundle(provider)
        self.provider = self.bundle.provider

    def _resource(
        self, key: str, raw: dict[str, Any], scope: str, observed: datetime
    ) -> OntologyResource:
        definition = {**self.bundle.defaults, **self.bundle.resources.get(key, {})}
        id_fields = tuple(
            definition.get("id_fields") or self.bundle.defaults["id_fields"]
        )
        provider_id = _first(raw, id_fields)
        if provider_id is None:
            raise ValueError(
                f"{self.provider}/{key} resource has no provider-native identifier"
            )
        dynamic = (
            bool(definition.get("dynamic_type")) or key not in self.bundle.resources
        )
        native_type = _first(
            raw,
            definition.get("type_fields")
            or self.bundle.defaults.get("type_fields", ()),
        )
        provider_type = str(
            native_type or definition.get("type") or f"{self.provider}.resource/{key}"
        )
        tags = _tags(raw)
        name = (
            tags.get("Name")
            or _first(raw, definition.get("name_fields") or ())
            or provider_id
        )
        location = (
            "global"
            if definition.get("global")
            else str(
                _first(
                    raw,
                    definition.get("location_fields")
                    or self.bundle.defaults.get("location_fields", ()),
                )
                or "unknown"
            )
        )
        if dynamic and native_type and definition.get("dynamic_type_prefix"):
            qualified = str(native_type)
            if (
                definition.get("dynamic_type_qualified_by_service")
                and ":" not in qualified
            ):
                qualified = f"{raw.get('Service') or 'unknown'}:{qualified}"
            provider_type = f"{definition['dynamic_type_prefix']}{qualified}"
        semantic = self.semantic_bundle.classify(provider_type, raw)
        aliases = _aliases(str(provider_id), raw, id_fields)
        zone_marker = definition.get("zone_identifier_contains")
        location_type = (
            "global"
            if location == "global"
            else (
                "unknown"
                if location == "unknown"
                else (
                    "zone"
                    if zone_marker and zone_marker in str(provider_id)
                    else "region"
                )
            )
        )
        return OntologyResource(
            canonical_id=canonical_id(self.provider, scope, str(provider_id)),
            provider=self.provider,
            provider_type=provider_type,
            service=str(raw.get("Service") or key),
            provider_id=str(provider_id),
            aliases=tuple(sorted(aliases)),
            cloud_scope_id=scope,
            location=location,
            location_type=location_type,
            name=str(name),
            category=str(
                semantic.facets.get("domain") or definition.get("category", "unknown")
            ),
            capabilities=semantic.capabilities,
            semantic_type=semantic.semantic_type,
            semantic_facets=semantic.facets,
            health=semantic.health,
            classification_status=semantic.status,
            classification_rule_id=semantic.rule_id,
            presentation_ref=semantic.presentation_ref,
            properties=_normalize(
                {k: v for k, v in raw.items() if not k.startswith("_")}
            ),
            raw=raw,
            tags=tags,
            source_api=str(raw.get("_source_api") or f"{self.provider}-mcp"),
            observed_at=observed,
            schema_version=self.bundle.schema_version,
        )

    def build_snapshot(
        self,
        inventory: dict[str, list[dict[str, Any]]],
        *,
        cloud_scope_id: str,
        observed_at: datetime | None = None,
        coverage: Iterable[Any] | None = None,
    ) -> OntologySnapshot:
        observed = observed_at or datetime.now(timezone.utc)
        records: list[tuple[str, OntologyResource, set[str]]] = []
        ordered = [k for k in inventory if k != "resource_inventory"] + (
            ["resource_inventory"] if "resource_inventory" in inventory else []
        )
        known_ids: set[str] = set()
        for key in ordered:
            definition = {**self.bundle.defaults, **self.bundle.resources.get(key, {})}
            for raw in inventory.get(key, []):
                if not isinstance(raw, dict):
                    continue
                resource = self._resource(key, raw, cloud_scope_id, observed)
                aliases = set(resource.aliases)
                if key == "resource_inventory" and resource.canonical_id in known_ids:
                    continue
                records.append((key, resource, aliases))
                if key != "resource_inventory":
                    known_ids.add(resource.canonical_id)

        alias_index: dict[str, str] = {}
        ambiguous_aliases: set[str] = set()
        for _, resource, aliases in records:
            for alias in aliases | {resource.canonical_id}:
                for value in {str(alias), str(alias).lower()}:
                    existing = alias_index.get(value)
                    if existing and existing != resource.canonical_id:
                        ambiguous_aliases.add(value)
                    else:
                        alias_index[value] = resource.canonical_id
        # A short name shared across types or regions cannot identify an endpoint.
        for value in ambiguous_aliases:
            alias_index.pop(value, None)

        edges: dict[tuple[str, str, str, str], OntologyRelationship] = {}
        unresolved: list[UnresolvedRelationship] = []
        rules_by_source: dict[str, list[dict[str, Any]]] = {}
        for rule in self.bundle.relationships:
            rules_by_source.setdefault(rule["source"], []).append(rule)
        for key, resource, _ in records:
            for rule in rules_by_source.get(key, ()):
                found = jmespath.search(rule["path"], resource.raw)
                values = found if isinstance(found, list) else [found]
                for value in values:
                    if value is None:
                        continue
                    target = alias_index.get(str(value)) or alias_index.get(
                        str(value).lower()
                    )
                    if not target:
                        unresolved.append(
                            UnresolvedRelationship(
                                source_id=resource.canonical_id,
                                target_ref=str(value),
                                kind=RelationshipKind(rule["kind"]),
                                rule_id=rule["id"],
                                path=rule["path"],
                            )
                        )
                        continue
                    if target == resource.canonical_id:
                        continue
                    source = resource.canonical_id
                    if rule.get("reverse"):
                        source, target = target, source
                    edge = OntologyRelationship(
                        source_id=source,
                        target_id=target,
                        kind=RelationshipKind(rule["kind"]),
                        evidence=(
                            RelationshipEvidence(
                                source=str(
                                    resource.raw.get("_hydrated_by")
                                    or resource.raw.get("_source_api")
                                    or f"{self.provider}-mcp"
                                ),
                                path=rule["path"],
                                value=value,
                            ),
                        ),
                        confidence=1.0,
                        inferred=False,
                        rule_id=rule["id"],
                        rule_version=self.bundle.bundle_version,
                        observed_at=observed,
                    )
                    edges.setdefault(edge.identity, edge)

        coverage_rows: list[DiscoveryCoverage] = []
        if coverage:
            for item in coverage:
                value = item if isinstance(item, dict) else vars(item)
                try:
                    status = CoverageStatus(str(value.get("status", "failed")))
                except ValueError:
                    status = CoverageStatus.FAILED
                coverage_rows.append(
                    DiscoveryCoverage(
                        provider=self.provider,
                        cloud_scope_id=cloud_scope_id,
                        location=str(
                            value.get("region") or value.get("location") or "unknown"
                        ),
                        service=str(value.get("service") or "unknown"),
                        status=status,
                        resources_found=int(value.get("resources_found") or 0),
                        error_code=value.get("error_code"),
                        error_message=value.get("error_message"),
                        started_at=observed,
                        completed_at=observed,
                    )
                )
        else:
            for key in self.bundle.resources:
                count = sum(1 for record_key, _, _ in records if record_key == key)
                coverage_rows.append(
                    DiscoveryCoverage(
                        provider=self.provider,
                        cloud_scope_id=cloud_scope_id,
                        location="global"
                        if self.bundle.resources[key].get("global")
                        else "unknown",
                        service=key,
                        status=CoverageStatus.COMPLETE
                        if count
                        else CoverageStatus.EMPTY,
                        resources_found=count,
                        started_at=observed,
                        completed_at=observed,
                    )
                )
        return OntologySnapshot(
            resources=tuple(r for _, r, _ in records),
            relationships=tuple(edges.values()),
            coverage=tuple(coverage_rows),
            schema_version=self.semantic_bundle.schema_version,
            spec_bundle_version=self.semantic_bundle.bundle_version,
            spec_bundle_hash=self.semantic_bundle.sha256,
            taxonomy_version=self.semantic_bundle.taxonomy_version,
            presentation_bundle_version=self.semantic_bundle.bundle_version,
            presentation_bundle_hash=self.semantic_bundle.presentation_hash,
            unresolved_relationships=tuple(unresolved),
        )
