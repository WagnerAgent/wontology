import type { Resource, Snapshot } from "./types";
import type {
  Estate,
  EstateGroup,
  EstateResource,
  Status,
} from "./estate-model";

const labels: Record<string, string> = {
  "network.boundary": "Networks",
  "network.segment": "Subnets",
  "network.interface": "Interfaces",
  "network.security-group": "Security groups",
  "network.load-balancer": "Load balancers",
  "compute.instance": "Instances",
  "compute.function": "Functions",
  "storage.block.volume": "Block volumes",
  "storage.object.bucket": "Buckets",
  "data.database.instance": "Databases",
};

const category = (r: Resource) =>
  r.category === "database" ? "data" : r.category || "unknown";
const region = (r: Resource) => {
  const location = r.location.split("/").pop() || "global";
  return r.provider === "gcp"
    ? location.replace(/(\d)-[a-z]$/, "$1")
    : location;
};
const status = (r: Resource): Status => {
  const value = r.health?.state;
  const observed: Record<string, Status> = {
    healthy: "ok",
    degraded: "warn",
    unhealthy: "bad",
    not_applicable: "na",
  };
  return observed[value] || "unknown";
};

/** Presentation only: membership follows observed containment/attachment paths.
 * Grouping never creates a resource-to-resource dependency in the ontology.
 */
export function toEstate(
  snapshot: Snapshot | null,
  visible?: Resource[],
): Estate {
  const resources = snapshot?.resources || [];
  const byId = new Map(resources.map((r) => [r.canonical_id, r]));
  const networks = new Map(
    resources
      .filter((r) => r.semantic_type === "network.boundary")
      .map((r) => [r.canonical_id, r]),
  );
  const children = new Map<string, Set<string>>();
  const add = (parent: string, child: string) => {
    if (!byId.has(parent) || !byId.has(child) || networks.has(child)) return;
    if (!children.has(parent)) children.set(parent, new Set());
    children.get(parent)!.add(child);
  };
  for (const edge of snapshot?.relationships || []) {
    if (edge.kind === "contains") add(edge.source_id, edge.target_id);
    if (edge.kind === "deployed_in") add(edge.target_id, edge.source_id);
    if (edge.kind === "attached_to") {
      const parent = byId.get(edge.target_id);
      if (
        parent &&
        ["network.interface", "compute.instance"].includes(parent.semantic_type)
      )
        add(edge.target_id, edge.source_id);
    }
  }
  // Two memberships suffice to identify ambiguity, and bound traversal on cycles.
  const membership = new Map<string, Set<string>>();
  const queue: string[] = [];
  for (const id of networks.keys()) {
    membership.set(id, new Set([id]));
    queue.push(id);
  }
  for (let index = 0; index < queue.length; index++) {
    const parent = queue[index];
    for (const child of children.get(parent) || []) {
      const ids = membership.get(child) || new Set<string>();
      const before = ids.size;
      for (const id of membership.get(parent)!) if (ids.size < 2) ids.add(id);
      if (ids.size !== before) {
        membership.set(child, ids);
        queue.push(child);
      }
    }
  }
  const vpcs = new Map<string, Estate["vpcs"][number]>();
  const groups = new Map<string, EstateGroup>();
  const mapped: EstateResource[] = [];
  const counts = { ok: 0, warn: 0, bad: 0, unknown: 0, na: 0 };
  for (const resource of visible || resources) {
    const ids = membership.get(resource.canonical_id);
    const network = ids?.size === 1 ? networks.get([...ids][0]) : undefined;
    const location = region(resource);
    const boundary =
      network?.canonical_id ||
      (ids && ids.size > 1 ? "multiple-networks" : "unassigned");
    const vpc = JSON.stringify([location, boundary]);
    const vpcLabel =
      network?.name ||
      (ids && ids.size > 1
        ? "Multiple networks"
        : "Outside / unassigned network");
    vpcs.set(vpc, {
      key: vpc,
      label: vpcLabel,
      region: location,
      kind: network ? "network" : "scope",
    });
    const tier = category(resource);
    const typeLabel =
      labels[resource.semantic_type] ||
      resource.semantic_type.split(".").pop()!.replaceAll("-", " ");
    const icon = `/icons/${tier === "compute" ? "compute" : tier === "network" ? "network" : tier === "data" || tier === "storage" ? "database" : "generic"}.svg`;
    const groupId = JSON.stringify([
      vpc,
      resource.semantic_type,
      resource.provider_type,
    ]);
    const health = status(resource);
    const item: EstateResource = {
      searchText: `${resource.provider_id} ${resource.provider_type} ${JSON.stringify(resource.tags)}`,
      id: resource.canonical_id,
      name: resource.name,
      type: resource.provider_type,
      typeLabel,
      icon,
      unit: "resource",
      vpc,
      vpcLabel,
      region: location,
      tier,
      group: typeLabel,
      groupId,
      status: health,
    };
    mapped.push(item);
    counts[health]++;
    let group = groups.get(groupId);
    if (!group) {
      group = {
        id: groupId,
        name: typeLabel,
        type: resource.provider_type,
        typeLabel,
        icon,
        unit: "resource",
        tier,
        tierLabel: tier,
        vpc,
        vpcLabel,
        region: location,
        count: 0,
        ok: 0,
        warn: 0,
        bad: 0,
        unknown: 0,
        na: 0,
        status: "unknown",
      };
      groups.set(groupId, group);
    }
    group.count++;
    group[health]++;
    group.status = group.bad
      ? "bad"
      : group.warn
        ? "warn"
        : group.unknown
          ? "unknown"
          : group.ok
            ? "ok"
            : "na";
  }
  const groupFor = new Map(mapped.map((r) => [r.id, r.groupId]));
  const deps: Estate["deps"] = [];
  const seen = new Set<string>();
  for (const edge of snapshot?.relationships || []) {
    const source = groupFor.get(edge.source_id),
      target = groupFor.get(edge.target_id);
    if (!source || !target || source === target) continue;
    const key = JSON.stringify([source, target]);
    if (!seen.has(key)) {
      seen.add(key);
      deps.push([source, target]);
    }
  }
  const order = [
    "network",
    "compute",
    "data",
    "storage",
    "messaging",
    "security",
    "identity",
    "observability",
    "unknown",
  ];
  const lanes = [...new Set(mapped.map((r) => r.tier))]
    .sort(
      (a, b) =>
        (order.indexOf(a) < 0 ? 99 : order.indexOf(a)) -
        (order.indexOf(b) < 0 ? 99 : order.indexOf(b)),
    )
    .map((id, index) => ({ id, label: id, order: index }));
  return {
    vpcs: [...vpcs.values()],
    groups: [...groups.values()],
    resources: mapped,
    deps,
    regions: [...new Set(mapped.map((r) => r.region))].sort(),
    lanes,
    total: mapped.length,
    counts,
  };
}
