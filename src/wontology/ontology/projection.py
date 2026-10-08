"""Provider-neutral, presentation-ready topology projections."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from wontology.ontology.bundle_v3 import CompiledV3Bundle


LOGICAL_ROLES = {"runtime", "boundary", "control"}
OPERATIONS_ROLES = {"backup", "configuration", "policy", "operations", "supporting"}


def _group_id(placement_id: str, grouping_type: str) -> str:
    digest = hashlib.sha256(f"{placement_id}|{grouping_type}".encode()).hexdigest()[:20]
    return f"grp_{digest}"


def build_projection(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    bundle: CompiledV3Bundle,
    view: str,
) -> dict[str, Any]:
    by_id = {item["canonical_id"]: item for item in entities}
    parent: dict[str, str] = {}
    for edge in relationships:
        if edge["type"] == "contains":
            parent[edge["target_id"]] = edge["source_id"]
        elif edge["type"] in {"deployed_in", "attached_to"}:
            parent[edge["source_id"]] = edge["target_id"]

    def boundary(entity: dict[str, Any]) -> dict[str, Any] | None:
        current = entity
        visited: set[str] = set()
        while current and current["canonical_id"] not in visited:
            if current.get(
                "semantic_type"
            ) == "network.boundary" or "network_boundary" in current.get(
                "capabilities", []
            ):
                return current
            visited.add(current["canonical_id"])
            current = by_id.get(parent.get(current["canonical_id"], ""))
        return None

    groups: dict[str, dict[str, Any]] = {}
    group_by_entity: dict[str, str] = {}
    placements: dict[str, dict[str, Any]] = {}
    projected_resources: list[dict[str, Any]] = []
    for entity in entities:
        network = boundary(entity)
        location = entity.get("location") or "unknown"
        if network:
            placement_id = f"network:{network['canonical_id']}"
            placement_label = (
                network.get("name") or network.get("provider_id") or "Network"
            )
            placement_kind = "network"
        elif location not in {"global", "unknown"}:
            placement_id = f"region:{location}:unattached"
            placement_label = f"{location} / Unattached"
            placement_kind = "region_unattached"
        elif location == "global":
            placement_id = f"scope:{entity.get('cloud_scope_id')}:global"
            placement_label = "Global scope"
            placement_kind = "global"
        else:
            placement_id = f"scope:{entity.get('cloud_scope_id')}:unattached"
            placement_label = "Unattached"
            placement_kind = "unattached"
        placements.setdefault(
            placement_id,
            {
                "id": placement_id,
                "label": placement_label,
                "kind": placement_kind,
                "location": location,
                "parent_id": None,
            },
        )
        semantic_type = entity.get("semantic_type") or "generic.resource"
        presentation_ref = entity.get("presentation_ref") or semantic_type
        presentation = (
            bundle.presentation.get(presentation_ref)
            or bundle.presentation.get(semantic_type)
            or bundle.presentation["generic.resource"]
        )
        role = (
            (entity.get("classification") or {}).get("role")
            or entity.get("semantic_facets", {}).get("role")
            or "unknown"
        )
        group_id = _group_id(placement_id, presentation_ref)
        group_by_entity[entity["canonical_id"]] = group_id
        group = groups.setdefault(
            group_id,
            {
                "id": group_id,
                "semantic_type": semantic_type,
                "presentation_ref": presentation_ref,
                "label": presentation.get("label") or semantic_type,
                "unit": presentation.get("unit") or "resource",
                "lane_id": presentation.get("lane") or "other",
                "icon_asset_url": f"/ontology/assets/{bundle.sha256}/{presentation.get('icon_asset', 'generic.svg')}",
                "accent_token": presentation.get("accent_token") or "neutral",
                "handles": presentation.get("handles")
                or ["top", "right", "bottom", "left"],
                "property_schema": bundle.authoring.get(
                    semantic_type, {"type": "object", "properties": {}}
                ),
                "placement_id": placement_id,
                "role": role,
                "count": 0,
                "health": {
                    state: 0
                    for state in (
                        "healthy",
                        "degraded",
                        "unhealthy",
                        "unknown",
                        "not_applicable",
                    )
                },
                "visible": view == "inventory"
                or (view == "logical" and role in LOGICAL_ROLES)
                or (view == "operations" and role in OPERATIONS_ROLES),
                "summary_only": view == "logical" and role not in LOGICAL_ROLES,
            },
        )
        group["count"] += 1
        health_state = (entity.get("health") or {}).get("state") or "unknown"
        if health_state not in group["health"]:
            health_state = "unknown"
        group["health"][health_state] += 1
        if group["visible"] and not group["summary_only"]:
            projected_resources.append(
                {
                    "id": entity["canonical_id"],
                    "name": entity.get("name") or entity.get("provider_id"),
                    "native_type": entity.get("provider_type"),
                    "semantic_type": semantic_type,
                    "group_id": group_id,
                    "placement_id": placement_id,
                    "lane_id": group["lane_id"],
                    "health": entity.get("health") or {"state": "unknown"},
                    "icon_asset_url": group["icon_asset_url"],
                    "unit": group["unit"],
                }
            )

    aggregated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in relationships:
        source = group_by_entity.get(edge["source_id"])
        target = group_by_entity.get(edge["target_id"])
        if not source or not target or source == target:
            continue
        key = (source, target, edge["type"])
        value = aggregated.setdefault(
            key,
            {
                "id": f"edge_{hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]}",
                "source": source,
                "target": target,
                "type": edge["type"],
                "count": 0,
                "provenance": "authoritative",
                "rule_ids": [],
            },
        )
        value["count"] += 1
        if edge.get("rule_id") not in value["rule_ids"]:
            value["rule_ids"].append(edge.get("rule_id"))
    return {
        "view": view,
        "lanes": list(bundle.lanes),
        "placements": list(placements.values()),
        "groups": list(groups.values()),
        "resources": projected_resources,
        "edges": list(aggregated.values()),
    }
