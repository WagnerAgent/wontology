"""Compiled, provider-neutral ontology v3 classification and UI metadata."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import jmespath
import yaml


HEALTH_STATES = {"healthy", "degraded", "unhealthy", "unknown", "not_applicable"}
CLASSIFICATION_STATES = {"classified", "unclassified", "provider_specific"}


@dataclass(frozen=True)
class SemanticResult:
    semantic_type: str
    facets: dict[str, str | None]
    capabilities: tuple[str, ...]
    health: dict[str, Any]
    status: str
    rule_id: str | None
    presentation_ref: str


@dataclass(frozen=True)
class CompiledV3Bundle:
    provider: str
    schema_version: str
    bundle_version: str
    taxonomy_version: str
    sha256: str
    presentation_hash: str
    rules: tuple[dict[str, Any], ...]
    presentation: dict[str, dict[str, Any]]
    authoring: dict[str, dict[str, Any]]
    lanes: tuple[dict[str, Any], ...]
    asset_root: Path

    def classify(self, native_type: str, raw: dict[str, Any]) -> SemanticResult:
        candidates: list[tuple[int, int, dict[str, Any]]] = []
        for rule in self.rules:
            exact = rule.get("native_type")
            pattern = rule.get("native_type_glob")
            if exact == native_type or (
                pattern and fnmatch.fnmatchcase(native_type, pattern)
            ):
                condition = rule.get("when")
                if condition and not jmespath.search(condition, raw):
                    continue
                candidates.append(
                    (int(rule.get("priority", 0)), 1 if exact else 0, rule)
                )
        if not candidates:
            rule = {
                "id": None,
                "semantic_type": "generic.resource",
                "domain": "unknown",
                "kind": "resource",
                "subtype": None,
                "role": "unknown",
                "management_model": "unknown",
                "status": "unclassified",
                "capabilities": ["discovered", "requires_classification"],
            }
        else:
            rule = max(candidates, key=lambda item: (item[0], item[1]))[2]
        health = _health(rule.get("health") or {}, raw)
        semantic_type = str(rule.get("semantic_type") or "generic.resource")
        return SemanticResult(
            semantic_type=semantic_type,
            facets={
                "domain": str(rule.get("domain") or "unknown"),
                "kind": str(rule.get("kind") or "resource"),
                "subtype": rule.get("subtype"),
                "role": str(rule.get("role") or "unknown"),
                "management_model": str(rule.get("management_model") or "unknown"),
            },
            capabilities=tuple(str(value) for value in rule.get("capabilities") or ()),
            health=health,
            status=str(rule.get("status") or "classified"),
            rule_id=rule.get("id"),
            presentation_ref=str(rule.get("presentation_ref") or semantic_type),
        )

    def catalog(self, purpose: str = "render") -> list[dict[str, Any]]:
        values = []
        for semantic_type, presentation in sorted(self.presentation.items()):
            item = {"semantic_type": semantic_type, **presentation}
            if purpose == "authoring":
                item["property_schema"] = self.authoring.get(
                    semantic_type, {"type": "object", "properties": {}}
                )
            values.append(item)
        return values

    def asset(self, asset_id: str) -> Path | None:
        if not asset_id or "/" in asset_id or "\\" in asset_id or ".." in asset_id:
            return None
        candidate = self.asset_root / asset_id
        if candidate.is_file() and candidate.suffix.lower() == ".svg":
            return candidate
        shared = (
            Path(str(files("wontology.ontology.bundles").joinpath("core/assets")))
            / asset_id
        )
        return shared if shared.is_file() and shared.suffix.lower() == ".svg" else None


def _health(spec: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    path = spec.get("path")
    native = jmespath.search(path, raw) if path else None
    if native is None:
        state = str(spec.get("missing") or "unknown")
    else:
        mapping = {
            str(key).lower(): value for key, value in (spec.get("map") or {}).items()
        }
        state = str(mapping.get(str(native).lower(), spec.get("default") or "unknown"))
    if state not in HEALTH_STATES:
        raise ValueError(f"invalid ontology health state {state!r}")
    return {
        "state": state,
        "native_state": native,
        "evidence_path": path if native is not None else None,
    }


def _read_yaml(path: Any, default: Any) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return default, b""
    return yaml.safe_load(raw) or default, raw


@lru_cache(maxsize=16)
def load_v3_bundle(provider: str) -> CompiledV3Bundle:
    provider = provider.lower()
    root = files("wontology.ontology.bundles")
    core, core_raw = _read_yaml(root.joinpath("core/taxonomy.yaml"), {})
    projection, projection_raw = _read_yaml(root.joinpath("core/projection.yaml"), {})
    provider_root = root.joinpath(f"providers/{provider}")
    semantics, semantics_raw = _read_yaml(provider_root.joinpath("semantics.yaml"), {})
    presentation, presentation_raw = _read_yaml(
        provider_root.joinpath("presentation.yaml"), {}
    )
    authoring, authoring_raw = _read_yaml(provider_root.joinpath("authoring.yaml"), {})
    required = {"schema_version", "bundle_version", "provider", "rules"}
    if missing := required - set(semantics):
        raise ValueError(f"ontology v3 bundle {provider!r} missing {sorted(missing)}")
    if str(semantics["provider"]).lower() != provider:
        raise ValueError("ontology v3 provider does not match bundle directory")
    allowed_types = set(core.get("semantic_types") or ())
    seen: dict[tuple[str, int], str] = {}
    for rule in semantics["rules"]:
        if not rule.get("id"):
            raise ValueError("ontology semantic rule requires an id")
        match = rule.get("native_type") or rule.get("native_type_glob")
        if not match or (rule.get("native_type") and rule.get("native_type_glob")):
            raise ValueError(
                f"rule {rule['id']} requires exactly one native type matcher"
            )
        key = (str(match), int(rule.get("priority", 0)))
        if key in seen:
            raise ValueError(
                f"ambiguous semantic rules {seen[key]!r} and {rule['id']!r}"
            )
        seen[key] = str(rule["id"])
        semantic_type = str(rule.get("semantic_type") or "")
        if semantic_type not in allowed_types and not semantic_type.startswith(
            f"{provider}."
        ):
            raise ValueError(
                f"rule {rule['id']} references unknown semantic type {semantic_type!r}"
            )
        if rule.get("status", "classified") not in CLASSIFICATION_STATES:
            raise ValueError(f"rule {rule['id']} has invalid classification status")
        if rule.get("when"):
            jmespath.compile(rule["when"])
        _health(rule.get("health") or {}, {})
    presentation_items = dict(presentation.get("types") or {})
    if "generic.resource" not in presentation_items:
        raise ValueError("presentation bundle requires generic.resource")
    for rule in semantics["rules"]:
        if (
            rule.get("presentation_ref")
            and str(rule["presentation_ref"]) not in presentation_items
        ):
            raise ValueError(
                f"rule {rule['id']} references missing presentation {rule['presentation_ref']!r}"
            )
    digest_bytes = b"\n".join(
        (core_raw, projection_raw, semantics_raw, presentation_raw, authoring_raw)
    )
    return CompiledV3Bundle(
        provider=provider,
        schema_version=str(semantics["schema_version"]),
        bundle_version=str(semantics["bundle_version"]),
        taxonomy_version=str(core.get("version") or "3.0.0"),
        sha256=hashlib.sha256(digest_bytes).hexdigest(),
        presentation_hash=hashlib.sha256(presentation_raw + authoring_raw).hexdigest(),
        rules=tuple(dict(rule) for rule in semantics["rules"]),
        presentation=presentation_items,
        authoring=dict(authoring.get("types") or {}),
        lanes=tuple(dict(lane) for lane in projection.get("lanes") or ()),
        asset_root=Path(str(provider_root.joinpath("assets"))),
    )


def bundle_manifest(bundle: CompiledV3Bundle) -> str:
    return json.dumps(
        {
            "provider": bundle.provider,
            "schema_version": bundle.schema_version,
            "bundle_version": bundle.bundle_version,
            "taxonomy_version": bundle.taxonomy_version,
            "sha256": bundle.sha256,
            "presentation_hash": bundle.presentation_hash,
        },
        sort_keys=True,
    )
